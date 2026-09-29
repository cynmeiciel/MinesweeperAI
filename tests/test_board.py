import random

import pytest

from minesweeper.core.board import Board, neighbors
from minesweeper.core.config import FirstClick, GameConfig


def test_neighbors_corner_edge_centre():
    assert neighbors(0, 0, 3, 3) == [(0, 1), (1, 0), (1, 1)]
    assert len(neighbors(0, 1, 3, 3)) == 5
    assert len(neighbors(1, 1, 3, 3)) == 8
    assert neighbors(0, 0, 1, 1) == []


def test_neighbors_order_is_row_major():
    assert neighbors(1, 1, 3, 3) == [
        (0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2),
    ]


def test_from_mines_adjacency():
    # . * .
    # . . .
    # * . .      (a mine's own count ignores itself)
    board = Board.from_mines(3, 3, [(0, 1), (2, 0)])
    assert board.adjacent == ((1, 0, 1), (2, 2, 1), (0, 1, 0))
    assert board.is_mine((0, 1))
    assert not board.is_mine((1, 1))


def test_from_mines_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="out of bounds"):
        Board.from_mines(3, 3, [(3, 0)])


def test_generate_places_exact_count():
    cfg = GameConfig(9, 9, 10)
    board = Board.generate(cfg, random.Random(1))
    assert len(board.mines) == 10
    assert all(0 <= r < 9 and 0 <= c < 9 for r, c in board.mines)


def test_generate_same_seed_same_board():
    cfg = GameConfig(16, 30, 99)
    a = Board.generate(cfg, random.Random(42))
    b = Board.generate(cfg, random.Random(42))
    c = Board.generate(cfg, random.Random(43))
    assert a.mines == b.mines
    assert a.mines != c.mines


def test_generate_respects_exclusion():
    cfg = GameConfig(5, 5, 16)
    exclude = {(2, 2), *neighbors(2, 2, 5, 5)}
    for seed in range(50):
        board = Board.generate(cfg, random.Random(seed), exclude)
        assert not board.mines & exclude


def test_generate_rejects_when_not_enough_room():
    cfg = GameConfig(3, 3, 9, first_click=FirstClick.UNSAFE)
    with pytest.raises(ValueError, match="not enough"):
        Board.generate(cfg, random.Random(0), {(0, 0)})
