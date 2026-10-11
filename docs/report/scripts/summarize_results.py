"""Validate experiment data and generate summary.csv and tables.md."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import zipfile
from collections import Counter
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minesweeper.analysis.batch import CSV_FIELDS, wilson_interval

EXPERIMENT_FIELDS = ["experiment_id", "opening_strategy", "include_outside"]
RESULTS = {"won", "lost", "stalled"}
SUMMARY_FIELDS = [
    "experiment_id", "groups", "solver", "rows", "cols", "mines", "density",
    "first_click", "chord", "flood_fill", "opening_strategy", "include_outside",
    "games", "wins", "losses", "stalled", "win_rate", "ci_low", "ci_high",
    "mean_moves", "mean_guesses", "mean_time_ms", "median_time_ms",
    "p95_time_ms", "max_time_ms",
    "mean_safe_coverage", "stalled_safe_coverage",
]


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, using the fixed (n - 1) method."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def load_data(data_dir: Path) -> tuple[dict[str, object], dict[str, list[dict[str, str]]]]:
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") not in (1, 2):
        raise ValueError("unsupported manifest schema")
    if not manifest.get("experiments"):
        raise ValueError("manifest contains no experiments")
    if manifest["schema_version"] == 2:
        from run_experiments import build_experiments
        plan = build_experiments(manifest["suite"], manifest["games_override"])
        expected_plan = {item.experiment_id: item for item in plan}
        actual_ids = [item["experiment_id"] for item in manifest["experiments"]]
        if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_plan):
            raise ValueError("manifest configurations do not match the requested suite")
        with zipfile.ZipFile(data_dir / "source_snapshot.zip") as archive:
            for name, digest in manifest["source_sha256"].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise ValueError(f"source snapshot checksum mismatch: {name}")
    rows_by_id: dict[str, list[dict[str, str]]] = {}
    expected_fields = CSV_FIELDS + EXPERIMENT_FIELDS
    for experiment in manifest.get("experiments", []):
        experiment_id = experiment["experiment_id"]
        if experiment_id in rows_by_id:
            raise ValueError(f"duplicate experiment: {experiment_id}")
        if manifest["schema_version"] == 2:
            planned = expected_plan[experiment_id]
            reference = planned.manifest_config()
            for key in ("solver", "rows", "cols", "mines", "first_click", "chord", "flood_fill", "opening_strategy", "include_outside", "groups", "group_games", "games_expected"):
                if experiment[key] != reference[key]:
                    raise ValueError(f"manifest configuration mismatch: {experiment_id}/{key}")
            if experiment["seed_start"] != manifest["seed_start"]:
                raise ValueError(f"manifest seed start mismatch: {experiment_id}")
        if experiment.get("status") != "complete":
            raise ValueError(f"experiment is incomplete: {experiment_id}")
        expected = int(experiment["games_expected"])
        completed = int(experiment["games_completed"])
        if expected < 1 or int(experiment["seed_end"]) != int(experiment["seed_start"]) + expected - 1:
            raise ValueError(f"invalid expected seed range: {experiment_id}")
        if expected != completed:
            raise ValueError(f"incomplete game count for {experiment_id}: {completed}/{expected}")
        csv_path = data_dir / experiment["csv_path"]
        if not csv_path.resolve().is_relative_to(data_dir.resolve()):
            raise ValueError(f"CSV path escapes data directory: {experiment_id}")
        if not csv_path.exists():
            raise ValueError(f"missing CSV for {experiment_id}: {csv_path}")
        if manifest["schema_version"] == 2 and hashlib.sha256(csv_path.read_bytes()).hexdigest() != manifest["csv_sha256"][experiment_id]:
            raise ValueError(f"CSV checksum mismatch: {experiment_id}")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != expected_fields:
                raise ValueError(f"schema mismatch for {experiment_id}: {reader.fieldnames}")
            rows = list(reader)
        if len(rows) != expected:
            raise ValueError(f"row count mismatch for {experiment_id}: {len(rows)}/{expected}")
        seeds = [int(row["seed"]) for row in rows]
        if len(set(seeds)) != len(seeds):
            raise ValueError(f"duplicate seed in {experiment_id}")
        expected_seeds = set(range(int(experiment["seed_start"]), int(experiment["seed_end"]) + 1))
        if set(seeds) != expected_seeds:
            raise ValueError(f"missing or unexpected seed in {experiment_id}")
        if any(row["result"] not in RESULTS for row in rows):
            raise ValueError(f"invalid result in {experiment_id}")
        for row in rows:
            if set(row) != set(expected_fields) or any(value is None for value in row.values()):
                raise ValueError(f"malformed CSV row: {experiment_id}")
            for key in ("experiment_id", "solver", "rows", "cols", "mines", "first_click", "chord", "flood_fill", "opening_strategy", "include_outside"):
                if row[key] != str(experiment[key]):
                    raise ValueError(f"CSV configuration mismatch: {experiment_id}/{key}")
            safe = int(row["rows"]) * int(row["cols"]) - int(row["mines"])
            revealed = int(row["cells_revealed"])
            moves, guesses = int(row["moves"]), int(row["guesses"])
            duration = float(row["time_ms"])
            if not 0 <= revealed <= safe or int(row["cells_remaining"]) != safe - revealed:
                raise ValueError(f"invalid safe-cell counts: {experiment_id}")
            if not 0 <= guesses <= moves <= 2 * int(row["rows"]) * int(row["cols"]) or not math.isfinite(duration) or duration < 0:
                raise ValueError(f"invalid moves/guesses/time: {experiment_id}")
            if row["result"] == "won" and revealed != safe:
                raise ValueError(f"won game has unrevealed safe cells: {experiment_id}")
            if float(row["density"]) != round(int(row["mines"]) / (int(row["rows"]) * int(row["cols"])), 4):
                raise ValueError(f"CSV density mismatch: {experiment_id}")
        rows_by_id[experiment_id] = rows
    return manifest, rows_by_id


def summarize(manifest: dict[str, object], rows_by_id: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    experiments = {item["experiment_id"]: item for item in manifest["experiments"]}
    output: list[dict[str, object]] = []
    for experiment_id, rows in rows_by_id.items():
        config = experiments[experiment_id]
        wins = sum(row["result"] == "won" for row in rows)
        losses = sum(row["result"] == "lost" for row in rows)
        stalled = sum(row["result"] == "stalled" for row in rows)
        low, high = wilson_interval(wins, len(rows))
        times = [float(row["time_ms"]) for row in rows]
        safe = config["rows"] * config["cols"] - config["mines"]
        coverage = [int(row["cells_revealed"]) / safe for row in rows]
        stalled_coverage = [int(row["cells_revealed"]) / safe for row in rows if row["result"] == "stalled"]
        output.append({
            "experiment_id": experiment_id,
            "groups": ";".join(config["groups"]),
            "solver": config["solver"],
            "rows": config["rows"],
            "cols": config["cols"],
            "mines": config["mines"],
            "density": config["mines"] / (config["rows"] * config["cols"]),
            "first_click": config["first_click"],
            "chord": config["chord"],
            "flood_fill": config["flood_fill"],
            "opening_strategy": config["opening_strategy"],
            "include_outside": config["include_outside"],
            "games": len(rows),
            "wins": wins,
            "losses": losses,
            "stalled": stalled,
            "win_rate": wins / len(rows),
            "ci_low": low,
            "ci_high": high,
            "mean_moves": mean(float(row["moves"]) for row in rows),
            "mean_guesses": mean(float(row["guesses"]) for row in rows),
            "mean_time_ms": mean(times),
            "median_time_ms": median(times),
            "p95_time_ms": percentile(times, 0.95),
            "max_time_ms": max(times),
            "mean_safe_coverage": mean(coverage),
            "stalled_safe_coverage": mean(stalled_coverage) if stalled_coverage else None,
        })
    return output


def group_summaries(manifest, rows_by_id):
    """Reuse CSV seed prefixes at each group's requested sample size."""
    output = []
    for config in manifest["experiments"]:
        for group in config["groups"]:
            count = config.get("group_games", {}).get(group, config["games_expected"])
            start = config["seed_start"]
            rows = [row for row in rows_by_id[config["experiment_id"]] if start <= int(row["seed"]) < start + count]
            if len(rows) != count:
                raise ValueError(f"missing seed prefix for {config['experiment_id']}/{group}")
            view = dict(config, groups=[group])
            output.extend(summarize({"experiments": [view]}, {config["experiment_id"]: rows}))
    return output


