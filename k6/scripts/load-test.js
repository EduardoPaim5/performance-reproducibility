import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';

const targetUrl = __ENV.TARGET_URL || 'http://localhost:8080/';
const vus = Number.parseInt(__ENV.VUS || '50', 10);
const rampUpDuration = __ENV.RAMP_UP || '1m';
const warmupDuration = __ENV.WARMUP || '1m';
const duration = __ENV.DURATION || '5m';
const rampDownDuration = __ENV.RAMP_DOWN || '1s';
const thinkTime = Number.parseFloat(__ENV.THINK_TIME || '1');

export const options = {
  scenarios: {
    static_page_load: {
      executor: 'ramping-vus',
      stages: [
        { duration: rampUpDuration, target: vus },
        { duration: warmupDuration, target: vus },
        { duration, target: vus },
        { duration: rampDownDuration, target: 0 },
      ],
      gracefulRampDown: '0s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{phase:measurement}': ['p(95)<500'],
    'http_req_failed{phase:measurement}': ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

function durationToMs(value) {
  const match = /^(\d+(?:\.\d+)?)(ms|s|m|h)$/.exec(value);

  if (!match) {
    return 0;
  }

  const amount = Number.parseFloat(match[1]);
  const unit = match[2];

  if (unit === 'ms') return amount;
  if (unit === 's') return amount * 1000;
  if (unit === 'm') return amount * 60 * 1000;
  if (unit === 'h') return amount * 60 * 60 * 1000;

  return 0;
}

function currentPhase() {
  const rampUpMs = durationToMs(rampUpDuration);
  const warmupMs = durationToMs(warmupDuration);
  const measurementMs = durationToMs(duration);
  const rampDownMs = durationToMs(rampDownDuration);
  const totalMs = rampUpMs + warmupMs + measurementMs + rampDownMs;
  const elapsed = exec.scenario.progress * totalMs;

  if (elapsed < rampUpMs) {
    return 'ramp_up';
  }

  if (elapsed < rampUpMs + warmupMs) {
    return 'warmup';
  }

  return 'measurement';
}

export default function () {
  const phase = currentPhase();
  const response = http.get(targetUrl, {
    tags: {
      scenario: __ENV.SCENARIO || 'manual',
      target: targetUrl,
      phase,
    },
  });

  check(response, {
    'status is 200': (r) => r.status === 200,
    'body is not empty': (r) => r.body && r.body.length > 0,
  });

  sleep(thinkTime);
}
