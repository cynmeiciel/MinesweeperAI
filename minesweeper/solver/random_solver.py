"""Baseline: reveal a uniformly random hidden cell. Lower bound for comparisons."""
from __future__ import annotations

import random

from minesweeper.core.game import PlayerView
from minesweeper.solver.base import Move


class RandomSolver:
    name = "random"

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def next_move(self, view: PlayerView) -> Move:
        hidden = view.hidden_cells()
        if not hidden:
            raise ValueError("no hidden cells left to reveal")
        return Move("reveal", self._rng.choice(hidden), "random pick", certain=False)
