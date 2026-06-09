#!/usr/bin/env python3
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from xml.sax.saxutils import escape


COLORS = {
    "p95": "#2563eb",
    "p99": "#dc2626",
    "throughput": "#16a34a",
    "error": "#9333ea",
    "grid": "#d7dde5",
    "axis": "#334155",
    "text": "#0f172a",
    "muted": "#64748b",
}


def parse_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def load_rows(input_file, scenario=None, run_id=None):
    rows = []

    with input_file.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            if scenario and row.get("scenario") != scenario:
                continue
            if run_id and row.get("run_id") != run_id:
                continue

            parsed = {
                "scenario": row.get("scenario", ""),
                "phase": row.get("phase", ""),
                "run_id": row.get("run_id", ""),
                "level": int(row.get("level") or 0),
                "load_vus": int(row.get("load_vus") or 0),
                "replication": int(row.get("replication") or 0),
                "latency_p95_ms": parse_float(row.get("latency_p95_ms")),
                "latency_p99_ms": parse_float(row.get("latency_p99_ms")),
                "throughput_rps": parse_float(row.get("throughput_rps")),
                "error_rate": parse_float(row.get("error_rate")),
            }
            rows.append(parsed)

    return sorted(rows, key=lambda item: (item["load_vus"], item["replication"]))


def group_medians(rows, field):
    values_by_vus = defaultdict(list)

    for row in rows:
        value = row.get(field)
        if value is not None:
            values_by_vus[row["load_vus"]].append(value)

    return [
        {"load_vus": load_vus, "value": median(values)}
        for load_vus, values in sorted(values_by_vus.items())
        if values
    ]


def max_value(rows, fields):
    values = []

    for row in rows:
        for field in fields:
            value = row.get(field)
            if value is not None:
                values.append(value)

    return max(values) if values else 1


def nice_max(value):
    if value <= 0:
        return 1

    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude

    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10

    return nice * magnitude


def format_tick(value, max_y):
    if max_y <= 2:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    if max_y <= 20:
        return f"{value:.1f}".rstrip("0").rstrip(".")

    return f"{value:.0f}"


class Svg:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            "<style>",
            "text { font-family: Inter, Arial, sans-serif; fill: #0f172a; }",
            ".small { font-size: 18px; }",
            ".label { font-size: 20px; fill: #475569; }",
            ".title { font-size: 32px; font-weight: 700; }",
            ".panel-title { font-size: 24px; font-weight: 700; }",
            ".legend { font-size: 19px; }",
            "</style>",
            '<rect width="100%" height="100%" fill="#ffffff"/>',
        ]

    def add(self, text):
        self.parts.append(text)

    def text(self, x, y, text, klass="small", anchor="start", color=None):
        color_attr = f' fill="{color}"' if color else ""
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{klass}" text-anchor="{anchor}"{color_attr}>{escape(str(text))}</text>'
        )

    def finish(self):
        self.parts.append("</svg>")
        return "\n".join(self.parts) + "\n"


def scale_x(load_vus, x_values, left, width):
    if len(x_values) == 1:
        return left + width / 2

    min_x = min(x_values)
    max_x = max(x_values)
    return left + ((load_vus - min_x) / (max_x - min_x)) * width


def scale_y(value, max_y, top, height):
    return top + height - (value / max_y) * height


