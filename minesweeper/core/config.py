"""Game configuration: board size, mine count and rule variants."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FirstClick(Enum):
    """What the first reveal is guaranteed to be."""

    UNSAFE = "UNSAFE"    # mines placed up front; first click may lose
    SAFE = "SAFE"        # first clicked cell is never a mine
    OPENING = "OPENING"  # first clicked cell and its neighbours are mine-free


class FloodFill(Enum):
    BFS = "BFS"
    DFS = "DFS"


# Cells that must stay mine-free for each first-click rule (worst case).
_RESERVE = {FirstClick.UNSAFE: 0, FirstClick.SAFE: 1, FirstClick.OPENING: 9}


@dataclass(frozen=True)
class GameConfig:
    rows: int
    cols: int
    mines: int
    first_click: FirstClick = FirstClick.OPENING
    chord: bool = True
    flood_fill: FloodFill = FloodFill.BFS
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError(f"board must be at least 1x1, got {self.rows}x{self.cols}")
        if self.mines < 1:
            raise ValueError(f"need at least 1 mine, got {self.mines}")
        cells = self.rows * self.cols
        max_mines = cells - min(_RESERVE[self.first_click], cells)
        if self.mines > max_mines:
            raise ValueError(
                f"too many mines: {self.mines} on {self.rows}x{self.cols} with "
                f"first_click={self.first_click.name} (max {max_mines})"
            )

    @classmethod
    def from_density(cls, rows: int, cols: int, density: float, **kwargs) -> GameConfig:
        if not 0 < density < 1:
            raise ValueError(f"density must be between 0 and 1 (exclusive), got {density}")
        mines = max(1, round(rows * cols * density))
        return cls(rows, cols, mines, **kwargs)

    @property
    def density(self) -> float:
        return self.mines / (self.rows * self.cols)


PRESETS: dict[str, GameConfig] = {
    "tiny": GameConfig(5, 5, 3),
    "beginner": GameConfig(9, 9, 10),
    "intermediate": GameConfig(16, 16, 40),
    "expert": GameConfig(16, 30, 99),
}
