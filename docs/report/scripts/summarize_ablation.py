"""Validate ablation provenance/data and generate descriptive report tables."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import zipfile
from collections import defaultdict
from math import comb
from pathlib import Path
from statistics import mean, median

from ablation_common import VARIANTS, SEARCH_VARIANTS, STATS_FIELDS, COUNTERS, file_digest, restore_snapshot, read_jsonl
from run_ablation import GAME_FIELDS, FRONTIER_FIELDS
from summarize_results import percentile
from minesweeper.analysis.batch import wilson_interval

FIELDS = ["section", "config_id", "preset", "variant", "games", "wins", "losses", "stalled",
          "win_rate", "ci_low", "ci_high", "mean_moves", "mean_guesses", "mean_time_ms",
          "b", "c", "mcnemar_exact_p", "win_difference_pp",
          "snapshots", "infeasible_snapshots", "excluded_snapshots", "matched_snapshots",
          "mean_nodes", "median_nodes", "p95_nodes", "mean_pruned_nodes", "mean_forced_assignments",
          "median_dfs_time_ms", "p95_dfs_time_ms", "total_node_ratio", "total_dfs_time_ratio"]


def mcnemar_exact(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / (1 << n)) if n else 1.0


def read_csv(path, expected_fields):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError(f"CSV schema mismatch: {path.name}")
        rows = list(reader)
    if any(set(r) != set(expected_fields) or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f"malformed CSV row: {path.name}")
    return rows


def check_stats(row):
    for key in COUNTERS:
        if int(row[key]) < 0:
            raise ValueError("negative structural counter")
    for key in ("dfs_time_ms", "probability_time_ms"):
        if not math.isfinite(float(row[key])) or float(row[key]) < 0:
            raise ValueError("invalid timing")
    if row["use_propagation"] == "False" and (int(row["forced_assignments"]) or int(row["propagation_passes"])):
        raise ValueError("no_propagation counters include automatic assignments")
    if int(row["max_depth"]) > int(row["largest_component_variables"]):
        raise ValueError("invalid DFS depth")


def check_variant(row):
    if row["variant"] not in VARIANTS or row["collect_stats"] != "True":
        raise ValueError("unknown variant/stats mode")
    for key, value in VARIANTS[row["variant"]].items():
        if row[key] != str(value):
            raise ValueError("row does not match its ablation variant")
    check_stats(row)


def validate(out, allow_incomplete_replay=False):
    manifest = json.loads((out / "manifest.json").read_text())
    if manifest.get("schema_version") != 1 or manifest.get("pipeline") != "ablation":
        raise ValueError("not a supported ablation manifest")
    if manifest.get("variants") != VARIANTS or not manifest.get("collect_stats"):
        raise ValueError("manifest variant mismatch")
    if manifest.get("failure") or manifest.get("replay_error"):
        raise ValueError("run has an unresolved execution/equality failure")
    phases = manifest["phases"]
    if phases["collect"] != "complete" or phases["games"] != "complete":
        raise ValueError("collection or paired games incomplete")
    if phases["replay"] != "complete" and not allow_incomplete_replay:
        raise ValueError("replay incomplete; no official tables generated")
    if manifest["warmup_repetitions"] != 1 or manifest["measured_repetitions"] < 1:
        raise ValueError("invalid replay methodology")
    if manifest["weighting"] != "unique snapshots; occurrences recorded, not used as weights":
        raise ValueError("unknown snapshot weighting")
    for name in ("frontiers.jsonl", "collection_games.csv", "ablation_games.csv", "ablation_frontiers.csv"):
        if file_digest(out / name) != manifest["data_sha256"][name]:
            raise ValueError(f"checksum mismatch: {name}")
    with zipfile.ZipFile(out / "source_snapshot.zip") as archive:
        import hashlib
        for name, sha in manifest["source_sha256"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != sha:
                raise ValueError("source snapshot checksum mismatch")
    configs = {c["config_id"]: c for c in manifest["configurations"]}
    if len(configs) != len(manifest["configurations"]) or not configs:
        raise ValueError("duplicate or empty configurations")
    games = read_csv(out / "ablation_games.csv", GAME_FIELDS)
    collection = read_csv(out / "collection_games.csv", GAME_FIELDS)
    start = manifest["seed_start"]
    def validate_games(rows, variants):
        actual = {}
        expected = {(cid, seed, v) for cid, cfg in configs.items()
                    for seed in range(start, start + cfg["games"]) for v in variants}
        for row in rows:
            check_variant(row)
            key = row["config_id"], int(row["seed"]), row["variant"]
            if key not in expected or key in actual:
                raise ValueError("missing/duplicate/unexpected game key")
            cfg = configs[row["config_id"]]
            for field in ("rows", "cols", "mines", "first_click", "chord", "flood_fill", "opening_strategy", "include_outside"):
                if row[field] != str(cfg[field]):
                    raise ValueError("game configuration mismatch")
            if row["solver"] != "lv3" or row["result"] not in ("won", "lost", "stalled") or row["execution_error"]:
                raise ValueError("invalid game result or execution failure")
            duration = float(row["time_ms"])
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("invalid game duration")
            safe = int(row["rows"]) * int(row["cols"]) - int(row["mines"])
            revealed = int(row["cells_revealed"])
            moves, guesses = int(row["moves"]), int(row["guesses"])
            if not 0 <= revealed <= safe or int(row["cells_remaining"]) != safe - revealed or not 0 <= guesses <= moves:
                raise ValueError("invalid game counters")
            if row["result"] == "won" and revealed != safe:
                raise ValueError("won with unrevealed safe cells")
            if not row["board_fingerprint"] or len(row["board_fingerprint"]) != 64:
                raise ValueError("missing board fingerprint")
            actual[key] = row
        if set(actual) != expected:
            raise ValueError("incomplete seed/configuration/variant matrix")
        return actual
    game_map = validate_games(games, ("baseline", "no_info"))
    collection_map = validate_games(collection, ("baseline",))
    if len(games) != manifest["info_games_completed"] or len(collection) != manifest["collection_games_completed"]:
        raise ValueError("manifest completed game counts differ")
    for (cid, seed, variant), row in game_map.items():
        other = game_map[cid, seed, "baseline"]
        if row["board_fingerprint"] != other["board_fingerprint"]:
            raise ValueError("paired initial board mismatch")
        if variant == "baseline":
            reference = collection_map[cid, seed, "baseline"]
            for key in ("result", "moves", "guesses", "cells_revealed", "board_fingerprint", *COUNTERS):
                if row[key] != reference[key]:
                    raise ValueError("baseline collection/game replay differs")
    snapshots = read_jsonl(out / "frontiers.jsonl")
    seen, occurrences = set(), set()
    for snapshot in snapshots:
        restore_snapshot(snapshot)
        sid = snapshot["snapshot_id"]
        if sid in seen or not snapshot["occurrences"]:
            raise ValueError("duplicate/empty snapshot")
        seen.add(sid)
        cid = snapshot["input"]["config"]["config_id"]
        if cid not in configs:
            raise ValueError("snapshot configuration unknown")
        expected_config = {k: v for k, v in configs[cid].items() if k not in ("games", "preset")}
        if snapshot["input"]["config"] != expected_config:
            raise ValueError("snapshot inference settings mismatch")
        for source in snapshot["occurrences"]:
            key = source["config_id"], source["seed"], source["step"]
            if key in occurrences or key[0] != cid or not start <= key[1] < start + configs[cid]["games"] or key[2] < 0:
                raise ValueError("invalid/duplicate snapshot occurrence")
            occurrences.add(key)
    if len(seen) != manifest["snapshots_unique"] or len(occurrences) != manifest["snapshot_occurrences"]:
        raise ValueError("snapshot/occurrence count mismatch")
    replay_rows = read_csv(out / "ablation_frontiers.csv", FRONTIER_FIELDS)
    by_snapshot = defaultdict(dict)
    for row in replay_rows:
        check_variant(row)
        sid, variant = row["snapshot_id"], row["variant"]
        if sid not in seen or variant not in SEARCH_VARIANTS or variant in by_snapshot[sid]:
            raise ValueError("duplicate or unexpected replay row")
        if row["status"] != "complete" or int(row["measured_repetitions"]) != manifest["measured_repetitions"] or int(row["warmup_repetitions"]) != 1:
            raise ValueError("incomplete replay measurements")
        if int(row["nodes_visited"]) != 2 * int(row["branch_points"]) + int(row["components_count"]):
            raise ValueError("invalid complete binary-search node counts")
        if int(row["nodes_visited"]) != sum(int(row[k]) for k in ("branch_points", "pruned_nodes", "solutions_count")):
            raise ValueError("invalid node classifications")
        if row["feasibility"] not in ("feasible", "component_infeasible", "global_infeasible"):
            raise ValueError("unknown replay feasibility")
        if len(row["exact_result_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in row["exact_result_sha256"]):
            raise ValueError("invalid exact-result checksum")
        by_snapshot[sid][variant] = row
    complete = []
    for snapshot in snapshots:
        sid = snapshot["snapshot_id"]
        rows = by_snapshot.get(sid, {})
        if set(rows) != set(SEARCH_VARIANTS):
            if allow_incomplete_replay and manifest["snapshot_status"].get(sid) != "complete":
                continue
            raise ValueError("incomplete matched replay triple")
        if manifest["snapshot_status"].get(sid) != "complete":
            raise ValueError("CSV and manifest replay status differ")
        if len({r["exact_result_sha256"] for r in rows.values()}) != 1 or len({r["feasibility"] for r in rows.values()}) != 1:
            raise ValueError("solution/probability comparison failed")
        if any(int(r["occurrences"]) != len(snapshot["occurrences"]) for r in rows.values()):
            raise ValueError("snapshot weighting mismatch")
        complete.append(rows)
    if phases["replay"] == "complete" and len(complete) != len(snapshots):
        raise ValueError("complete replay manifest omits snapshots")
    return manifest, configs, game_map, complete, len(snapshots) - len(complete)


def summarize(out, allow_incomplete_replay=False):
    manifest, configs, games, triples, excluded = validate(out, allow_incomplete_replay)
    feasible = [t for t in triples if t["baseline"]["feasibility"] == "feasible"]
    output = []
    baseline_nodes = sum(int(t["baseline"]["nodes_visited"]) for t in feasible)
    baseline_time = sum(float(t["baseline"]["dfs_time_ms"]) for t in feasible)
    for variant in SEARCH_VARIANTS:
        rs = [t[variant] for t in feasible]
        nodes, times = [int(r["nodes_visited"]) for r in rs], [float(r["dfs_time_ms"]) for r in rs]
        output.append(dict(section="replay", variant=variant, snapshots=len(rs),
                           infeasible_snapshots=len(triples) - len(feasible), excluded_snapshots=excluded,
                           matched_snapshots=len(triples), mean_nodes=mean(nodes) if nodes else "",
                           median_nodes=median(nodes) if nodes else "", p95_nodes=percentile(nodes, .95) if nodes else "",
                           mean_pruned_nodes=mean(int(r["pruned_nodes"]) for r in rs) if rs else "",
                           mean_forced_assignments=mean(int(r["forced_assignments"]) for r in rs) if rs else "",
                           median_dfs_time_ms=median(times) if times else "", p95_dfs_time_ms=percentile(times, .95) if times else "",
                           total_node_ratio=sum(nodes) / baseline_nodes if baseline_nodes else "",
                           total_dfs_time_ratio=sum(times) / baseline_time if baseline_time else ""))
    for cid, cfg in configs.items():
        pairs = {}
        for variant in ("baseline", "no_info"):
            rs = [games[cid, seed, variant] for seed in range(manifest["seed_start"], manifest["seed_start"] + cfg["games"])]
            pairs[variant] = rs
            wins = sum(r["result"] == "won" for r in rs)
            lo, hi = wilson_interval(wins, len(rs))
            output.append(dict(section="info", config_id=cid, preset=cfg["preset"], variant=variant,
                               games=len(rs), wins=wins, losses=sum(r["result"] == "lost" for r in rs),
                               stalled=sum(r["result"] == "stalled" for r in rs), win_rate=wins / len(rs),
                               ci_low=lo, ci_high=hi, mean_moves=mean(int(r["moves"]) for r in rs),
                               mean_guesses=mean(int(r["guesses"]) for r in rs),
                               mean_time_ms=mean(float(r["time_ms"]) for r in rs)))
        b = sum(a["result"] == "won" and z["result"] != "won" for a, z in zip(pairs["baseline"], pairs["no_info"]))
        c = sum(a["result"] != "won" and z["result"] == "won" for a, z in zip(pairs["baseline"], pairs["no_info"]))
        output.append(dict(section="info_pair", config_id=cid, preset=cfg["preset"], games=cfg["games"],
                           b=b, c=c, mcnemar_exact_p=mcnemar_exact(b, c),
                           win_difference_pp=100 * (c - b) / cfg["games"]))
    with (out / "ablation_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        writer.writerows(output)
    lines = ["# Ablation results", "",
             f"Sample override: {manifest['games_override']}; unique-state weighting; excluded snapshots: {excluded}.",
             "Smoke samples validate the pipeline, not population-level heuristic effects.",
             "no_propagation disables automatic assignments but RETAINS feasibility pruning.",
             "Times are ms: warm-up once, five measured repetitions by default; median per snapshot.",
             "P95 uses linear interpolation at (n-1)*0.95. Ratios are ratios of TOTALS on identical feasible snapshots.",
             "Infeasible states are counted separately, never treated as ordinary probabilities.",
             "INFO game node totals cannot establish Degree/propagation effects.",
             "McNemar exact: two-sided binomial on b+c at p0=0.5, unadjusted; no_info minus baseline in percentage points.",
             "Wilson intervals describe each rate, not the paired difference; non-significance does not establish equivalence.",
             "Stalled counts require diagnosis before strategic conclusions.", ""]
    for section in ("replay", "info", "info_pair"):
        rows = [r for r in output if r["section"] == section]
        columns = [key for key in FIELDS if key != "section" and any(key in r for r in rows)]
        lines += [f"## {section}", "", "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
        lines += ["| " + " | ".join(str(r.get(k, "")) for k in columns) + " |" for r in rows]
        lines.append("")
    (out / "ablation_tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--allow-incomplete-replay", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = summarize(args.data_dir, args.allow_incomplete_replay)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(f"wrote {len(rows)} ablation summary rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
