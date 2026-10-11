"""Collect frontiers, run paired INFO games, and replay search ablations."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from statistics import median

from ablation_common import (
    ROOT, VARIANTS, SEARCH_VARIANTS, STATS_FIELDS, COUNTERS, canonical, digest,
    file_digest, snapshot_input, read_jsonl, write_jsonl, replay, result_digest,
)
from run_experiments import _manifest, _write_manifest, save_source_provenance
from minesweeper.analysis.batch import CSV_FIELDS, run_game
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.solver.dfs_solver import DFSStats, DfsSolver

GAME_FIELDS = CSV_FIELDS + ["config_id", "variant", "opening_strategy", "include_outside",
                           "variable_order", "use_propagation", "guess_tiebreak",
                           "collect_stats", "board_fingerprint", "execution_error"] + STATS_FIELDS
FRONTIER_FIELDS = ["snapshot_id", "variant", "variable_order", "use_propagation",
                   "guess_tiebreak", "collect_stats", "occurrences", "measured_repetitions",
                   "warmup_repetitions", "status", "feasibility", "exact_result_sha256"] + STATS_FIELDS


def build_configs(presets, games, opening="center", outside=False, first="OPENING", flood="BFS"):
    if len(set(presets)) != len(presets):
        raise ValueError("duplicate presets")
    output = []
    for name in presets:
        c = PRESETS[name]
        item = dict(preset=name, rows=c.rows, cols=c.cols, mines=c.mines,
                    first_click=first, chord=True, flood_fill=flood,
                    opening_strategy=opening, include_outside=outside,
                    games=games if games is not None else (300 if name == "expert" else 1000))
        item["config_id"] = digest({k: v for k, v in item.items() if k not in ("games", "preset")})[:16]
        output.append(item)
    return output


class TrackedSolver(DfsSolver):
    """Instrumentation via a factory, without patching solver functions."""

    def __init__(self, rng, **kwargs):
        super().__init__(rng, collect_stats=True, **kwargs)
        self.total_stats = DFSStats()
        self.calls = 0

    def next_move(self, view):
        self.calls += 1
        try:
            return super().next_move(view)
        finally:
            self.total_stats.add(self.last_stats)


class BatchWarnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def game(config, seed, variant, frontier_callback=None):
    holder, fingerprint = {}, []
    def factory(rng):
        solver = TrackedSolver(rng, **VARIANTS[variant],
                               opening_strategy=config["opening_strategy"],
                               include_outside=config["include_outside"])
        if frontier_callback is not None:
            solver.frontier_observer = lambda view, constraints: frontier_callback(view, constraints, solver.calls - 1)
        holder["solver"] = solver
        return solver

    def observe(engine, solver, step):
        if not fingerprint and engine.board is not None:
            fingerprint.append(digest({"rows": engine.rows, "cols": engine.cols,
                                       "mines": sorted(engine.board.mines)}))

    cfg = GameConfig(config["rows"], config["cols"], config["mines"],
                     first_click=FirstClick[config["first_click"]],
                     chord=config["chord"], flood_fill=FloodFill[config["flood_fill"]], seed=seed)
    warnings = BatchWarnings()
    logger = logging.getLogger("minesweeper.analysis.batch")
    logger.addHandler(warnings)
    try:
        record = run_game(cfg, DfsSolver, solver_factory=factory, move_observer=observe)
    finally:
        logger.removeHandler(warnings)
    row = asdict(record) | asdict(holder["solver"].total_stats)
    row.update(config_id=config["config_id"], variant=variant,
               opening_strategy=config["opening_strategy"], include_outside=config["include_outside"],
               collect_stats=True, board_fingerprint=fingerprint[0] if fingerprint else "",
               execution_error="; ".join(warnings.messages), **VARIANTS[variant])
    return row


def collect(out, manifest):
    snapshots = {}
    count = 0
    with (out / "collection_games.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, GAME_FIELDS)
        writer.writeheader()
        try:
            for config in manifest["configurations"]:
                print("Collect:", config["preset"], config["games"], "baseline games", flush=True)
                for seed in range(manifest["seed_start"], manifest["seed_start"] + config["games"]):
                    def capture(view, constraints, step):
                        payload = snapshot_input(view, constraints, config)
                        # Sample size and human-readable preset are provenance,
                        # not inputs to inference or duplicate-state identity.
                        payload["config"] = {k: v for k, v in config.items() if k not in ("games", "preset")}
                        sid = digest(payload)
                        item = snapshots.setdefault(sid, dict(snapshot_id=sid, input=payload, occurrences=[]))
                        item["occurrences"].append(dict(seed=seed, step=step, config_id=config["config_id"]))
                    row = game(config, seed, "baseline", capture)
                    writer.writerow(row)
                    handle.flush()
                    count += 1
                    if row["execution_error"]:
                        raise RuntimeError(row["execution_error"])
        finally:
            write_jsonl(out / "frontiers.jsonl", snapshots.values())
            manifest["collection_games_completed"] = count
            manifest["snapshots_unique"] = len(snapshots)
            manifest["snapshot_occurrences"] = sum(len(s["occurrences"]) for s in snapshots.values())
    if not snapshots:
        raise ValueError("No actual DFS frontiers collected; add seeds or a deterministic fixture")


def info_games(out, manifest):
    count = 0
    with (out / "ablation_games.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, GAME_FIELDS)
        writer.writeheader()
        try:
            for config in manifest["configurations"]:
                print("INFO:", config["preset"], config["games"], "paired seeds", flush=True)
                for seed in range(manifest["seed_start"], manifest["seed_start"] + config["games"]):
                    pair = []
                    for variant in ("baseline", "no_info"):
                        row = game(config, seed, variant)
                        writer.writerow(row)
                        handle.flush()
                        count += 1
                        pair.append(row)
                        if row["execution_error"]:
                            raise RuntimeError(row["execution_error"])
                    if not pair[0]["board_fingerprint"] or pair[0]["board_fingerprint"] != pair[1]["board_fingerprint"]:
                        raise ValueError(f"Initial board mismatch for {config['config_id']}/seed {seed}")
        finally:
            manifest["info_games_completed"] = count


def search_replay(out, manifest):
    snapshots = read_jsonl(out / "frontiers.jsonl")
    rng = random.Random(manifest["shuffle_seed"])
    progress = manifest.setdefault("snapshot_status", {})
    with (out / "ablation_frontiers.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FRONTIER_FIELDS)
        writer.writeheader()
        for index, snapshot in enumerate(snapshots):
            sid = snapshot["snapshot_id"]
            progress[sid] = "incomplete"
            _write_manifest(out / "manifest.json", manifest)
            reference = None
            structural, timings = {}, {v: [] for v in SEARCH_VARIANTS}
            # One unrecorded warm-up per variant, then five measured passes.
            for iteration in range(manifest["measured_repetitions"] + 1):
                order = list(SEARCH_VARIANTS)
                rng.shuffle(order)
                for variant in order:
                    exact, stats = replay(snapshot, variant)
                    if reference is None:
                        reference = exact
                    if exact != reference:
                        manifest["replay_error"] = f"solution/probability mismatch: {sid}/{variant}"
                        raise ValueError(manifest["replay_error"])
                    counters = {k: getattr(stats, k) for k in COUNTERS}
                    if variant in structural and counters != structural[variant]:
                        raise ValueError(f"non-repeatable counters: {sid}/{variant}")
                    structural[variant] = counters
                    if iteration:
                        timings[variant].append((stats.dfs_time_ms, stats.probability_time_ms))
            # Flush only a complete, verified triple; an interrupted snapshot is
            # excluded for ALL variants, never just for the slow variant.
            for variant in SEARCH_VARIANTS:
                row = dict(snapshot_id=sid, variant=variant, collect_stats=True,
                           occurrences=len(snapshot["occurrences"]),
                           measured_repetitions=manifest["measured_repetitions"],
                           warmup_repetitions=1, status="complete",
                           feasibility=reference[0], exact_result_sha256=result_digest(reference),
                           **VARIANTS[variant], **structural[variant])
                row["dfs_time_ms"] = median(t[0] for t in timings[variant])
                row["probability_time_ms"] = median(t[1] for t in timings[variant])
                writer.writerow(row)
            handle.flush()
            progress[sid] = "complete"
            _write_manifest(out / "manifest.json", manifest)
            print(f"Replay [{index + 1}/{len(snapshots)}] verified {sid[:12]}", flush=True)


def run(args):
    out = args.out_dir
    if out.exists() and any(out.iterdir()):
        if args.phase == "all":
            raise ValueError("output directory is not empty; use a new directory")
        manifest = json.loads((out / "manifest.json").read_text())
        if manifest.get("pipeline") != "ablation" or manifest.get("schema_version") != 1:
            raise ValueError("not an ablation manifest")
        if manifest["phases"][args.phase] != "pending":
            raise ValueError("phase has already started; use a new run, do not overwrite")
        if any(getattr(args, name) is not None for name in (
            "games", "presets", "seed_start", "repetitions", "shuffle_seed",
            "opening_strategy", "include_outside", "first_click", "flood_fill")):
            raise ValueError("continuation uses saved settings; omit configuration/repetition overrides")
        for name, sha in manifest["source_sha256"].items():
            if file_digest(ROOT / name) != sha:
                raise ValueError("source changed since collection; restore the recorded snapshot")
    else:
        configs = build_configs(args.presets or ["beginner", "intermediate", "expert"], args.games,
                                args.opening_strategy or "center", bool(args.include_outside),
                                args.first_click or "OPENING", args.flood_fill or "BFS")
        manifest = _manifest([], datetime.now().astimezone().isoformat(), sys.argv)
        manifest.update(schema_version=1, pipeline="ablation", variants=VARIANTS,
                        configurations=configs, seed_start=args.seed_start or 0,
                        games_override=args.games, measured_repetitions=args.repetitions if args.repetitions is not None else 5,
                        shuffle_seed=args.shuffle_seed if args.shuffle_seed is not None else 0, collect_stats=True,
                        weighting="unique snapshots; occurrences recorded, not used as weights",
                        warmup_repetitions=1, timing="sequential; perf_counter_ns; median of repetitions",
                        status="incomplete", phases={p: "pending" for p in ("collect", "games", "replay")},
                        commands=[])
        save_source_provenance(out, manifest)
    phases = ("collect", "games", "replay") if args.phase == "all" else (args.phase,)
    manifest["commands"].append(sys.argv)
    try:
        for phase in phases:
            if phase == "replay" and manifest["phases"]["collect"] != "complete":
                raise ValueError("collect must complete before replay")
            manifest["phases"][phase] = "incomplete"
            _write_manifest(out / "manifest.json", manifest)
            {"collect": collect, "games": info_games, "replay": search_replay}[phase](out, manifest)
            manifest["phases"][phase] = "complete"
            manifest["status"] = "complete" if all(v == "complete" for v in manifest["phases"].values()) else "incomplete"
    except Exception as exc:
        manifest["failure"] = str(exc)
        raise
    finally:
        manifest["ended_at"] = datetime.now().astimezone().isoformat()
        files = [p for p in out.iterdir() if p.suffix in (".csv", ".jsonl")]
        manifest["data_sha256"] = {p.name: file_digest(p) for p in files}
        _write_manifest(out / "manifest.json", manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--phase", choices=("all", "collect", "games", "replay"), default="all")
    parser.add_argument("--presets", nargs="+", choices=("beginner", "intermediate", "expert"))
    parser.add_argument("--games", type=int)
    parser.add_argument("--seed-start", type=int)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--shuffle-seed", type=int)
    parser.add_argument("--opening-strategy", choices=("center", "corner"), default=None)
    parser.add_argument("--include-outside", action="store_true", default=None)
    parser.add_argument("--first-click", choices=("OPENING", "SAFE", "UNSAFE"), default=None)
    parser.add_argument("--flood-fill", choices=("BFS", "DFS"), default=None)
    args = parser.parse_args(argv)
    if (args.games is not None and args.games < 1) or (args.repetitions is not None and args.repetitions < 1):
        parser.error("games and repetitions must be positive")
    try:
        run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
