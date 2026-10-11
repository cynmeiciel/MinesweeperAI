"""Plot experiment summaries into PNG and SVG figures."""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _read_summary(data_dir: Path) -> list[dict[str, str]]:
    # Group views preserve the density group's 500-seed prefix of a shared
    # 1,000-game baseline; all values still come from validated raw CSVs.
    path = data_dir / "group_summary.csv"
    if not path.exists():
        path = data_dir / "summary.csv"
    if not path.exists():
        raise ValueError(f"missing summary: {path}; run summarize_results.py first")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _save(figure, output: Path, name: str) -> None:
    figure.savefig(output / f"{name}.png", dpi=300, bbox_inches="tight")
    figure.savefig(output / f"{name}.svg", bbox_inches="tight")


def plot_solver(rows: list[dict[str, str]], output: Path) -> bool:
    main = [row for row in rows if "main" in row["groups"]]
    if not main:
        return False
    dimensions = sorted({(int(row['rows']), int(row['cols'])) for row in main})
    presets = [f"{r}x{c}" for r, c in dimensions]
    solvers = ["random", "lv1", "lv2", "lv3"]
    values = defaultdict(dict)
    intervals = defaultdict(dict)
    for row in main:
        preset = f"{row['rows']}x{row['cols']}"
        if row["solver"] in values[preset]:
            raise ValueError(f"multiple main variants for {preset}/{row['solver']}")
        values[preset][row["solver"]] = float(row["win_rate"]) * 100
        intervals[preset][row["solver"]] = (
            max(0.0, float(row["win_rate"]) * 100 - float(row["ci_low"]) * 100),
            max(0.0, float(row["ci_high"]) * 100 - float(row["win_rate"]) * 100),
        )
    missing = [(preset, solver) for preset in presets for solver in solvers if solver not in values[preset]]
    if missing or len(main) != 16:
        raise ValueError(f"incomplete main group; missing solver/preset data: {missing}")
    import matplotlib.pyplot as plt
    figure, axis = plt.subplots(figsize=(10, 6))
    width = 0.8 / len(solvers)
    positions = list(range(len(presets)))
    for index, solver in enumerate(solvers):
        heights = [values[preset][solver] for preset in presets]
        errors = [intervals[preset][solver] for preset in presets]
        axis.bar(
            [position + index * width for position in positions],
            heights,
            width,
            label=solver,
            yerr=list(zip(*errors)) if errors else None,
            capsize=3,
            hatch=["//", "\\\\", "..", "xx"][index],
        )
    sample_sizes = {f"{row['rows']}x{row['cols']}": row['games'] for row in main}
    sizes = ", ".join(f"{preset}: n={sample_sizes[preset]}" for preset in presets)
    axis.set_title("Win rate by solver — OPENING, chord on, BFS\n" + sizes, fontsize=11)
    axis.set_xlabel("Preset dimensions")
    axis.set_ylabel("Win rate (%)")
    axis.set_ylim(0, 100)
    axis.set_xticks([position + width * (len(solvers) - 1) / 2 for position in positions], presets)
    axis.legend(title="Solver")
    figure.tight_layout()
    _save(figure, output, "win_rate_by_solver")
    plt.close(figure)
    return True


def plot_density(rows: list[dict[str, str]], output: Path) -> bool:
    density = [
        row for row in rows
        if "density" in row["groups"] and row["solver"] == "lv3"
    ]
    if not density:
        return False
    if len(density) != 20 or {int(row['mines']) for row in density} != set(range(5, 25)):
        raise ValueError("incomplete density group: require 5–24 mines")
    import matplotlib.pyplot as plt

    density.sort(key=lambda row: float(row["density"]))
    x = [float(row["density"]) * 100 for row in density]
    y = [float(row["win_rate"]) * 100 for row in density]
    low = [float(row["ci_low"]) * 100 for row in density]
    high = [float(row["ci_high"]) * 100 for row in density]
    figure, axis = plt.subplots(figsize=(9, 6))
    axis.plot(x, y, marker="o", label="LV3")
    axis.fill_between(x, low, high, alpha=0.2, label="95% Wilson CI")
    sizes = ", ".join(sorted({row['games'] for row in density}))
    axis.set_title(f"LV3 9×9 — OPENING, center, BFS, outside=False\nn={sizes} per point")
    axis.set_xlabel("Mine density (%)")
    axis.set_ylabel("Win rate (%)")
    axis.set_ylim(0, 100)
    axis.legend()
    figure.tight_layout()
    _save(figure, output, "win_rate_by_density")
    plt.close(figure)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        rows = _read_summary(args.data_dir)
        output = args.data_dir / "figures"
        output.mkdir(exist_ok=True)
        produced = []
        if plot_solver(rows, output):
            produced.append("win_rate_by_solver")
        else:
            print("No main group: win_rate_by_solver not produced.")
        if plot_density(rows, output):
            produced.append("win_rate_by_density")
        else:
            print("No density group: win_rate_by_density not produced.")
        if not produced:
            raise ValueError("no complete data groups available for plotting")
    except (OSError, ValueError, ImportError) as exc:
        parser.error(str(exc))
    print(f"wrote figures: {', '.join(produced)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
