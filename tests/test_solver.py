import random
from fractions import Fraction

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import CellState, Game, PlayerView, Status
import pytest

from minesweeper.solver import ConstraintSolver, DfsSolver, SOLVERS, RuleBasedSolver, SolverStuck
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
    assert SOLVERS["lv3"] is DfsSolver
    assert DfsSolver.name == "lv3"


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
    assert move.cell == (0, 2)
    assert move.certain


def test_dfs_solver_uses_probability_when_no_certain_move_exists():
    view = PlayerView(
        rows=1,
        cols=3,
        total_mines=1,
        cells=((None, 1, None),),
        flags=frozenset(),
        status=Status.PLAYING,
    )

    move = DfsSolver(random.Random(0)).next_move(view)

    assert move.action == "reveal"
    assert move.cell == (0, 0)
    assert not move.certain
    assert "P(MINE)=1/2" in move.reason
    assert "MINES_LEFT=1" in move.reason


def test_dfs_solver_checks_all_frontier_components_before_guessing():
    move = DfsSolver._choose_move(
        {(0, 0): Fraction(1, 2), (1, 0): Fraction(0)},
        {(0, 0): 2, (1, 0): 1},
    )

    assert move.action == "reveal"
    assert move.cell == (1, 0)
    assert move.certain


def test_dfs_solver_opens_lowest_mine_probability_when_no_certain_move_exists():
    move = DfsSolver._choose_move(
        {(0, 0): Fraction(2, 3), (0, 1): Fraction(1, 3)},
        {(0, 0): 1, (0, 1): 1},
        mines_left=1,
    )

    assert move.action == "reveal"
    assert move.cell == (0, 1)
    assert not move.certain
    assert "P(MINE)=1/3" in move.reason


def test_dfs_solver_finishes_when_no_frontier_remains():
    view = PlayerView(
        rows=1,
        cols=4,
        total_mines=2,
        cells=((None, 2, None, None),),
        flags=frozenset({(0, 0), (0, 2)}),
        status=Status.PLAYING,
    )

    move = DfsSolver(random.Random(0)).next_move(view)

    assert move.action == "reveal"
    assert move.cell == (0, 3)
    assert move.certain
    assert "P(MINE)=0" in move.reason


def test_dfs_solver_only_considers_frontier_cells():
    view = PlayerView(
        rows=1,
        cols=5,
        total_mines=1,
        cells=((None, 1, None, None, None),),
        flags=frozenset(),
        status=Status.PLAYING,
    )

    move = DfsSolver(random.Random(0)).next_move(view)

    assert move.action == "reveal"
    assert move.cell == (0, 0)
    assert not move.certain
    assert "P(MINE)=1/2" in move.reason
    assert "MINES_LEFT=1" in move.reason


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
    assert move.cell == (0, 2)
    assert move.reason == "[Opening] REVEAL (0, 2)"


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
