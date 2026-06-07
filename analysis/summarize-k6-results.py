#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path


FILENAME_RE = re.compile(
    r"level-(?P<level>\d+)-vus-(?P<vus>\d+)-rep-(?P<replication>\d+)-summary\.json$"
)


def metric_value(metrics, name, field, default=""):
    metric = metrics.get(name, {})
    value = metric.get(field, default)

    if value is None:
        return default

    return value


def preferred_metric_value(metrics, preferred_name, fallback_name, field, default=""):
    value = metric_value(metrics, preferred_name, field, default)

    if value != default:
        return value

    return metric_value(metrics, fallback_name, field, default)


def load_metadata(summary_file):
    metadata_file = summary_file.parent / "metadata.env"
    metadata = {}

    if not metadata_file.exists():
        return metadata

    for line in metadata_file.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        metadata[key] = value

    return metadata


def summarize_file(summary_file):
    match = FILENAME_RE.search(summary_file.name)

    if not match:
        return None

    data = json.loads(summary_file.read_text(encoding="utf-8"))
    metrics = data.get("metrics", {})
    metadata = load_metadata(summary_file)

    return {
        "scenario": metadata.get("SCENARIO", ""),
        "phase": metadata.get("EXPERIMENT_PHASE", ""),
        "run_id": metadata.get("RUN_ID", ""),
        "level": match.group("level"),
        "load_vus": match.group("vus"),
        "replication": match.group("replication"),
        "latency_avg_ms": preferred_metric_value(
            metrics, "http_req_duration{phase:measurement}", "http_req_duration", "avg"
        ),
        "latency_p95_ms": preferred_metric_value(
            metrics, "http_req_duration{phase:measurement}", "http_req_duration", "p(95)"
        ),
        "latency_p99_ms": preferred_metric_value(
            metrics, "http_req_duration{phase:measurement}", "http_req_duration", "p(99)"
        ),
        "throughput_rps": metric_value(metrics, "http_reqs", "rate"),
        "error_rate": preferred_metric_value(
            metrics, "http_req_failed{phase:measurement}", "http_req_failed", "value"
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate a simple CSV summary from k6 --summary-export JSON files."
    )
    parser.add_argument(
        "--input-dir",
        default="results/raw",
        help="Directory containing k6 summary JSON files.",
    )
    parser.add_argument(
        "--output",
        default="results/processed/k6-summary.csv",
        help="Output CSV file.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_file = Path(args.output)
    rows = []

    for summary_file in sorted(input_dir.rglob("*-summary.json")):
        row = summarize_file(summary_file)

        if row:
            rows.append(row)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "scenario",
        "phase",
        "run_id",
        "level",
        "load_vus",
        "replication",
        "latency_avg_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "throughput_rps",
        "error_rate",
    ]

    with output_file.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    main()
