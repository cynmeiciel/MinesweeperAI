"""LV1 deterministic Minesweeper solver."""
from __future__ import annotations

import logging
import random
from typing import Literal

from minesweeper.core.board import Cell
from minesweeper.core.game import PlayerView
from minesweeper.solver.base import Move, SolverStuck

log = logging.getLogger(__name__)


class RuleBasedSolver:
    """Apply only the basic mine and safe-neighbour rules."""

    name = "lv1"

    def __init__(self, rng: random.Random) -> None:
        self.last_level = 1
        del rng  # The LV1 solver never guesses.

    def next_move(self, view: PlayerView) -> Move:
        if not self._open_cells(view):
            hidden = view.hidden_cells()
            if hidden:
                cell = min(
                    hidden,
                    key=lambda candidate: (
                        abs(2 * candidate[0] - (view.rows - 1))
                        + abs(2 * candidate[1] - (view.cols - 1)),
                        candidate,
                    ),
                )
                reason = f"[Opening] REVEAL {cell}"
                log.info(reason)
                return Move("reveal", cell, reason, certain=True)

        for source in self._open_cells(view):
            number = view.number(source)
            assert number is not None
            unknown = [cell for cell in view.neighbors(source) if view.is_hidden(cell)]
            flagged = sum(cell in view.flags for cell in view.neighbors(source))
            remaining_mines = number - flagged

            if unknown and len(unknown) == remaining_mines:
                return self._move("Rule 1", source, "flag", unknown[0])
            if unknown and remaining_mines == 0:
                return self._move("Rule 2", source, "reveal", unknown[0])
        log.info("AI -> STUCK")
        raise SolverStuck("AI -> STUCK")

    @staticmethod
    def _open_cells(view: PlayerView) -> list[Cell]:
        return [
            (row, col)
            for row in range(view.rows)
            for col in range(view.cols)
            if view.number((row, col)) is not None
        ]

    @staticmethod
    def _move(
        rule: str, source: Cell, action: Literal["reveal", "flag"], target: Cell
    ) -> Move:
        reason = f"[{rule}] {source} -> {action.upper()} {target}"
        log.info(reason)
        return Move(action, target, reason, certain=True)