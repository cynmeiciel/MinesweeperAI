"""Report pipeline checks: sample reuse, provenance and corrupt-input rejection."""
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "docs/report/scripts"
sys.path.insert(0, str(SCRIPTS))
import run_experiments as runner
import summarize_results as summary
import plot_results as plots


def test_shared_configuration_preserves_density_sample_size():
    experiments = runner.build_experiments("all", None)
    assert len(experiments) == 43
    assert sum(e.games for e in experiments) == 30000
    shared = next(e for e in experiments if e.solver == "lv3" and (e.config.rows, e.config.cols, e.config.mines) == (9, 9, 10) and e.config.first_click.name == "OPENING" and e.config.flood_fill.name == "BFS" and e.opening_strategy == "center" and not e.include_outside)
    assert shared.games == 1000
    assert shared.group_games["density"] == 500
    assert shared.group_games["main"] == 1000


@pytest.fixture
def run_dir(tmp_path):
    runner.run(tmp_path / "data", "first-click", 7, 3)
    return tmp_path / "data"


def test_verified_data_and_non_overwrite(run_dir):
    manifest, raw = summary.load_data(run_dir)
    rows = summary.summarize(manifest, raw)
    assert len(rows) == 3
    assert manifest["games_override"] == 3
    assert all(row["wins"] + row["losses"] + row["stalled"] == 3 for row in rows)
    with pytest.raises(SystemExit, match="not empty"):
        runner.run(run_dir, "first-click", 7, 3)


@pytest.mark.parametrize("field,value", [("solver", "lv1"), ("opening_strategy", "corner"), ("seed", "999"), ("result", "unknown"), ("time_ms", "nan"), ("cells_revealed", "999")])
def test_corrupt_csv_rejected_even_with_recomputed_hash(run_dir, field, value):
    manifest = json.loads((run_dir / "manifest.json").read_text())
    experiment = manifest["experiments"][0]
    path = run_dir / experiment["csv_path"]
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    rows[0][field] = value
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest["csv_sha256"][experiment["experiment_id"]] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        summary.load_data(run_dir)


def test_incomplete_run_rejected(run_dir):
    manifest = json.loads((run_dir / "manifest.json").read_text())
    manifest["experiments"][0]["status"] = "running"
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="incomplete"):
        summary.load_data(run_dir)


def test_density_uses_prefix_not_full_baseline(run_dir):
    manifest, raw = summary.load_data(run_dir)
    item = manifest["experiments"][0]
    item["groups"] = ["main", "density"]
    item["group_games"] = {"main": 3, "density": 2}
    rows = summary.group_summaries({"experiments": [item]}, raw)
    assert [(r["groups"], r["games"]) for r in rows] == [("main", 3), ("density", 2)]


def test_plot_refuses_missing_solver_instead_of_zero(tmp_path):
    row = dict(groups="main", rows="5", cols="5", solver="lv3", games="5", win_rate="1", ci_low="0.5", ci_high="1")
    with pytest.raises(ValueError, match="incomplete main"):
        plots.plot_solver([row], tmp_path)


def test_plot_refuses_missing_density_point(tmp_path):
    with pytest.raises(ValueError, match="incomplete density"):
        plots.plot_density([dict(groups="density", solver="lv3", mines="10")], tmp_path)
