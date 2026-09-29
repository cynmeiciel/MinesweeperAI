"""Ground-truth mine layout. Knows nothing about what the player has seen."""
from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from minesweeper.core.config import GameConfig

Cell = tuple[int, int]  # (row, col)


def neighbors(r: int, c: int, rows: int, cols: int) -> list[Cell]:
    """In-bounds cells among the 8 surrounding (r, c), in row-major order."""
    return [
        (r + dr, c + dc)
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if (dr or dc) and 0 <= r + dr < rows and 0 <= c + dc < cols
    ]


@dataclass(frozen=True)
class Board:
    rows: int
    cols: int
    mines: frozenset[Cell]
    adjacent: tuple[tuple[int, ...], ...]  # mines among each cell's neighbours

    @classmethod
    def from_mines(cls, rows: int, cols: int, mines: Iterable[Cell]) -> Board:
        mine_set = frozenset(mines)
        for r, c in mine_set:
            if not (0 <= r < rows and 0 <= c < cols):
                raise ValueError(f"mine {(r, c)} out of bounds for {rows}x{cols}")
        adjacent = tuple(
            tuple(sum(n in mine_set for n in neighbors(r, c, rows, cols)) for c in range(cols))
            for r in range(rows)
        )
        return cls(rows, cols, mine_set, adjacent)

    @classmethod
    def generate(
        cls, config: GameConfig, rng: random.Random, exclude: Iterable[Cell] = frozenset()
    ) -> Board:
        excluded = set(exclude)
        allowed = [
            (r, c)
            for r in range(config.rows)
            for c in range(config.cols)
            if (r, c) not in excluded
        ]
        if config.mines > len(allowed):
            raise ValueError(
                f"not enough free cells: {config.mines} mines, {len(allowed)} allowed"
            )
        return cls.from_mines(config.rows, config.cols, rng.sample(allowed, config.mines))

    def is_mine(self, cell: Cell) -> bool:
        return cell in self.mines
