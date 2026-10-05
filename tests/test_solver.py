import random

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import CellState, Game, Status
import pytest

from minesweeper.solver import ConstraintSolver, SOLVERS, RuleBasedSolver, SolverStuck
from minesweeper.solver.base import Move, apply_move
from minesweeper.solver.random_solver import RandomSolver


def strip_game() -> Game:  # 0 0 0 0 1 *
    cfg = GameConfig(1, 6, 1, first_click=FirstClick.UNSAFE)
    return Game(cfg, board=Board.from_mines(1, 6, [(0, 5)]))


def test_registry():
    assert SOLVERS["random"] is RandomSolver
    assert RandomSolver.name == "random"
    assert SOLVERS["lv1"] is RuleBasedSolver
    assert RuleBasedSolver.name == "lv1"
    assert SOLVERS["lv2"] is ConstraintSolver
    assert ConstraintSolver.name == "lv2"


def test_constraint_solver_flags_mine_from_subset_difference():
    board = Board.from_mines(3, 3, [(0, 0), (2, 0), (2, 1), (2, 2)])
    game = Game(
        GameConfig(3, 3, 4, first_click=FirstClick.UNSAFE), board=board
    )
    game.reveal(0, 1)
    game.reveal(1, 1)

    move = ConstraintSolver(random.Random(0)).next_move(game.view())

    assert move.action == "flag"
    assert move.cell == (2, 0)
    assert move.certain


def test_constraint_solver_opens_safe_cell_from_zero_difference():
    board = Board.from_mines(3, 3, [(0, 0)])
    game = Game(
        GameConfig(3, 3, 1, first_click=FirstClick.UNSAFE), board=board
    )
    game.reveal(0, 1)
    game.reveal(1, 1)

    move = ConstraintSolver(random.Random(0)).next_move(game.view())

    assert move.action == "reveal"
    assert move.cell == (2, 0)
    assert move.certain


def test_constraint_solver_opens_first_cell_instead_of_stuck():
    move = ConstraintSolver(random.Random(0)).next_move(strip_game().view())

    assert move.action == "reveal"
    assert move.cell == (0, 0)
    assert move.certain


def test_rule_based_solver_flags_all_determined_mines():
    g = Game(
        GameConfig(1, 4, 2, first_click=FirstClick.UNSAFE),
        board=Board.from_mines(1, 4, [(0, 0), (0, 2)]),
    )
    g.reveal(0, 1)
    solver = RuleBasedSolver(random.Random(0))

    first = solver.next_move(g.view())
    assert first.action == "flag"
    assert first.cell == (0, 0)
    assert first.reason == "[Rule 1] (0, 1) -> FLAG (0, 0)"
    assert apply_move(g, first)

    second = solver.next_move(g.view())
    assert second.action == "flag"
    assert second.cell == (0, 2)
    assert apply_move(g, second)


def test_rule_based_solver_opens_determined_safe_cell():
    g = strip_game()
    g.reveal(0, 4)
    g.toggle_flag(0, 5)
    move = RuleBasedSolver(random.Random(0)).next_move(g.view())

    assert move.action == "reveal"
    assert move.cell == (0, 3)
    assert move.reason == "[Rule 2] (0, 4) -> REVEAL (0, 3)"


def test_rule_based_solver_reports_stuck_without_deterministic_move():
    game = strip_game()
    game.reveal(0, 4)
    with pytest.raises(SolverStuck, match="AI -> STUCK"):
        RuleBasedSolver(random.Random(0)).next_move(game.view())


def test_rule_based_solver_opens_first_cell_instead_of_stuck():
    move = RuleBasedSolver(random.Random(0)).next_move(strip_game().view())

    assert move.action == "reveal"
    assert move.cell == (0, 0)
    assert move.reason == "[Opening] REVEAL (0, 0)"


def test_random_solver_only_picks_hidden_unflagged():
    g = strip_game()
    g.reveal(0, 4)
    g.toggle_flag(0, 0)
    solver = RandomSolver(random.Random(0))
    picks = {solver.next_move(g.view()).cell for _ in range(200)}
    assert picks == {(0, 1), (0, 2), (0, 3), (0, 5)}


def test_random_solver_move_shape():
    move = RandomSolver(random.Random(0)).next_move(strip_game().view())
    assert move.action == "reveal"
    assert move.certain is False
    assert move.reason == "random pick"


def test_random_solver_deterministic_with_seed():
    view = Game(GameConfig(9, 9, 10, seed=3)).view()
    a = [RandomSolver(random.Random(5)).next_move(view).cell for _ in range(3)]
    b = [RandomSolver(random.Random(5)).next_move(view).cell for _ in range(3)]
    assert a == b


def test_apply_move_reveal_and_flag():
    g = strip_game()
    assert apply_move(g, Move("reveal", (0, 4), "", True))
    assert g.state(0, 4) is CellState.REVEALED
    assert apply_move(g, Move("flag", (0, 5), "", True))
    assert g.state(0, 5) is CellState.FLAGGED


def test_apply_move_rejects_illegal():
    g = strip_game()
    g.reveal(0, 4)
    assert not apply_move(g, Move("reveal", (0, 4), "", True))   # already revealed
    assert not apply_move(g, Move("flag", (0, 4), "", True))     # revealed
    assert not apply_move(g, Move("reveal", (3, 3), "", True))   # out of bounds
    assert not apply_move(g, Move("dance", (0, 0), "", True))    # type: ignore[arg-type]
    g.toggle_flag(0, 0)
    assert not apply_move(g, Move("reveal", (0, 0), "", True))   # flagged


def test_apply_move_after_game_over():
    g = strip_game()
    g.reveal(0, 5)
    assert g.status is Status.LOST
    assert not apply_move(g, Move("reveal", (0, 0), "", True))
