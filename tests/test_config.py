import dataclasses

import pytest

from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig


def test_defaults():
    cfg = GameConfig(9, 9, 10)
    assert cfg.first_click is FirstClick.OPENING
    assert cfg.chord is True
    assert cfg.flood_fill is FloodFill.BFS
    assert cfg.seed is None


def test_density_property():
    assert GameConfig(10, 10, 15).density == pytest.approx(0.15)


def test_from_density_rounds_and_passes_options():
    cfg = GameConfig.from_density(9, 9, 0.123, chord=False, seed=7)
    assert cfg.mines == round(81 * 0.123)  # 10
    assert cfg.chord is False
    assert cfg.seed == 7


def test_from_density_at_least_one_mine():
    assert GameConfig.from_density(5, 5, 0.001).mines == 1


@pytest.mark.parametrize("density", [0, -0.1, 1, 1.5])
def test_from_density_rejects_out_of_range(density):
    with pytest.raises(ValueError, match="density"):
        GameConfig.from_density(9, 9, density)


@pytest.mark.parametrize("rows,cols", [(0, 5), (5, 0), (-1, 5)])
def test_rejects_bad_dimensions(rows, cols):
    with pytest.raises(ValueError, match="at least 1x1"):
        GameConfig(rows, cols, 1, first_click=FirstClick.UNSAFE)


def test_rejects_zero_mines():
    with pytest.raises(ValueError, match="at least 1 mine"):
        GameConfig(5, 5, 0)


@pytest.mark.parametrize(
    "rule,max_mines",
    [(FirstClick.UNSAFE, 25), (FirstClick.SAFE, 24), (FirstClick.OPENING, 16)],
)
def test_mine_limit_per_first_click_rule(rule, max_mines):
    GameConfig(5, 5, max_mines, first_click=rule)  # boundary is valid
    with pytest.raises(ValueError, match="too many mines"):
        GameConfig(5, 5, max_mines + 1, first_click=rule)


def test_opening_reserve_capped_on_tiny_boards():
    # 2x2 board: OPENING reserves min(9, 4) = 4 cells → no room for mines
    with pytest.raises(ValueError, match="too many mines"):
        GameConfig(2, 2, 1)
    GameConfig(2, 2, 3, first_click=FirstClick.SAFE)


def test_presets():
    assert {k: (v.rows, v.cols, v.mines) for k, v in PRESETS.items()} == {
        "tiny": (5, 5, 3),
        "beginner": (9, 9, 10),
        "intermediate": (16, 16, 40),
        "expert": (16, 30, 99),
    }


def test_frozen_and_replace_revalidates():
    cfg = PRESETS["tiny"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.rows = 3  # type: ignore[misc]
    with pytest.raises(ValueError):
        dataclasses.replace(cfg, mines=100)
