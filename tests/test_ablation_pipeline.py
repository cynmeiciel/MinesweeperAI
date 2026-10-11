"""Real smoke pipeline plus negative data/provenance checks."""
import csv
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "docs/report/scripts"
sys.path.insert(0, str(SCRIPTS))
import ablation_common as common
import run_ablation as runner
import summarize_ablation as summary


@pytest.fixture
def run_dir(tmp_path):
    out = tmp_path / "run"
    runner.main(["--presets", "beginner", "--games", "10", "--out-dir", str(out)])
    return out


def test_real_dfs_smoke_has_verified_replay_and_paired_games(run_dir):
    manifest, configs, games, triples, excluded = summary.validate(run_dir)
    assert manifest["status"] == "complete"
    assert len(games) == 20 and len(triples) >= 1 and excluded == 0
    assert manifest["snapshot_occurrences"] >= manifest["snapshots_unique"] >= 1
    assert all(r["measured_repetitions"] == "5" for t in triples for r in t.values())
    rows = summary.summarize(run_dir)
    assert len(rows) == 6
    assert (run_dir / "ablation_summary.csv").exists()
    assert (run_dir / "ablation_tables.md").exists()
    with pytest.raises(SystemExit):
        runner.main(["--presets", "beginner", "--games", "10", "--out-dir", str(run_dir)])


def test_phased_pipeline_uses_saved_settings(tmp_path):
    out = tmp_path / "phases"
    runner.main(["--phase", "collect", "--presets", "beginner", "--games", "10", "--out-dir", str(out)])
    with pytest.raises(ValueError, match="paired games incomplete"):
        summary.validate(out)
    runner.main(["--phase", "replay", "--out-dir", str(out)])
    runner.main(["--phase", "games", "--out-dir", str(out)])
    summary.validate(out)
    with pytest.raises(SystemExit):
        runner.main(["--phase", "replay", "--out-dir", str(out)])


def test_snapshot_contains_only_observable_state_and_hash_covers_inputs(run_dir):
    snapshot = common.read_jsonl(run_dir / "frontiers.jsonl")[0]
    view, constraints = common.restore_snapshot(snapshot)
    assert not any(k in snapshot["input"]["view"] for k in ("mine_positions", "board", "ground_truth"))
    assert len(constraints) > 0
    snapshot["input"]["view"]["total_mines"] += 1
    with pytest.raises(ValueError, match="hash"):
        common.restore_snapshot(snapshot)


@pytest.mark.parametrize("file,field,value", [
    ("ablation_games.csv", "guess_tiebreak", "info"),
    ("ablation_games.csv", "seed", "999"),
    ("ablation_games.csv", "board_fingerprint", "bad"),
    ("ablation_games.csv", "execution_error", "solver exception"),
    ("ablation_frontiers.csv", "nodes_visited", "-1"),
    ("ablation_frontiers.csv", "dfs_time_ms", "nan"),
    ("ablation_frontiers.csv", "exact_result_sha256", "mismatch"),
])
def test_corrupted_rows_rejected_even_if_file_hash_is_recomputed(run_dir, file, field, value):
    path = run_dir / file
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    index = next(i for i, row in enumerate(rows) if row["variant"] == "no_info") if file == "ablation_games.csv" else 0
    rows[index][field] = value
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    manifest["data_sha256"][file] = common.file_digest(path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        summary.validate(run_dir)


def test_incomplete_replay_is_excluded_as_a_matched_triple(run_dir):
    manifest = json.loads((run_dir / "manifest.json").read_text())
    path = run_dir / "ablation_frontiers.csv"
    path.write_text(",".join(runner.FRONTIER_FIELDS) + "\n")
    manifest["data_sha256"][path.name] = common.file_digest(path)
    manifest["status"] = "incomplete"
    manifest["phases"]["replay"] = "incomplete"
    manifest["snapshot_status"] = {sid: "incomplete" for sid in manifest["snapshot_status"]}
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="replay incomplete"):
        summary.validate(run_dir)
    _, _, _, triples, excluded = summary.validate(run_dir, allow_incomplete_replay=True)
    assert not triples and excluded == manifest["snapshots_unique"]
    rows = summary.summarize(run_dir, allow_incomplete_replay=True)
    assert all(r["excluded_snapshots"] == excluded for r in rows if r["section"] == "replay")


def test_exact_mcnemar_known_cases():
    assert summary.mcnemar_exact(0, 0) == 1
    assert summary.mcnemar_exact(2, 0) == .5
    assert summary.mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert summary.mcnemar_exact(4, 6) == summary.mcnemar_exact(6, 4)


def test_default_main_sample_sizes():
    configs = runner.build_configs(["beginner", "intermediate", "expert"], None)
    assert [c["games"] for c in configs] == [1000, 1000, 300]


def test_duplicate_presets_rejected():
    with pytest.raises(ValueError, match="duplicate presets"):
        runner.build_configs(["beginner", "beginner"], 10)
