"""Shared ablation schema, snapshot encoding and exact replay."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, fields
from math import comb
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minesweeper.core.game import PlayerView, Status
from minesweeper.solver.constraint_solver import Constraint, ConstraintSolver
from minesweeper.solver.dfs_solver import DFSStats, DfsSolver

VARIANTS = {
    "baseline": dict(variable_order="degree", use_propagation=True, guess_tiebreak="info"),
    "no_degree": dict(variable_order="coordinate", use_propagation=True, guess_tiebreak="info"),
    "no_propagation": dict(variable_order="degree", use_propagation=False, guess_tiebreak="info"),
    "no_info": dict(variable_order="degree", use_propagation=True, guess_tiebreak="coordinate"),
}
SEARCH_VARIANTS = ("baseline", "no_degree", "no_propagation")
STATS_FIELDS = [f.name for f in fields(DFSStats)]
COUNTERS = [f for f in STATS_FIELDS if not f.endswith("_time_ms")]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode_constraints(constraints):
    return [{"cells": [list(c) for c in sorted(item.cells)], "mines": item.mines} for item in constraints]


def snapshot_input(view, constraints, config):
    return {
        "schema_version": 1, "config": config,
        "view": {"rows": view.rows, "cols": view.cols, "total_mines": view.total_mines,
                 "cells": view.cells, "flags": sorted(view.flags), "status": view.status.name},
        "constraints": encode_constraints(constraints),
    }


def restore_snapshot(snapshot):
    payload = snapshot["input"]
    if snapshot["snapshot_id"] != digest(payload) or payload["schema_version"] != 1:
        raise ValueError("snapshot hash/schema mismatch")
    v = payload["view"]
    view = PlayerView(v["rows"], v["cols"], v["total_mines"],
                      tuple(tuple(row) for row in v["cells"]),
                      frozenset(tuple(c) for c in v["flags"]), Status[v["status"]])
    if len(view.cells) != view.rows or any(len(row) != view.cols for row in view.cells):
        raise ValueError("invalid snapshot dimensions")
    if encode_constraints(ConstraintSolver._build_constraints(view)) != payload["constraints"]:
        raise ValueError("snapshot original constraints differ from PlayerView")
    if payload["config"]["rows"] != view.rows or payload["config"]["cols"] != view.cols or payload["config"]["mines"] != view.total_mines:
        raise ValueError("snapshot configuration mismatch")
    return view, tuple(Constraint(frozenset(tuple(c) for c in item["cells"]), item["mines"]) for item in payload["constraints"])


def replay(snapshot, variant):
    """Enumerate exact sets and Fractions; do not advance a game."""
    view, constraints = restore_snapshot(snapshot)
    components = DfsSolver._components(constraints)
    totals = DFSStats()
    solution_sets, solution_maps = [], []
    options = VARIANTS[variant]
    for component in components:
        stats = DFSStats()
        solutions = DfsSolver._solve_component(
            component, variable_order=options["variable_order"],
            use_propagation=options["use_propagation"], stats=stats,
        )
        stats.components_count = 1
        stats.largest_component_variables = len(component.cells)
        totals.add(stats)
        solution_sets.append(frozenset(tuple(s[c] for c in component.cells) for s in solutions))
        solution_maps.append(solutions)
    if any(not solutions for solutions in solution_maps):
        return ("component_infeasible", tuple(solution_sets), (), ()), totals
    frontier = {c for component in components for c in component.cells}
    outside = set(view.hidden_cells()) - frontier
    mines_left = view.total_mines - len(view.flags)
    start = perf_counter_ns()
    probabilities, information = DfsSolver._global_probabilities(
        components, solution_maps, outside, mines_left,
        include_outside=snapshot["input"]["config"]["include_outside"],
    )
    totals.probability_time_ms = (perf_counter_ns() - start) / 1_000_000
    # Empty probabilities can also mean a feasible board with no frontier.
    distribution = {0: 1}
    for solutions in solution_maps:
        distribution = DfsSolver._convolve(distribution, DfsSolver._mine_distribution(solutions))
    weight = sum(count * comb(len(outside), mines_left - mines)
                 for mines, count in distribution.items() if 0 <= mines_left - mines <= len(outside))
    status = "feasible" if weight else "global_infeasible"
    exact = (status, tuple(solution_sets), tuple(sorted(probabilities.items())), tuple(sorted(information.items())))
    return exact, totals


def result_digest(exact):
    status, solutions, probabilities, info = exact
    return digest({"status": status, "solutions": [sorted(s) for s in solutions],
                   "probabilities": [(c, p.numerator, p.denominator) for c, p in probabilities],
                   "information": info})


def read_jsonl(path):
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path, rows):
    temporary = path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(canonical(row) + "\n")
    temporary.replace(path)
