#!/usr/bin/env python3
"""Non-parametric statistical analysis for confirmatory k6 results.

The script intentionally uses only Python's standard library so it can run in
the experiment repository without extra dependencies.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
from collections import defaultdict
from pathlib import Path


METRICS = [
    "latency_avg_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "throughput_rps",
    "error_rate",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rank_values(values: list[float]) -> tuple[list[float], dict[int, int]]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    tie_counts: dict[int, int] = {}
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for idx, _ in ordered[i:j]:
            ranks[idx] = avg_rank
        tie_size = j - i
        if tie_size > 1:
            tie_counts[i] = tie_size
        i = j
    return ranks, tie_counts


def regularized_gamma_q(a: float, x: float) -> float:
    """Upper regularized incomplete gamma Q(a, x).

    Implementation follows the common series / continued fraction split used in
    Numerical Recipes. It is sufficient for chi-square survival probabilities.
    """

    if x < 0 or a <= 0:
        raise ValueError("invalid gamma arguments")
    if x == 0:
        return 1.0

    eps = 1e-14
    tiny = 1e-300
    max_iter = 1000

    if x < a + 1.0:
        term = 1.0 / a
        total = term
        ap = a
        for _ in range(max_iter):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * eps:
                p = total * math.exp(-x + a * math.log(x) - math.lgamma(a))
                return max(0.0, min(1.0, 1.0 - p))
        raise RuntimeError("gamma series did not converge")

    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
            return max(0.0, min(1.0, q))
    raise RuntimeError("gamma continued fraction did not converge")


def chi_square_sf(x: float, df: int) -> float:
    return regularized_gamma_q(df / 2.0, x / 2.0)


def kruskal_wallis(groups: dict[str, list[float]]) -> tuple[float, float]:
    labels: list[str] = []
    values: list[float] = []
    for label, group in groups.items():
        labels.extend([label] * len(group))
        values.extend(group)

    n_total = len(values)
    ranks, tie_counts = rank_values(values)
    rank_sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for label, rank in zip(labels, ranks):
        rank_sums[label] += rank
        counts[label] += 1

    h = 0.0
    for label in groups:
        h += (rank_sums[label] ** 2) / counts[label]
    h = (12.0 / (n_total * (n_total + 1.0))) * h - 3.0 * (n_total + 1.0)

    tie_sum = sum(size**3 - size for size in tie_counts.values())
    if tie_sum:
        correction = 1.0 - tie_sum / (n_total**3 - n_total)
        h /= correction

    p_value = chi_square_sf(h, len(groups) - 1)
    return h, p_value


def normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def mann_whitney_u(x: list[float], y: list[float]) -> tuple[float, float]:
    values = x + y
    ranks, tie_counts = rank_values(values)
    n1 = len(x)
    n2 = len(y)
    r1 = sum(ranks[:n1])
    u1 = r1 - n1 * (n1 + 1) / 2.0

    mean_u = n1 * n2 / 2.0
    n_total = n1 + n2
    tie_term = sum(size**3 - size for size in tie_counts.values())
    variance = n1 * n2 / 12.0 * ((n_total + 1.0) - tie_term / (n_total * (n_total - 1.0)))
    if variance <= 0:
        return u1, 1.0
    z = (u1 - mean_u) / math.sqrt(variance)
    return u1, normal_two_sided_p(z)


def cliffs_delta(x: list[float], y: list[float]) -> float:
    greater = 0
    lower = 0
    for a in x:
        for b in y:
            if a > b:
                greater += 1
            elif a < b:
                lower += 1
    return (greater - lower) / (len(x) * len(y))


def effect_magnitude(delta: float) -> str:
    value = abs(delta)
    if value < 0.147:
        return "negligible"
    if value < 0.33:
        return "small"
    if value < 0.474:
        return "medium"
    return "large"


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def format_float(value: float) -> str:
    if abs(value) < 0.0001 and value != 0:
        return f"{value:.3e}"
    return f"{value:.6f}"


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run non-parametric statistics on confirmatory k6 CSV data.")
    parser.add_argument(
        "--input",
        default="results/processed/k6-summary-with-c1-c2-c3-c4-confirmatory.csv",
        help="Input per-replication CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/processed",
        help="Directory for statistical output CSV files.",
    )
    args = parser.parse_args()

    rows = [row for row in read_rows(Path(args.input)) if row.get("phase") == "confirmatory"]
    grouped: dict[tuple[int, str, str], list[float]] = defaultdict(list)
    for row in rows:
        scenario = row["scenario"]
        load_vus = int(row["load_vus"])
        for metric in METRICS:
            grouped[(load_vus, metric, scenario)].append(float(row[metric]))

    loads = sorted({int(row["load_vus"]) for row in rows})
    scenarios = sorted({row["scenario"] for row in rows})

    kruskal_rows: list[dict[str, object]] = []
    pairwise_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for load_vus in loads:
        for metric in METRICS:
            groups = {scenario: grouped[(load_vus, metric, scenario)] for scenario in scenarios}
            h_stat, p_value = kruskal_wallis(groups)
            kruskal_rows.append(
                {
                    "load_vus": load_vus,
                    "metric": metric,
                    "h_statistic": format_float(h_stat),
                    "p_value": format_float(p_value),
                    "significant_0_05": p_value < 0.05,
                }
            )

            for scenario in scenarios:
                values = groups[scenario]
                summary_rows.append(
                    {
                        "load_vus": load_vus,
                        "metric": metric,
                        "scenario": scenario,
                        "n": len(values),
                        "mean": format_float(mean(values)),
                        "median": format_float(median(values)),
                    }
                )

            comparisons = list(itertools.combinations(scenarios, 2))
            for left, right in comparisons:
                left_values = groups[left]
                right_values = groups[right]
                u_stat, p_pair = mann_whitney_u(left_values, right_values)
                delta = cliffs_delta(left_values, right_values)
                pairwise_rows.append(
                    {
                        "load_vus": load_vus,
                        "metric": metric,
                        "scenario_a": left,
                        "scenario_b": right,
                        "u_statistic": format_float(u_stat),
                        "p_value": format_float(p_pair),
                        "p_bonferroni_6": format_float(min(p_pair * len(comparisons), 1.0)),
                        "cliffs_delta_a_minus_b": format_float(delta),
                        "effect_magnitude": effect_magnitude(delta),
                        "median_a": format_float(median(left_values)),
                        "median_b": format_float(median(right_values)),
                    }
                )

    pair_count = len(list(itertools.combinations(scenarios, 2)))
    global_pairwise_count = len(METRICS) * len(loads) * pair_count
    for row in pairwise_rows:
        raw_p_value = float(row["p_value"])
        row["p_bonferroni_global"] = format_float(
            min(raw_p_value * global_pairwise_count, 1.0)
        )

    output_dir = Path(args.output_dir)
    write_csv(
        output_dir / "stats-confirmatory-kruskal.csv",
        kruskal_rows,
        ["load_vus", "metric", "h_statistic", "p_value", "significant_0_05"],
    )
    write_csv(
        output_dir / "stats-confirmatory-pairwise.csv",
        pairwise_rows,
        [
            "load_vus",
            "metric",
            "scenario_a",
            "scenario_b",
            "u_statistic",
            "p_value",
            "p_bonferroni_6",
            "p_bonferroni_global",
            "cliffs_delta_a_minus_b",
            "effect_magnitude",
            "median_a",
            "median_b",
        ],
    )
    write_csv(
        output_dir / "stats-confirmatory-summary.csv",
        summary_rows,
        ["load_vus", "metric", "scenario", "n", "mean", "median"],
    )

    print(f"Wrote {output_dir / 'stats-confirmatory-kruskal.csv'}")
    print(f"Wrote {output_dir / 'stats-confirmatory-pairwise.csv'}")
    print(f"Wrote {output_dir / 'stats-confirmatory-summary.csv'}")


if __name__ == "__main__":
    main()
