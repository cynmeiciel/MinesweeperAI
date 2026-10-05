"""LV2 deterministic solver using subset constraint reasoning."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from minesweeper.core.board import Cell
from minesweeper.core.game import PlayerView
from minesweeper.solver.base import Move, SolverStuck
from minesweeper.solver.rule_based_solver import RuleBasedSolver


@dataclass(frozen=True)
class Constraint:
    cells: frozenset[Cell]
    mines: int


class ConstraintSolver:
    """Apply LV1 rules, then derive safe cells and mines by subset differences."""

    name = "lv2"

    def __init__(self, rng: random.Random) -> None:
        self._lv1 = RuleBasedSolver(rng)

    def next_move(self, view: PlayerView) -> Move:
        try:
            return self._lv1.next_move(view)
        except SolverStuck:
            pass

        constraints = self._close_constraints(self._build_constraints(view))
        for constraint in constraints:
            if constraint.mines == 0:
                cell = self._first_cell(constraint.cells)
                return self._move("SAFE", constraint, "reveal", cell)
            if constraint.mines == len(constraint.cells):
                cell = self._first_cell(constraint.cells)
                return self._move("MINE", constraint, "flag", cell)
        raise SolverStuck("AI -> STUCK")

    @staticmethod
    def _build_constraints(view: PlayerView) -> list[Constraint]:
        constraints: list[Constraint] = []
        for row in range(view.rows):
            for col in range(view.cols):
                source = (row, col)
                number = view.number(source)
                if number is None:
                    continue
                neighbors = view.neighbors(source)
                unknown = frozenset(cell for cell in neighbors if view.is_hidden(cell))
                remaining_mines = number - sum(cell in view.flags for cell in neighbors)
                if unknown and 0 <= remaining_mines <= len(unknown):
                    constraints.append(Constraint(unknown, remaining_mines))
        return constraints

    @staticmethod
    def _close_constraints(constraints: list[Constraint]) -> list[Constraint]:
        known = {(constraint.cells, constraint.mines) for constraint in constraints}
        closed = list(constraints)
        changed = True
        while changed:
            changed = False
            for left in tuple(closed):
                for right in tuple(closed):
                    if not left.cells < right.cells:
                        continue
                    cells = right.cells - left.cells
                    mines = right.mines - left.mines
                    if not cells or not 0 <= mines <= len(cells):
                        continue
                    key = (cells, mines)
                    if key not in known:
                        known.add(key)
                        closed.append(Constraint(cells, mines))
                        changed = True
        return closed

    @staticmethod
    def _first_cell(cells: frozenset[Cell]) -> Cell:
        return min(cells)

    @staticmethod
    def _move(
        kind: str,
        constraint: Constraint,
        action: Literal["reveal", "flag"],
        cell: Cell,
    ) -> Move:
        reason = f"[LV2 {kind}] {constraint.cells} = {constraint.mines} -> {action.upper()} {cell}"
        return Move(action, cell, reason, certain=True)