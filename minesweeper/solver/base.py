"""Solver contract shared by the GUI and the batch runner."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol

from minesweeper.core.board import Cell
from minesweeper.core.game import CellState, Game, PlayerView


@dataclass(frozen=True)
class Move:
    action: Literal["reveal", "flag"]
    cell: Cell
    reason: str    # human-readable, shown in the GUI and useful for the report
    certain: bool  # False = a guess


class Solver(Protocol):
    name: ClassVar[str]

    def __init__(self, rng: random.Random) -> None: ...

    def next_move(self, view: PlayerView) -> Move: ...


def solver_rng(seed: int) -> random.Random:
    """Reproducible RNG for a solver, independent of the board's RNG stream.

    Seeding it with the game seed itself would replay the board generator's
    draws, so a random guess would land exactly on the first mine placed.
    """
    return random.Random(f"solver:{seed}")


def apply_move(game: Game, move: Move) -> bool:
    """Apply a solver move. Returns False (and changes nothing) if it is illegal."""
    r, c = move.cell
    if game.is_over or not (0 <= r < game.rows and 0 <= c < game.cols):
        return False
    if move.action == "reveal":
        if game.state(r, c) is not CellState.HIDDEN:
            return False
        game.reveal(r, c)
        return True
    if move.action == "flag":
        return game.toggle_flag(r, c)
    return False
