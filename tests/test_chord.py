import pytest

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import CellState, Game, Status


def make_game(rows, cols, mines, **kw) -> Game:
    kw.setdefault("first_click", FirstClick.UNSAFE)
    cfg = GameConfig(rows, cols, len(mines), **kw)
    return Game(cfg, board=Board.from_mines(rows, cols, mines))


# 3x3, one mine top-left:
#   * 1 0
#   1 1 0
#   0 0 0
def corner_game(**kw) -> Game:
    return make_game(3, 3, [(0, 0)], **kw)


def test_chord_reveals_unflagged_neighbours():
    g = make_game(3, 4, [(0, 0), (2, 3)])
    g.reveal(1, 1)                      # number 1
    g.toggle_flag(0, 0)
    res = g.chord(1, 1)
    # every unflagged neighbour opens; zeros among them keep flood-filling
    assert {(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)} <= set(res.revealed)
    assert g.state(0, 0) is CellState.FLAGGED
    assert g.stats.clicks == 2


def test_chord_refused_when_flag_count_differs():
    g = corner_game()
    g.reveal(1, 1)
    assert g.chord(1, 1).revealed == ()  # 0 flags, number is 1


def test_chord_refused_with_more_flags_than_number():
    g = corner_game()
    g.reveal(1, 1)
    g.toggle_flag(0, 0)
    g.toggle_flag(0, 1)                 # 2 flags around a 1
    res = g.chord(1, 1)
    assert res.revealed == ()
    assert g.state(0, 2) is CellState.HIDDEN
    assert g.status is Status.PLAYING


def test_chord_refused_on_hidden_cell():
    g = corner_game()
    g.reveal(1, 1)
    assert g.chord(2, 2).revealed == ()


def test_chord_disabled_by_config():
    g = corner_game(chord=False)
    g.reveal(1, 1)
    g.toggle_flag(0, 0)
    assert g.chord(1, 1).revealed == ()
    assert g.status is Status.PLAYING


def test_chord_with_wrong_flag_loses():
    g = corner_game()
    g.reveal(1, 1)
    g.toggle_flag(0, 1)                 # wrong flag
    res = g.chord(1, 1)
    assert res.hit_mine == (0, 0)
    assert g.status is Status.LOST


def test_chord_can_win():  # Review Focus 3
    g = corner_game()
    g.reveal(1, 1)
    g.toggle_flag(0, 0)
    res = g.chord(1, 1)
    assert res.status is Status.WON
    assert g.revealed_count == 8


def test_chord_after_game_over_is_noop():
    g = corner_game()
    g.reveal(1, 1)
    g.reveal(0, 0)
    assert g.chord(1, 1).revealed == ()


def test_chord_out_of_bounds():
    with pytest.raises(IndexError):
        corner_game().chord(5, 5)
