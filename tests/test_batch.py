import csv
import io
import random

import pytest

from minesweeper.analysis.__main__ import main
from minesweeper.analysis.batch import (
    CSV_FIELDS,
    format_summary,
    run_batch,
    run_game,
    summarize,
    wilson_interval,
    write_csv,
    write_failure_log,
)
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.solver.base import Move
from minesweeper.solver.debug import Debug
from minesweeper.solver.random_solver import RandomSolver


def test_run_game_record_fields():
    rec = run_game(GameConfig(9, 9, 10, seed=3), RandomSolver)
    assert rec.seed == 3 and (rec.rows, rec.cols, rec.mines) == (9, 9, 10)
    assert rec.first_click == "OPENING" and rec.flood_fill == "BFS" and rec.chord is True
    assert rec.solver == "random"
    assert rec.result in {"won", "lost"}
    assert rec.moves >= 1 and rec.guesses == rec.moves
    assert rec.cells_revealed >= 1
    assert rec.time_ms >= 0


def test_run_game_requires_seed():
    with pytest.raises(ValueError, match="seed"):
        run_game(GameConfig(9, 9, 10), RandomSolver)


def test_batch_is_reproducible():
    cfgs = [GameConfig(9, 9, 10)]
    a = run_batch(cfgs, "random", games=20, base_seed=100)
    b = run_batch(cfgs, "random", games=20, base_seed=100)
    strip = lambda recs: [r.__dict__ | {"time_ms": 0} for r in recs]
    assert strip(a) == strip(b)
    assert [r.seed for r in a] == list(range(100, 120))


def test_batch_cartesian_product():
    recs = run_batch([GameConfig(5, 5, 3), GameConfig(9, 9, 10)], "random", 4, 0)
    assert len(recs) == 8


class StuckSolver:
    name = "stuck"

    def __init__(self, rng: random.Random) -> None:
        pass

    def next_move(self, view):
        return Move("flag", (0, 0), "toggle forever", certain=True)


class IllegalSolver(StuckSolver):
    name = "illegal"

    def next_move(self, view):
        return Move("reveal", (99, 99), "off the board", certain=True)


class CrashingSolver(StuckSolver):
    name = "crash"

    def next_move(self, view):
        raise RuntimeError("boom")


@pytest.mark.parametrize("solver_cls", [StuckSolver, IllegalSolver, CrashingSolver])
def test_misbehaving_solvers_stall(solver_cls):
    rec = run_game(GameConfig(5, 5, 3, seed=1), solver_cls)
    assert rec.result == "stalled"
    assert rec.moves <= 5 * 5 * 2


def test_wilson_interval_known_values():
    assert wilson_interval(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert wilson_interval(0, 10) == pytest.approx((0.0, 0.2775), abs=1e-4)
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_write_csv_header_and_rows():
    recs = run_batch([GameConfig(5, 5, 3)], "random", 3, 0)
    buf = io.StringIO()
    write_csv(recs, buf)
    rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
    assert list(rows[0]) == CSV_FIELDS
    assert len(rows) == 3


def test_write_game_log_includes_seed_and_remaining_counts(tmp_path):
    records = [
        run_game(GameConfig(5, 5, 3, seed=0), StuckSolver),
        run_game(GameConfig(5, 5, 3, seed=1), RandomSolver),
    ]
    path = tmp_path / "failures.log"
    with path.open("w", encoding="utf-8") as file:
        write_failure_log(records, file)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "seed,result,solver,mines_remaining,cells_remaining,moves,guesses"
    assert lines[1].startswith("0,stalled,stuck,")
    assert lines[2].startswith("1,lost,random,")


def test_summarize_groups_by_config():
    recs = run_batch([GameConfig(5, 5, 3), GameConfig(9, 9, 10)], "random", 10, 0)
    summaries = summarize(recs)
    assert len(summaries) == 2
    s = summaries[0]
    assert s.games == 10
    assert s.wins == sum(r.result == "won" for r in recs[:10])
    assert s.ci_low <= s.win_rate <= s.ci_high
    text = format_summary(summaries)
    assert "5x5" in text and "9x9" in text


def test_main_writes_csv(tmp_path, capsys):
    out = tmp_path / "r.csv"
    code = main(["--preset", "tiny", "--games", "5", "--seed", "0", "--out", str(out)])
    assert code == 0
    assert len(out.read_text().splitlines()) == 6
    assert "win rate" in capsys.readouterr().out.lower()


def test_main_invalid_config_exits_2(capsys):  # Review Focus 4
    with pytest.raises(SystemExit) as exc:
        main(["--preset", "tiny", "--density", "0.9", "--games", "1"])
    assert exc.value.code == 2
    assert "too many mines" in capsys.readouterr().err


def test_main_rejects_zero_games(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--games", "0"])
    assert exc.value.code == 2


def test_solver_rng_independent_of_board_rng():
    # Regression: seeding the solver like the board made its first random pick
    # replay the first mine position (100% first-move loss under UNSAFE).
    recs = run_batch(
        [GameConfig(9, 9, 10, first_click=FirstClick.UNSAFE)], "random", games=300, base_seed=0
    )
    first_move_losses = sum(r.result == "lost" and r.moves == 1 for r in recs) / len(recs)
    assert first_move_losses < 0.3  # expected ~10/81 = 12%


def test_main_bad_out_path_fails_before_running(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--games", "1", "--out", str(tmp_path / "missing" / "r.csv")])
    assert exc.value.code == 2
    assert "cannot write" in capsys.readouterr().err


class NoisyDebugSolver(RandomSolver):
    """Random solver that attaches invalid overlay data to every move."""

    name = "noisy"

    def next_move(self, view):
        move = super().next_move(view)
        return Move(
            move.action, move.cell, move.reason, move.certain,
            debug=Debug(probabilities={(99, 99): 5.0}, labels={move.cell: ""}),
        )


def test_batch_ignores_debug_even_when_invalid():
    cfg = GameConfig(9, 9, 10, seed=11)
    keep = lambda r: {k: v for k, v in r.__dict__.items() if k not in ("solver", "time_ms")}
    assert keep(run_game(cfg, RandomSolver)) == keep(run_game(cfg, NoisyDebugSolver))
