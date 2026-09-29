import pytest

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import Game
from minesweeper.gui.render import (
    FLAG,
    HIDDEN_BG,
    HIT_BG,
    MINE,
    NUMBER_COLORS,
    REVEALED_BG,
    WRONG_FLAG,
    cell_appearance,
    cell_size_for,
    pixel_to_cell,
)


def game_3x3() -> Game:
    #   * 1 0
    #   1 1 0
    #   0 0 0
    cfg = GameConfig(3, 3, 1, first_click=FirstClick.UNSAFE)
    return Game(cfg, board=Board.from_mines(3, 3, [(0, 0)]))


def test_hidden_cell():
    a = cell_appearance(game_3x3(), 1, 1)
    assert (a.text, a.bg, a.raised) == ("", HIDDEN_BG, True)


def test_revealed_number_and_blank():
    g = game_3x3()
    g.reveal(1, 1)
    a = cell_appearance(g, 1, 1)
    assert (a.text, a.fg, a.bg, a.raised) == ("1", NUMBER_COLORS[1], REVEALED_BG, False)
    g.reveal(2, 2)
    assert cell_appearance(g, 2, 2).text == ""


def test_flag():
    g = game_3x3()
    g.toggle_flag(0, 0)
    assert cell_appearance(g, 0, 0).text == FLAG


def test_lost_shows_mines_hit_and_wrong_flags():
    cfg = GameConfig(3, 3, 2, first_click=FirstClick.UNSAFE)
    g = Game(cfg, board=Board.from_mines(3, 3, [(0, 0), (2, 2)]))
    g.toggle_flag(1, 1)  # wrong flag
    g.reveal(0, 0)       # hit
    hit = cell_appearance(g, 0, 0)
    assert (hit.text, hit.bg) == (MINE, HIT_BG)
    other = cell_appearance(g, 2, 2)
    assert other.text == MINE and other.bg == REVEALED_BG
    assert cell_appearance(g, 1, 1).text == WRONG_FLAG


def test_won_shows_hidden_mines_as_flags():
    g = game_3x3()
    g.reveal(2, 2)
    assert g.is_over
    assert cell_appearance(g, 0, 0).text == FLAG


def test_all_numbers_have_colours():
    assert set(NUMBER_COLORS) == set(range(1, 9))


@pytest.mark.parametrize(
    "x,y,expected",
    [(0, 0, (0, 0)), (39, 39, (0, 0)), (40, 0, (0, 1)), (119, 79, (1, 2)),
     (120, 0, None), (0, 80, None), (-1, 5, None), (5, -1, None)],
)
def test_pixel_to_cell(x, y, expected):  # Review Focus 5
    assert pixel_to_cell(x, y, 40, rows=2, cols=3) == expected


def test_cell_size_clamped():
    assert cell_size_for(9, 9, 2000, 2000) == 40
    assert cell_size_for(100, 100, 1000, 1000) == 16
    assert cell_size_for(16, 30, 900, 800) == 30