def draw_panel(svg, x, y, width, height, title, y_label, rows, series, max_y=None):
    margin_left = 86
    margin_right = 32
    margin_top = 56
    margin_bottom = 68
    plot_x = x + margin_left
    plot_y = y + margin_top
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    x_values = sorted({row["load_vus"] for row in rows})

    if not max_y:
        max_y = nice_max(max_value(rows, [item["field"] for item in series]) * 1.08)

    svg.add(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#f8fafc" stroke="#cbd5e1" rx="10"/>'
    )
    svg.text(x + 22, y + 36, title, "panel-title")
    svg.text(plot_x - 74, plot_y + plot_h / 2, y_label, "label", color=COLORS["muted"])

    for i in range(6):
        tick_value = max_y * i / 5
        tick_y = scale_y(tick_value, max_y, plot_y, plot_h)
        svg.add(
            f'<line x1="{plot_x}" y1="{tick_y:.1f}" x2="{plot_x + plot_w}" y2="{tick_y:.1f}" stroke="{COLORS["grid"]}" stroke-width="1"/>'
        )
        svg.text(
            plot_x - 14,
            tick_y + 6,
            format_tick(tick_value, max_y),
            "small",
            "end",
            COLORS["muted"],
        )

    for load_vus in x_values:
        tick_x = scale_x(load_vus, x_values, plot_x, plot_w)
        svg.add(
            f'<line x1="{tick_x:.1f}" y1="{plot_y}" x2="{tick_x:.1f}" y2="{plot_y + plot_h}" stroke="{COLORS["grid"]}" stroke-width="1"/>'
        )
        svg.text(tick_x, plot_y + plot_h + 36, load_vus, "small", "middle", COLORS["muted"])

    svg.add(
        f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" stroke="{COLORS["axis"]}" stroke-width="2"/>'
    )
    svg.add(
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" stroke="{COLORS["axis"]}" stroke-width="2"/>'
    )
    svg.text(plot_x + plot_w / 2, y + height - 18, "VUs", "label", "middle", COLORS["muted"])

    legend_x = x + width - 260
    legend_y = y + 38

    for index, item in enumerate(series):
        color = item["color"]
        field = item["field"]
        label = item["label"]
        median_points = group_medians(rows, field)
        points = [
            (
                scale_x(row["load_vus"], x_values, plot_x, plot_w),
                scale_y(row[field], max_y, plot_y, plot_h),
            )
            for row in rows
            if row.get(field) is not None
        ]

        for point_x, point_y in points:
            svg.add(
                f'<circle cx="{point_x:.1f}" cy="{point_y:.1f}" r="5" fill="{color}" opacity="0.38"/>'
            )

        median_path = [
            (
                scale_x(point["load_vus"], x_values, plot_x, plot_w),
                scale_y(point["value"], max_y, plot_y, plot_h),
            )
            for point in median_points
        ]
        if median_path:
            commands = " ".join(
                f"{'M' if point_index == 0 else 'L'} {point_x:.1f} {point_y:.1f}"
                for point_index, (point_x, point_y) in enumerate(median_path)
            )
            svg.add(
                f'<path d="{commands}" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
            )

        marker_y = legend_y + index * 28
        svg.add(f'<circle cx="{legend_x}" cy="{marker_y - 6}" r="6" fill="{color}"/>')
        svg.text(legend_x + 14, marker_y, label, "legend")


def subtitle_from_rows(rows):
    scenarios = sorted({row["scenario"] for row in rows if row["scenario"]})
    run_ids = sorted({row["run_id"] for row in rows if row["run_id"]})
    phases = sorted({row["phase"] for row in rows if row["phase"]})
    parts = []

    if scenarios:
        parts.append("scenario " + ", ".join(scenarios))
    if phases:
        parts.append(", ".join(phases))
    if run_ids:
        parts.append("run " + ", ".join(run_ids))

    return " | ".join(parts)


def render(rows, output_file, title):
    width = 1600
    height = 1040
    svg = Svg(width, height)
    subtitle = subtitle_from_rows(rows)
    latency_max = nice_max(max_value(rows, ["latency_p95_ms", "latency_p99_ms"]) * 1.08)
    throughput_max = nice_max(max_value(rows, ["throughput_rps"]) * 1.08)
    error_max = max(nice_max(max_value(rows, ["error_rate"]) * 100 * 1.08), 1)

    svg.text(52, 58, title, "title")
    if subtitle:
        svg.text(52, 92, subtitle, "label", color=COLORS["muted"])
    svg.text(
        width - 52,
        92,
        "dots = replications; lines = median by VUs",
        "label",
        "end",
        COLORS["muted"],
    )

    draw_panel(
        svg,
        40,
        130,
        1520,
        420,
        "Latency by load level",
        "ms",
        rows,
        [
            {"field": "latency_p95_ms", "label": "p95 latency", "color": COLORS["p95"]},
            {"field": "latency_p99_ms", "label": "p99 latency", "color": COLORS["p99"]},
        ],
        latency_max,
    )
    draw_panel(
        svg,
        40,
        590,
        740,
        380,
        "Throughput by load level",
        "req/s",
        rows,
        [
            {
                "field": "throughput_rps",
                "label": "throughput",
                "color": COLORS["throughput"],
            }
        ],
        throughput_max,
    )

    error_rows = [
        {**row, "error_rate_percent": (row["error_rate"] or 0) * 100}
        for row in rows
        if row.get("error_rate") is not None
    ]
    draw_panel(
        svg,
        820,
        590,
        740,
        380,
        "Error rate by load level",
        "%",
        error_rows,
        [
            {
                "field": "error_rate_percent",
                "label": "error rate",
                "color": COLORS["error"],
            }
        ],
        error_max,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(svg.finish(), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Generate an SVG figure from a k6 summary CSV."
    )
    parser.add_argument(
        "--input",
        default="results/processed/k6-summary.csv",
        help="Input CSV generated by analysis/summarize-k6-results.py.",
    )
    parser.add_argument(
        "--output",
        default="results/plots/k6-summary.svg",
        help="Output SVG figure.",
    )
    parser.add_argument("--scenario", help="Optional scenario filter, for example C2.")
    parser.add_argument("--run-id", help="Optional run_id filter.")
    parser.add_argument(
        "--title",
        default="k6 exploratory performance summary",
        help="Figure title.",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)
    rows = load_rows(input_file, scenario=args.scenario, run_id=args.run_id)

    if not rows:
        raise SystemExit("No rows found for the selected input/filter.")

    render(rows, output_file, args.title)
    print(f"Wrote {output_file}")


if __name__ == "__main__":
    main()
