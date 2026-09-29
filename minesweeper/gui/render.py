"""Pure helpers for drawing: no tkinter import, so they are unit-testable."""
from __future__ import annotations

from dataclasses import dataclass

from minesweeper.core.board import Cell
from minesweeper.core.game import CellState, Game, Status

# Tk 8.6 cannot render characters above U+FFFF, so only BMP symbols here.
FLAG = "⚑"
MINE = "✹"
WRONG_FLAG = "✗"
FACES = {Status.READY: "☺", Status.PLAYING: "☺", Status.WON: "✌", Status.LOST: "☹"}

HIDDEN_BG = "#c0c0c0"
REVEALED_BG = "#e8e8e8"
HIT_BG = "#ff4040"
NUMBER_COLORS = {
    1: "#0000ff", 2: "#008000", 3: "#ff0000", 4: "#000080",
    5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080",
}


@dataclass(frozen=True)
class Appearance:
    text: str
    fg: str
    bg: str
    raised: bool


def cell_appearance(game: Game, r: int, c: int) -> Appearance:
    state = game.state(r, c)
    board = game.board
    is_mine = board is not None and board.is_mine((r, c))
    if state is CellState.REVEALED:
        if is_mine:  # only the mine that was clicked
            return Appearance(MINE, "#000000", HIT_BG, False)
        n = game.number(r, c)
        return Appearance(str(n) if n else "", NUMBER_COLORS.get(n, "#000000"), REVEALED_BG, False)
    if state is CellState.FLAGGED:
        if game.status is Status.LOST and not is_mine:
            return Appearance(WRONG_FLAG, "#ff0000", HIDDEN_BG, True)
        return Appearance(FLAG, "#ff0000", HIDDEN_BG, True)
    if is_mine and game.status is Status.LOST:
        return Appearance(MINE, "#000000", REVEALED_BG, False)
    if is_mine and game.status is Status.WON:
        return Appearance(FLAG, "#ff0000", HIDDEN_BG, True)
    return Appearance("", "#000000", HIDDEN_BG, True)


def pixel_to_cell(x: float, y: float, cell_size: int, rows: int, cols: int) -> Cell | None:
    if x < 0 or y < 0:
        return None
    r, c = int(y // cell_size), int(x // cell_size)
    if r >= rows or c >= cols:
        return None
    return (r, c)


def cell_size_for(rows: int, cols: int, max_w: int, max_h: int) -> int:
    return max(16, min(40, max_w // cols, max_h // rows))
