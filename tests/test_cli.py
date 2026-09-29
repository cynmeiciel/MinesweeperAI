import argparse

import pytest

from minesweeper.cli import add_game_args, configs_from_args, parse_density
from minesweeper.core.config import FirstClick, FloodFill


def parse(argv, multi=True):
    parser = argparse.ArgumentParser()
    add_game_args(parser, multi=multi)
    return configs_from_args(parser.parse_args(argv))


def test_parse_density_single_and_range():
    assert parse_density("0.15") == [0.15]
    assert parse_density("0.10:0.25:0.03") == pytest.approx([0.10, 0.13, 0.16, 0.19, 0.22, 0.25])


@pytest.mark.parametrize("bad", ["abc", "0.1:0.2", "0.1:0.2:0", "0.3:0.1:0.05"])
def test_parse_density_rejects(bad):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_density(bad)


def test_default_is_beginner_with_default_rules():
    [cfg] = parse([])
    assert (cfg.rows, cfg.cols, cfg.mines) == (9, 9, 10)
    assert cfg.first_click is FirstClick.OPENING and cfg.chord and cfg.flood_fill is FloodFill.BFS


def test_rule_flags():
    [cfg] = parse(["--first-click", "SAFE", "--no-chord", "--flood-fill", "DFS", "--seed", "4"])
    assert cfg.first_click is FirstClick.SAFE
    assert cfg.chord is False
    assert cfg.flood_fill is FloodFill.DFS
    assert cfg.seed == 4


def test_multiple_presets():
    cfgs = parse(["--preset", "tiny", "--preset", "expert"])
    assert [(c.rows, c.cols, c.mines) for c in cfgs] == [(5, 5, 3), (16, 30, 99)]


def test_single_preset_non_multi():
    [cfg] = parse(["--preset", "intermediate"], multi=False)
    assert (cfg.rows, cfg.cols, cfg.mines) == (16, 16, 40)


def test_custom_size_with_mines():
    [cfg] = parse(["--rows", "7", "--cols", "8", "--mines", "5"])
    assert (cfg.rows, cfg.cols, cfg.mines) == (7, 8, 5)


def test_density_sweep_over_preset():
    cfgs = parse(["--preset", "beginner", "--density", "0.10:0.20:0.05"])
    assert [c.mines for c in cfgs] == [round(81 * d) for d in (0.10, 0.15, 0.20)]


def test_preset_mines_override():
    [cfg] = parse(["--preset", "beginner", "--mines", "20"])
    assert cfg.mines == 20


@pytest.mark.parametrize(
    "argv,msg",
    [
        (["--rows", "5"], "together"),
        (["--rows", "5", "--cols", "5"], "--mines or --density"),
        (["--preset", "tiny", "--rows", "5", "--cols", "5"], "either --preset"),
        (["--mines", "5", "--density", "0.1"], "either --mines"),
        (["--preset", "tiny", "--density", "0.9"], "too many mines"),
    ],
)
def test_invalid_combinations(argv, msg):
    with pytest.raises(ValueError, match=msg):
        parse(argv)
