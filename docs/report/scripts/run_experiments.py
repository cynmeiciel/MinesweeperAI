"""Run reproducible Minesweeper experiment suites and write raw CSV data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minesweeper.analysis.batch import CSV_FIELDS, GameRecord, run_game
from minesweeper.core.config import FirstClick, FloodFill, GameConfig
from minesweeper.solver import ConstraintSolver, DfsSolver, RandomSolver, RuleBasedSolver, Solver


SOLVERS = ("random", "lv1", "lv2", "lv3")
PRESETS = {
    "tiny": (5, 5, 3),
    "beginner": (9, 9, 10),
    "intermediate": (16, 16, 40),
    "expert": (16, 30, 99),
}
EXPERIMENT_FIELDS = ("experiment_id", "opening_strategy", "include_outside")


@dataclass
class Experiment:
    experiment_id: str
    groups: list[str]
    solver: str
    config: GameConfig
    opening_strategy: str
    include_outside: bool
    games: int
    group_games: dict[str, int] = field(default_factory=dict)
    csv_path: str = ""
    completed_games: int = 0
    status: str = "pending"
    seed_start: int | None = None
    seed_end: int | None = None

    def manifest_config(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "groups": self.groups,
            "group_games": self.group_games,
            "solver": self.solver,
            "rows": self.config.rows,
            "cols": self.config.cols,
            "mines": self.config.mines,
            "first_click": self.config.first_click.name,
            "chord": self.config.chord,
            "flood_fill": self.config.flood_fill.name,
            "opening_strategy": self.opening_strategy,
            "include_outside": self.include_outside,
            "seed_start": self.seed_start,
            "seed_end": self.seed_end,
            "games_expected": self.games,
            "games_completed": self.completed_games,
            "csv_path": self.csv_path,
            "status": self.status,
        }


def _solver_factory(
    solver_name: str, opening_strategy: str, include_outside: bool
) -> tuple[type[Solver], Callable[[random.Random], Solver]]:
    if solver_name == "random":
        return RandomSolver, lambda rng: RandomSolver(rng)
    if solver_name == "lv1":
        return RuleBasedSolver, lambda rng: RuleBasedSolver(
            rng, opening_strategy=opening_strategy
        )
    if solver_name == "lv2":
        return ConstraintSolver, lambda rng: ConstraintSolver(
            rng, opening_strategy=opening_strategy
        )
    if solver_name == "lv3":
        return DfsSolver, lambda rng: DfsSolver(
            rng,
            opening_strategy=opening_strategy,
            include_outside=include_outside,
        )
    raise ValueError(f"unknown solver: {solver_name}")


def _experiment_id(
    solver: str, config: GameConfig, opening_strategy: str, include_outside: bool
) -> str:
    return "_".join(
        (
            solver,
            f"{config.rows}x{config.cols}-{config.mines}",
            config.first_click.name.lower(),
            opening_strategy,
            config.flood_fill.name.lower(),
            f"outside{int(include_outside)}",
        )
    )


def build_experiments(suite: str, games_override: int | None) -> list[Experiment]:
    if suite not in {"all", "main", "first-click", "density", "flood-fill", "corner", "outside"}:
        raise ValueError(f"unknown suite: {suite}")

    experiments: dict[tuple, Experiment] = {}

    def add(
        group: str,
        solver: str,
        rows: int,
        cols: int,
        mines: int,
        first_click: FirstClick = FirstClick.OPENING,
        flood_fill: FloodFill = FloodFill.BFS,
        opening_strategy: str = "center",
        include_outside: bool = False,
        games: int = 1000,
    ) -> None:
        if solver == "random":
            opening_strategy = "random"
        config = GameConfig(
            rows,
            cols,
            mines,
            first_click=first_click,
            chord=True,
            flood_fill=flood_fill,
            seed=0,
        )
        key = (
            solver,
            rows,
            cols,
            mines,
            first_click,
            flood_fill,
            opening_strategy,
            include_outside,
        )
        experiment = experiments.get(key)
        if experiment is None:
            experiment = Experiment(
                experiment_id=_experiment_id(solver, config, opening_strategy, include_outside),
                groups=[group],
                solver=solver,
                config=config,
                opening_strategy=opening_strategy,
                include_outside=include_outside,
                games=games_override if games_override is not None else games,
                group_games={group: games_override if games_override is not None else games},
            )
            experiments[key] = experiment
        elif group not in experiment.groups:
            experiment.groups.append(group)
            experiment.group_games[group] = games_override if games_override is not None else games
            experiment.games = max(experiment.group_games.values())

    groups = {suite} if suite != "all" else {
        "main", "first-click", "density", "flood-fill", "corner", "outside"
    }
    if "main" in groups:
        for solver in SOLVERS:
            for name, (rows, cols, mines) in PRESETS.items():
                add("main", solver, rows, cols, mines, games=300 if name == "expert" else 1000)
    if "first-click" in groups:
        for first_click in FirstClick:
            add("first-click", "lv3", 9, 9, 10, first_click=first_click)
    if "density" in groups:
        for mines in range(5, 25):
            add("density", "lv3", 9, 9, mines, games=500)
    if "flood-fill" in groups:
        for flood_fill in FloodFill:
            add("flood-fill", "lv3", 9, 9, 10, flood_fill=flood_fill)
    if "corner" in groups:
        for opening_strategy in ("center", "corner"):
            for first_click in (FirstClick.SAFE, FirstClick.OPENING):
                add(
                    "corner",
                    "lv3",
                    9,
                    9,
                    10,
                    first_click=first_click,
                    opening_strategy=opening_strategy,
                )
    if "outside" in groups:
        for rows, cols, mines, games in (
            (9, 9, 10, 1000),
            (16, 16, 40, 1000),
            (16, 30, 99, 300),
        ):
            for include_outside in (False, True):
                add(
                    "outside",
                    "lv3",
                    rows,
                    cols,
                    mines,
                    include_outside=include_outside,
                    games=games,
                )
    return list(experiments.values())


def _git(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _environment() -> dict[str, object]:
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "os": platform.platform(),
        "cpu": platform.processor() or None,
    }


def _manifest(experiments: list[Experiment], start: str, command: list[str]) -> dict[str, object]:
    status = _git(["git", "status", "--porcelain"])
    return {
        "schema_version": 2,
        "git_commit": _git(["git", "rev-parse", "HEAD"]),
        "git_status": "clean" if not status else "dirty",
        "git_status_porcelain": status,
        "working_tree_patch": "working_tree.patch" if status else None,
        "environment": _environment(),
        "started_at": start,
        "ended_at": None,
        "command": command,
        "experiments": [experiment.manifest_config() for experiment in experiments],
    }


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _record_row(record: GameRecord, experiment: Experiment) -> dict[str, object]:
    row = asdict(record)
    row.update(
        experiment_id=experiment.experiment_id,
        opening_strategy=experiment.opening_strategy,
        include_outside=experiment.include_outside,
    )
    return row


def save_source_provenance(out_dir: Path, manifest: dict[str, object]) -> None:
    """Preserve runtime sources for either the report or ablation pipeline."""
    # Capture provenance before creating output files. The snapshot also preserves
    # untracked Python files, which git diff alone cannot capture.
    source_paths = sorted(set(ROOT.glob("minesweeper/**/*.py")) | set(ROOT.glob("docs/report/scripts/*.py")))
    manifest["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_dir / "source_snapshot.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_paths:
            archive.write(path, str(path.relative_to(ROOT)))
    _write_manifest(out_dir / "manifest.json", manifest)
    if manifest["git_status"] == "dirty":
        patch = _git(["git", "diff", "HEAD", "--binary"]) or ""
        (out_dir / "working_tree.patch").write_text(patch, encoding="utf-8")


def run(out_dir: Path, suite: str, seed_start: int, games_override: int | None) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"output directory is not empty: {out_dir}")
    experiments = build_experiments(suite, games_override)
    start = datetime.now().astimezone().isoformat()
    manifest = _manifest(experiments, start, sys.argv)
    manifest.update(suite=suite, seed_start=seed_start, games_override=games_override)
    save_source_provenance(out_dir, manifest)

    try:
        for index, experiment in enumerate(experiments, start=1):
            solver_cls, factory = _solver_factory(
                experiment.solver, experiment.opening_strategy, experiment.include_outside
            )
            experiment.csv_path = f"{experiment.experiment_id}.csv"
            experiment.status = "running"
            experiment.seed_start = seed_start
            experiment.seed_end = seed_start + experiment.games - 1
            print(f"[{index}/{len(experiments)}] starting {experiment.experiment_id}: {experiment.games} games", flush=True)
            manifest["experiments"] = [item.manifest_config() for item in experiments]
            _write_manifest(out_dir / "manifest.json", manifest)
            csv_path = out_dir / experiment.csv_path
            with csv_path.open("x", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS + list(EXPERIMENT_FIELDS))
                writer.writeheader()
                handle.flush()
                for offset in range(experiment.games):
                    config = replace(experiment.config, seed=seed_start + offset)
                    record = run_game(config, solver_cls, solver_factory=factory)
                    writer.writerow(_record_row(record, experiment))
                    handle.flush()
                    experiment.completed_games += 1
            experiment.status = "complete"
            print(
                f"[{index}/{len(experiments)}] {experiment.experiment_id}: "
                f"{experiment.completed_games}/{experiment.games}"
            )
            manifest["experiments"] = [
                item.manifest_config() for item in experiments
            ]
            checksums = manifest.setdefault("csv_sha256", {})
            checksums[experiment.experiment_id] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
            _write_manifest(out_dir / "manifest.json", manifest)
    finally:
        manifest["ended_at"] = datetime.now().astimezone().isoformat()
        manifest["experiments"] = [experiment.manifest_config() for experiment in experiments]
        _write_manifest(out_dir / "manifest.json", manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "main", "first-click", "density", "flood-fill", "corner", "outside"), default="all")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--games", type=int)
    args = parser.parse_args(argv)
    if args.games is not None and args.games < 1:
        parser.error("--games must be at least 1")
    run(args.out_dir, args.suite, args.seed_start, args.games)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
