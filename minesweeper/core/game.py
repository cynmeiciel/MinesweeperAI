"""Game rules and state on top of a Board."""
from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum

from minesweeper.core.board import Board, Cell, neighbors
from minesweeper.core.config import FirstClick, FloodFill, GameConfig


class CellState(Enum):
    HIDDEN = "hidden"
    FLAGGED = "flagged"
    REVEALED = "revealed"


class Status(Enum):
    READY = "ready"      # no reveal yet
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True)
class RevealResult:
    revealed: tuple[Cell, ...]  # newly revealed, in reveal order
    hit_mine: Cell | None
    status: Status


@dataclass
class GameStats:
    clicks: int = 0   # reveal/chord calls that changed the board
    flags: int = 0    # flag toggles that changed the board
    start_time: float | None = None
    end_time: float | None = None

    @property
    def elapsed(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.perf_counter()
        return end - self.start_time


@dataclass(frozen=True)
class PlayerView:
    """Everything a player (or solver) is allowed to see. Never mine positions."""

    rows: int
    cols: int
    total_mines: int
    cells: tuple[tuple[int | None, ...], ...]  # revealed number, else None
    flags: frozenset[Cell]
    status: Status

    def number(self, cell: Cell) -> int | None:
        return self.cells[cell[0]][cell[1]]

    def is_hidden(self, cell: Cell) -> bool:
        return self.number(cell) is None and cell not in self.flags

    def hidden_cells(self) -> list[Cell]:
        return [
            (r, c) for r in range(self.rows) for c in range(self.cols) if self.is_hidden((r, c))
        ]

    def neighbors(self, cell: Cell) -> list[Cell]:
        return neighbors(cell[0], cell[1], self.rows, self.cols)


class Game:
    def __init__(self, config: GameConfig, board: Board | None = None) -> None:
        self.config = config
        self.seed: int = (
            config.seed if config.seed is not None else random.SystemRandom().randrange(2**32)
        )
        self._rng = random.Random(self.seed)
        self.rows, self.cols = config.rows, config.cols
        self._state = [[CellState.HIDDEN] * self.cols for _ in range(self.rows)]
        self._revealed = 0
        self.flags_placed = 0
        self.status = Status.READY
        self.stats = GameStats()
        if board is not None:
            if (board.rows, board.cols, len(board.mines)) != (self.rows, self.cols, config.mines):
                raise ValueError("injected board does not match config")
            self._board: Board | None = board
        elif config.first_click is FirstClick.UNSAFE:
            self._board = Board.generate(config, self._rng)
        else:
            self._board = None  # generated on the first reveal

    # --- read-only accessors -------------------------------------------------

    @property
    def board(self) -> Board | None:
        """Ground truth, for rendering only. Solvers must use view()."""
        return self._board

    @property
    def revealed_count(self) -> int:
        return self._revealed

    @property
    def mines_remaining(self) -> int:
        return self.config.mines - self.flags_placed

    @property
    def is_over(self) -> bool:
        return self.status in (Status.WON, Status.LOST)

    def state(self, r: int, c: int) -> CellState:
        self._check(r, c)
        return self._state[r][c]

    def number(self, r: int, c: int) -> int | None:
        """Adjacent-mine count of a revealed safe cell, else None."""
        self._check(r, c)
        if self._state[r][c] is not CellState.REVEALED or self._board.is_mine((r, c)):
            return None
        return self._board.adjacent[r][c]

    def view(self) -> PlayerView:
        cells = tuple(
            tuple(self.number(r, c) for c in range(self.cols)) for r in range(self.rows)
        )
        flags = frozenset(
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self._state[r][c] is CellState.FLAGGED
        )
        return PlayerView(self.rows, self.cols, self.config.mines, cells, flags, self.status)

    # --- actions ---------------------------------------------------------------

    def reveal(self, r: int, c: int) -> RevealResult:
        self._check(r, c)
        if self.is_over or self._state[r][c] is not CellState.HIDDEN:
            return self._nothing()
        self._start((r, c))
        result = self._open([(r, c)])
        self.stats.clicks += 1
        return result

    def toggle_flag(self, r: int, c: int) -> bool:
        self._check(r, c)
        if self.is_over:
            return False
        state = self._state[r][c]
        if state is CellState.HIDDEN:
            self._state[r][c] = CellState.FLAGGED
            self.flags_placed += 1
        elif state is CellState.FLAGGED:
            self._state[r][c] = CellState.HIDDEN
            self.flags_placed -= 1
        else:
            return False
        self.stats.flags += 1
        return True

    def chord(self, r: int, c: int) -> RevealResult:
        """On a revealed number whose flagged neighbours equal it, reveal the rest."""
        self._check(r, c)
        if not self.config.chord or self.is_over or self._state[r][c] is not CellState.REVEALED:
            return self._nothing()
        around = neighbors(r, c, self.rows, self.cols)
        flagged = sum(self._state[nr][nc] is CellState.FLAGGED for nr, nc in around)
        hidden = [(nr, nc) for nr, nc in around if self._state[nr][nc] is CellState.HIDDEN]
        if flagged < self._board.adjacent[r][c] or not hidden:
            return self._nothing()
        result = self._open(hidden)
        self.stats.clicks += 1
        return result

    # --- internals -------------------------------------------------------------

    def _check(self, r: int, c: int) -> None:
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            raise IndexError(f"cell {(r, c)} out of bounds for {self.rows}x{self.cols}")

    def _nothing(self) -> RevealResult:
        return RevealResult((), None, self.status)

    def _start(self, cell: Cell) -> None:
        """Generate the board if needed and move READY → PLAYING."""
        if self._board is None:
            exclude = {cell}
            if self.config.first_click is FirstClick.OPENING:
                exclude.update(neighbors(*cell, self.rows, self.cols))
            self._board = Board.generate(self.config, self._rng, exclude)
        if self.status is Status.READY:
            self.status = Status.PLAYING
            self.stats.start_time = time.perf_counter()

    def _finish(self, status: Status) -> None:
        self.status = status
        self.stats.end_time = time.perf_counter()

    def _open(self, starts: list[Cell]) -> RevealResult:
        """Reveal each start cell (flood-filling zeros); stop at the first mine."""
        revealed: list[Cell] = []
        for start in starts:
            r, c = start
            if self._state[r][c] is not CellState.HIDDEN:
                continue  # already opened by an earlier flood in this call
            if self._board.is_mine(start):
                self._state[r][c] = CellState.REVEALED
                revealed.append(start)
                self._finish(Status.LOST)
                return RevealResult(tuple(revealed), start, self.status)
            revealed.extend(self._flood(start))
        if self._revealed == self.rows * self.cols - self.config.mines:
            self._finish(Status.WON)
        return RevealResult(tuple(revealed), None, self.status)

    def _flood(self, start: Cell) -> list[Cell]:
        """Iterative flood fill. BFS uses a queue, DFS a stack; same final set."""
        frontier = deque([start])
        pop = frontier.popleft if self.config.flood_fill is FloodFill.BFS else frontier.pop
        seen = {start}
        out: list[Cell] = []
        while frontier:
            r, c = pop()
            if self._state[r][c] is not CellState.HIDDEN:
                continue
            self._state[r][c] = CellState.REVEALED
            self._revealed += 1
            out.append((r, c))
            if self._board.adjacent[r][c] == 0:
                for n in neighbors(r, c, self.rows, self.cols):
                    if n not in seen and self._state[n[0]][n[1]] is CellState.HIDDEN:
                        seen.add(n)
                        frontier.append(n)
        return out
