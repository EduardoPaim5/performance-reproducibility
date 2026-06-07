# Local Prometheus with AWS exporters through an SSH tunnel

Scenario C4 uses an AWS EC2 instance, but Node Exporter and cAdvisor must not be exposed publicly. To keep Prometheus on the local lab server while still collecting metrics from the instance, use an SSH tunnel from the host where local Prometheus runs.

## Assumptions

- The AWS instance already exists and is reachable by SSH.
- Local Prometheus runs on the lab server, not on the dedicated k6 client.
- `AWS_USER`, `AWS_HOST`, and `SSH_KEY` are placeholders and must be replaced in the local environment.
- Node Exporter listens only on the instance, for example on `127.0.0.1:9100`.
- cAdvisor listens only on the instance, for example on `127.0.0.1:8080`.
- Exporter ports must not be allowed in the Security Group.

## SSH tunnel

Run on the local host:

```bash
ssh -i SSH_KEY -N \
  -L 19100:127.0.0.1:9100 \
  -L 18080:127.0.0.1:8080 \
  AWS_USER@AWS_HOST
```

Mappings:

- `127.0.0.1:19100` on the local host points to `127.0.0.1:9100` on the AWS instance.
- `127.0.0.1:18080` on the local host points to `127.0.0.1:8080` on the AWS instance.

If Prometheus runs through `docker/docker-compose.yml`, the file `monitoring/prometheus/prometheus.yml` uses:

- `host.docker.internal:19100` for Node Exporter;
- `host.docker.internal:18080` for cAdvisor.

If Prometheus runs natively on the local host, adjust the targets to:

```yaml
- 127.0.0.1:19100
- 127.0.0.1:18080
```

## Recommended Security Group

Keep only the minimum required exposure:

- port `80/tcp` for the experiment HTTP target, according to the defined policy;
- port `22/tcp` restricted to the administrative client IP;
- internal Swarm ports only when they are actually required between Swarm nodes.

Do not open publicly:

- `9100/tcp` from Node Exporter;
- `8080/tcp` from cAdvisor;
- `9090/tcp` from Prometheus.

## Validation

With the tunnel active, test locally:

```bash
curl http://127.0.0.1:19100/metrics
curl http://127.0.0.1:18080/metrics
```

Then check `Status > Targets` in local Prometheus.