def write_summary(data_dir: Path, rows: list[dict[str, object]], filename="summary.csv") -> None:
    with (data_dir / filename).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No data."
    columns = ["experiment_id", "games", "wins", "losses", "stalled", "win_rate", "ci_low", "ci_high", "mean_moves", "mean_guesses", "mean_safe_coverage", "stalled_safe_coverage", "mean_time_ms", "median_time_ms", "p95_time_ms", "max_time_ms"]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def write_tables(data_dir: Path, rows: list[dict[str, object]]) -> None:
    sections = ["# Experiment Tables", "", "All times are milliseconds. Percentiles use linear interpolation with position `(n - 1) * q`.", ""]
    for title, predicate in (
        ("Solver and preset", lambda row: "main" in str(row["groups"])),
        ("First-click rules", lambda row: "first-click" in str(row["groups"])),
        ("Density", lambda row: "density" in str(row["groups"])),
        ("Flood fill", lambda row: "flood-fill" in str(row["groups"])),
        ("Center and corner", lambda row: "corner" in str(row["groups"])),
        ("Frontier and outside", lambda row: "outside" in str(row["groups"])),
        ("LV3 timing", lambda row: row["solver"] == "lv3" and row["groups"] == "main"),
    ):
        sections.extend([f"## {title}", "", _table([row for row in rows if predicate(row)]), ""])
    (data_dir / "tables.md").write_text("\n".join(sections), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest, rows = load_data(args.data_dir)
        summary = summarize(manifest, rows)
        write_summary(args.data_dir, summary)
        grouped = group_summaries(manifest, rows)
        write_summary(args.data_dir, grouped, "group_summary.csv")
        write_tables(args.data_dir, grouped)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"wrote {len(summary)} summary rows to {args.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
