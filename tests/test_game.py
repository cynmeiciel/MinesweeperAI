import pytest

from minesweeper.core.board import Board, neighbors
from minesweeper.core.config import FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, Status


def make_game(rows, cols, mines, **kw) -> Game:
    """Game on a fixed, hand-made layout."""
    kw.setdefault("first_click", FirstClick.UNSAFE)
    cfg = GameConfig(rows, cols, len(mines), **kw)
    return Game(cfg, board=Board.from_mines(rows, cols, mines))


# Layout used by several tests (1 row, mine at the right end):
#   0 0 0 0 1 *
def strip_game(**kw) -> Game:
    return make_game(1, 6, [(0, 5)], **kw)


def test_initial_state():
    g = strip_game()
    assert g.status is Status.READY
    assert all(g.state(0, c) is CellState.HIDDEN for c in range(6))
    assert g.mines_remaining == 1
    assert g.revealed_count == 0


def test_reveal_number_reveals_only_that_cell():
    g = strip_game()
    res = g.reveal(0, 4)
    assert res.revealed == ((0, 4),)
    assert g.number(0, 4) == 1
    assert g.status is Status.PLAYING


def test_bfs_order():
    g = strip_game(flood_fill=FloodFill.BFS)
    res = g.reveal(0, 2)
    assert res.revealed == ((0, 2), (0, 1), (0, 3), (0, 0), (0, 4))


def test_dfs_order():
    g = strip_game(flood_fill=FloodFill.DFS)
    res = g.reveal(0, 2)
    assert res.revealed == ((0, 2), (0, 3), (0, 4), (0, 1), (0, 0))


def test_flood_fill_reaches_win():
    g = strip_game()
    res = g.reveal(0, 0)
    assert set(res.revealed) == {(0, c) for c in range(5)}
    assert res.status is Status.WON
    assert g.is_over


def test_bfs_and_dfs_reveal_same_set_on_random_boards():
    for seed in range(30):
        results = []
        for ff in FloodFill:
            g = Game(GameConfig(16, 16, 40, flood_fill=ff, seed=seed))
            results.append(set(g.reveal(8, 8).revealed))
        assert results[0] == results[1]


def test_flags_block_flood_fill():
    g = strip_game()
    assert g.toggle_flag(0, 1)
    res = g.reveal(0, 3)
    assert (0, 1) not in res.revealed and (0, 0) not in res.revealed
    assert g.state(0, 1) is CellState.FLAGGED
    assert g.status is Status.PLAYING


def test_reveal_mine_loses():
    g = strip_game()
    res = g.reveal(0, 5)
    assert res.hit_mine == (0, 5)
    assert res.status is Status.LOST
    assert g.state(0, 5) is CellState.REVEALED
    assert g.number(0, 5) is None


def test_left_click_on_flag_is_noop():  # Review Focus 1
    g = strip_game()
    g.toggle_flag(0, 5)
    res = g.reveal(0, 5)
    assert res.revealed == () and res.hit_mine is None
    assert g.status is Status.READY


def test_reveal_revealed_cell_is_noop():
    g = strip_game()
    g.reveal(0, 4)
    assert g.reveal(0, 4).revealed == ()


def test_actions_after_game_over_are_noops():  # Review Focus 5
    g = strip_game()
    g.reveal(0, 5)
    assert g.reveal(0, 0).revealed == ()
    assert g.toggle_flag(0, 0) is False
    assert g.status is Status.LOST


def test_out_of_bounds_raises_index_error():
    g = strip_game()
    with pytest.raises(IndexError):
        g.reveal(1, 0)
    with pytest.raises(IndexError):
        g.toggle_flag(0, -1)


def test_toggle_flag_counts():
    g = strip_game()
    assert g.toggle_flag(0, 0) and g.toggle_flag(0, 1)
    assert g.mines_remaining == -1  # may go negative
    assert g.toggle_flag(0, 0)
    assert g.state(0, 0) is CellState.HIDDEN
    assert g.flags_placed == 1
    assert g.stats.flags == 3
    assert g.status is Status.READY  # flagging does not start the game


def test_cannot_flag_revealed_cell():
    g = strip_game()
    g.reveal(0, 4)
    assert g.toggle_flag(0, 4) is False


def test_safe_first_click_never_mine():
    for seed in range(200):
        g = Game(GameConfig(3, 3, 8, first_click=FirstClick.SAFE, seed=seed))
        res = g.reveal(1, 1)
        assert res.hit_mine is None
        assert g.status is Status.WON  # only one safe cell on the board


@pytest.mark.parametrize("cell", [(0, 0), (0, 2), (4, 4), (2, 2), (4, 0)])
def test_opening_first_click_is_zero_even_at_max_density(cell):  # Review Focus 2
    for seed in range(50):
        g = Game(GameConfig(5, 5, 16, seed=seed))
        res = g.reveal(*cell)
        assert res.hit_mine is None
        assert g.number(*cell) == 0
        assert set(neighbors(*cell, 5, 5)) <= set(res.revealed)


def test_unsafe_board_exists_before_first_click():
    g = Game(GameConfig(5, 5, 3, first_click=FirstClick.UNSAFE, seed=1))
    assert g.board is not None


def test_board_generated_lazily_for_safe_rules():
    g = Game(GameConfig(5, 5, 3, seed=1))
    assert g.board is None
    g.reveal(2, 2)
    assert g.board is not None


def test_seed_recorded_when_not_given():
    g = Game(GameConfig(5, 5, 3))
    assert isinstance(g.seed, int)
    replay = Game(GameConfig(5, 5, 3, seed=g.seed))
    g.reveal(2, 2)
    replay.reveal(2, 2)
    assert g.board.mines == replay.board.mines


def test_injected_board_must_match_config():
    with pytest.raises(ValueError):
        Game(GameConfig(5, 5, 3), board=Board.from_mines(5, 5, [(0, 0)]))


def test_stats():
    g = strip_game()
    assert g.stats.elapsed == 0.0
    g.reveal(0, 4)
    g.reveal(0, 4)  # no-op, not counted
    assert g.stats.clicks == 1
    assert g.stats.start_time is not None
    g.reveal(0, 0)
    assert g.stats.end_time is not None
    assert g.stats.elapsed >= 0


def test_view_hides_mines():
    g = strip_game()
    g.toggle_flag(0, 5)
    g.reveal(0, 4)
    v = g.view()
    assert v.cells == ((None, None, None, None, 1, None),)
    assert v.flags == frozenset({(0, 5)})
    assert v.total_mines == 1
    assert v.number((0, 4)) == 1
    assert v.is_hidden((0, 0)) and not v.is_hidden((0, 5)) and not v.is_hidden((0, 4))
    assert v.hidden_cells() == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert v.neighbors((0, 0)) == [(0, 1)]
    assert not hasattr(v, "mines") and not hasattr(v, "board")
