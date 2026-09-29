# Minesweeper Game, GUI & Analysis Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A playable, fully configurable Minesweeper (tkinter GUI) with a GUI-free engine, a solver interface with a random baseline, and a headless batch runner that writes CSV statistics.

**Architecture:** `minesweeper/core` holds pure, seed-deterministic game logic (config → board → game). `solver` sees only a `PlayerView` (never mine positions). `gui` and `analysis` are thin front-ends over `core` + `solver`, sharing one CLI-argument → `GameConfig` builder in `minesweeper/cli.py`.

**Tech Stack:** Python 3.13, tkinter (Tk 8.6), stdlib only at runtime; pytest via `uv` for tests.

**Spec:** `docs/superpowers/specs/2026-09-29-minesweeper-design.md`

## Global Constraints

- No runtime dependencies; stdlib only. Dev dependency: `pytest>=8`.
- `requires-python = ">=3.11"`; developed on Python 3.13.7.
- `minesweeper/core` must not import from `gui`, `solver`, or `analysis`.
- Solvers receive only `PlayerView`; nothing a solver can reach exposes mine positions.
- Same `seed` → identical board and identical batch results (except `time_ms`).
- Flood fill is iterative (deque), never recursive.
- Tk 8.6: GUI text uses only BMP characters (`☺ ☹ ✌ ⚑ ✹ ✗`), no emoji above U+FFFF.
- Defaults: `first_click=OPENING`, `chord=True`, `flood_fill=BFS`, `seed=None`.
- Presets: tiny 5x5/3, beginner 9x9/10, intermediate 16x16/40, expert 16x30/99.
- Run tests with `uv run pytest` from the project root.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Left-clicking a flagged cell** → nothing happens (flag protects the cell). Test in Task 3.
2. **Max-density OPENING boards clicked at a corner/edge/centre** (e.g. 5x5 with 16 mines) → board generates, first click reveals a 0, never crashes. Test in Task 3.
3. **Winning via chord** (last safe cells opened by a chord) → status becomes WON. Test in Task 4.
4. **A density sweep that produces an invalid config** (e.g. `--preset tiny --density 0.9`) → CLI prints a clean error and exits with code 2, no traceback. Test in Task 7.
5. **Clicks outside the board / after game over** → ignored, never raise. Tests in Task 3 (`reveal`/`toggle_flag` after game over) and Task 8 (`pixel_to_cell` returns `None`).

## File Map

```
pyproject.toml, .gitignore, README.md
minesweeper/__init__.py
minesweeper/__main__.py          # GUI entry (Task 9)
minesweeper/cli.py               # shared argparse → GameConfig (Task 6)
minesweeper/core/__init__.py     # re-exports
minesweeper/core/config.py       # Task 1
minesweeper/core/board.py        # Task 2
minesweeper/core/game.py         # Tasks 3–4
minesweeper/solver/__init__.py   # SOLVERS registry (Task 5)
minesweeper/solver/base.py       # Move, Solver, apply_move (Task 5)
minesweeper/solver/random_solver.py
minesweeper/analysis/__init__.py
minesweeper/analysis/batch.py    # Task 7
minesweeper/analysis/__main__.py # Task 7
minesweeper/gui/__init__.py
minesweeper/gui/render.py        # pure helpers (Task 8)
minesweeper/gui/app.py           # tkinter (Task 9)
tests/test_config.py test_board.py test_game.py test_chord.py
tests/test_solver.py test_cli.py test_batch.py test_render.py
```

Spec deviations (intentional, small):
- `Board.adjacent` is a tuple of tuples (immutable) instead of `list[list[int]]`.
- `cell_appearance(game, r, c)` derives "reveal all" from `game.status` instead of taking a `reveal_all` flag; on WON, hidden mines are drawn as flags.
- Header uses BMP symbols instead of 🙂/💣/⏱ (Tk 8.6 limitation).
- `apply_move(game, move) -> bool` added to `solver/base.py` so GUI and batch share move legality rules.
- `Game.board` and `Game.revealed_count` are public read-only properties (GUI rendering + batch stats).

---

### Task 1: Project scaffolding + `GameConfig`

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `minesweeper/__init__.py`, `minesweeper/core/__init__.py`, `minesweeper/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `FirstClick` (UNSAFE/SAFE/OPENING), `FloodFill` (BFS/DFS), `GameConfig(rows, cols, mines, first_click=OPENING, chord=True, flood_fill=BFS, seed=None)` frozen dataclass with `.density` and `GameConfig.from_density(rows, cols, density, **kw)`, `PRESETS: dict[str, GameConfig]`.

- [ ] **Step 1: Create scaffolding**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "minesweeper"
version = "0.1.0"
description = "Configurable Minesweeper with GUI, solver interface and analysis harness"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
include = ["minesweeper*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
*.egg-info/
results*.csv
```

`minesweeper/__init__.py`:
```python
"""Configurable Minesweeper: engine, GUI, solvers and analysis."""
```

`minesweeper/core/__init__.py` (empty for now; filled in Task 3):
```python
"""Pure game logic. Must not import gui, solver or analysis."""
```

- [ ] **Step 2: Write the failing tests** — `tests/test_config.py`

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'minesweeper.core.config'`

- [ ] **Step 4: Implement** — `minesweeper/core/config.py`

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore minesweeper tests/test_config.py uv.lock
git commit -m "feat: project scaffolding and GameConfig

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
(If `uv.lock` was not created, drop it from `git add`.)

---

### Task 2: `Board` and `neighbors`

**Files:**
- Create: `minesweeper/core/board.py`
- Test: `tests/test_board.py`

**Interfaces:**
- Consumes: `GameConfig` (Task 1).
- Produces: `Cell = tuple[int, int]`; `neighbors(r, c, rows, cols) -> list[Cell]` (order: row-major over dr ∈ (-1,0,1), dc ∈ (-1,0,1)); frozen `Board(rows, cols, mines: frozenset[Cell], adjacent: tuple[tuple[int, ...], ...])` with `Board.from_mines(rows, cols, mines)`, `Board.generate(config, rng, exclude=frozenset())`, `board.is_mine(cell) -> bool`.

- [ ] **Step 1: Write the failing tests** — `tests/test_board.py`

```python
import random

import pytest

from minesweeper.core.board import Board, neighbors
from minesweeper.core.config import FirstClick, GameConfig


def test_neighbors_corner_edge_centre():
    assert neighbors(0, 0, 3, 3) == [(0, 1), (1, 0), (1, 1)]
    assert len(neighbors(0, 1, 3, 3)) == 5
    assert len(neighbors(1, 1, 3, 3)) == 8
    assert neighbors(0, 0, 1, 1) == []


def test_neighbors_order_is_row_major():
    assert neighbors(1, 1, 3, 3) == [
        (0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2),
    ]


def test_from_mines_adjacency():
    # . * .
    # . . .
    # * . .      (a mine's own count ignores itself)
    board = Board.from_mines(3, 3, [(0, 1), (2, 0)])
    assert board.adjacent == ((1, 0, 1), (2, 2, 1), (0, 1, 0))
    assert board.is_mine((0, 1))
    assert not board.is_mine((1, 1))


def test_from_mines_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="out of bounds"):
        Board.from_mines(3, 3, [(3, 0)])


def test_generate_places_exact_count():
    cfg = GameConfig(9, 9, 10)
    board = Board.generate(cfg, random.Random(1))
    assert len(board.mines) == 10
    assert all(0 <= r < 9 and 0 <= c < 9 for r, c in board.mines)


def test_generate_same_seed_same_board():
    cfg = GameConfig(16, 30, 99)
    a = Board.generate(cfg, random.Random(42))
    b = Board.generate(cfg, random.Random(42))
    c = Board.generate(cfg, random.Random(43))
    assert a.mines == b.mines
    assert a.mines != c.mines


def test_generate_respects_exclusion():
    cfg = GameConfig(5, 5, 16)
    exclude = {(2, 2), *neighbors(2, 2, 5, 5)}
    for seed in range(50):
        board = Board.generate(cfg, random.Random(seed), exclude)
        assert not board.mines & exclude


def test_generate_rejects_when_not_enough_room():
    cfg = GameConfig(3, 3, 9, first_click=FirstClick.UNSAFE)
    with pytest.raises(ValueError, match="not enough"):
        Board.generate(cfg, random.Random(0), {(0, 0)})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_board.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.core.board'`

- [ ] **Step 3: Implement** — `minesweeper/core/board.py`

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_board.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/core/board.py tests/test_board.py
git commit -m "feat: Board generation and neighbour helper

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `Game` — reveal, flood fill, flags, first-click rules, win/lose, stats, `PlayerView`

**Files:**
- Create: `minesweeper/core/game.py`
- Modify: `minesweeper/core/__init__.py` (re-exports)
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: `GameConfig`, `FirstClick`, `FloodFill` (Task 1); `Board`, `Cell`, `neighbors` (Task 2).
- Produces:
  - `CellState` (HIDDEN/FLAGGED/REVEALED), `Status` (READY/PLAYING/WON/LOST)
  - `RevealResult(revealed: tuple[Cell, ...], hit_mine: Cell | None, status: Status)` frozen
  - `GameStats(clicks=0, flags=0, start_time=None, end_time=None)` with `.elapsed -> float` seconds
  - `PlayerView(rows, cols, total_mines, cells: tuple[tuple[int | None, ...], ...], flags: frozenset[Cell], status)` frozen, with `.number(cell) -> int | None`, `.is_hidden(cell) -> bool` (unrevealed and unflagged), `.hidden_cells() -> list[Cell]`, `.neighbors(cell) -> list[Cell]`
  - `Game(config, board=None)` with attributes `config`, `seed: int`, `rows`, `cols`, `status`, `stats`, `flags_placed`; properties `board -> Board | None`, `revealed_count -> int`, `mines_remaining -> int`, `is_over -> bool`; methods `state(r, c) -> CellState`, `number(r, c) -> int | None`, `reveal(r, c) -> RevealResult`, `toggle_flag(r, c) -> bool`, `view() -> PlayerView`. (`chord` added in Task 4.)
  - Internal helper used by Task 4: `self._open(starts: list[Cell]) -> RevealResult`.

- [ ] **Step 1: Write the failing tests** — `tests/test_game.py`

```python
import pytest

from minesweeper.core.board import Board, neighbors
from minesweeper.core.config import FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, Status


def make_game(rows, cols, mines, **kw) -> Game:
    """Game on a fixed, hand-made layout."""
    kw.setdefault("first_click", FirstClick.UNSAFE)
    cfg = GameConfig(rows, cols, len(mines), **kw)
    return Game(cfg, board=Board.from_mines(rows, cols, mines))


# Layout used by several tests (1 row, mine at the right end):
#   0 0 0 0 1 *
def strip_game(**kw) -> Game:
    return make_game(1, 6, [(0, 5)], **kw)


def test_initial_state():
    g = strip_game()
    assert g.status is Status.READY
    assert all(g.state(0, c) is CellState.HIDDEN for c in range(6))
    assert g.mines_remaining == 1
    assert g.revealed_count == 0


def test_reveal_number_reveals_only_that_cell():
    g = strip_game()
    res = g.reveal(0, 4)
    assert res.revealed == ((0, 4),)
    assert g.number(0, 4) == 1
    assert g.status is Status.PLAYING


def test_bfs_order():
    g = strip_game(flood_fill=FloodFill.BFS)
    res = g.reveal(0, 2)
    assert res.revealed == ((0, 2), (0, 1), (0, 3), (0, 0), (0, 4))


def test_dfs_order():
    g = strip_game(flood_fill=FloodFill.DFS)
    res = g.reveal(0, 2)
    assert res.revealed == ((0, 2), (0, 3), (0, 4), (0, 1), (0, 0))


def test_flood_fill_reaches_win():
    g = strip_game()
    res = g.reveal(0, 0)
    assert set(res.revealed) == {(0, c) for c in range(5)}
    assert res.status is Status.WON
    assert g.is_over


def test_bfs_and_dfs_reveal_same_set_on_random_boards():
    for seed in range(30):
        results = []
        for ff in FloodFill:
            g = Game(GameConfig(16, 16, 40, flood_fill=ff, seed=seed))
            results.append(set(g.reveal(8, 8).revealed))
        assert results[0] == results[1]


def test_flags_block_flood_fill():
    g = strip_game()
    assert g.toggle_flag(0, 1)
    res = g.reveal(0, 3)
    assert (0, 1) not in res.revealed and (0, 0) not in res.revealed
    assert g.state(0, 1) is CellState.FLAGGED
    assert g.status is Status.PLAYING


def test_reveal_mine_loses():
    g = strip_game()
    res = g.reveal(0, 5)
    assert res.hit_mine == (0, 5)
    assert res.status is Status.LOST
    assert g.state(0, 5) is CellState.REVEALED
    assert g.number(0, 5) is None


def test_left_click_on_flag_is_noop():  # Review Focus 1
    g = strip_game()
    g.toggle_flag(0, 5)
    res = g.reveal(0, 5)
    assert res.revealed == () and res.hit_mine is None
    assert g.status is Status.READY


def test_reveal_revealed_cell_is_noop():
    g = strip_game()
    g.reveal(0, 4)
    assert g.reveal(0, 4).revealed == ()


def test_actions_after_game_over_are_noops():  # Review Focus 5
    g = strip_game()
    g.reveal(0, 5)
    assert g.reveal(0, 0).revealed == ()
    assert g.toggle_flag(0, 0) is False
    assert g.status is Status.LOST


def test_out_of_bounds_raises_index_error():
    g = strip_game()
    with pytest.raises(IndexError):
        g.reveal(1, 0)
    with pytest.raises(IndexError):
        g.toggle_flag(0, -1)


def test_toggle_flag_counts():
    g = strip_game()
    assert g.toggle_flag(0, 0) and g.toggle_flag(0, 1)
    assert g.mines_remaining == -1  # may go negative
    assert g.toggle_flag(0, 0)
    assert g.state(0, 0) is CellState.HIDDEN
    assert g.flags_placed == 1
    assert g.stats.flags == 3
    assert g.status is Status.READY  # flagging does not start the game


def test_cannot_flag_revealed_cell():
    g = strip_game()
    g.reveal(0, 4)
    assert g.toggle_flag(0, 4) is False


def test_safe_first_click_never_mine():
    for seed in range(200):
        g = Game(GameConfig(3, 3, 8, first_click=FirstClick.SAFE, seed=seed))
        res = g.reveal(1, 1)
        assert res.hit_mine is None
        assert g.status is Status.WON  # only one safe cell on the board


@pytest.mark.parametrize("cell", [(0, 0), (0, 2), (4, 4), (2, 2), (4, 0)])
def test_opening_first_click_is_zero_even_at_max_density(cell):  # Review Focus 2
    for seed in range(50):
        g = Game(GameConfig(5, 5, 16, seed=seed))
        res = g.reveal(*cell)
        assert res.hit_mine is None
        assert g.number(*cell) == 0
        assert set(neighbors(*cell, 5, 5)) <= set(res.revealed)


def test_unsafe_board_exists_before_first_click():
    g = Game(GameConfig(5, 5, 3, first_click=FirstClick.UNSAFE, seed=1))
    assert g.board is not None


def test_board_generated_lazily_for_safe_rules():
    g = Game(GameConfig(5, 5, 3, seed=1))
    assert g.board is None
    g.reveal(2, 2)
    assert g.board is not None


def test_seed_recorded_when_not_given():
    g = Game(GameConfig(5, 5, 3))
    assert isinstance(g.seed, int)
    replay = Game(GameConfig(5, 5, 3, seed=g.seed))
    g.reveal(2, 2)
    replay.reveal(2, 2)
    assert g.board.mines == replay.board.mines


def test_injected_board_must_match_config():
    with pytest.raises(ValueError):
        Game(GameConfig(5, 5, 3), board=Board.from_mines(5, 5, [(0, 0)]))


def test_stats():
    g = strip_game()
    assert g.stats.elapsed == 0.0
    g.reveal(0, 4)
    g.reveal(0, 4)  # no-op, not counted
    assert g.stats.clicks == 1
    assert g.stats.start_time is not None
    g.reveal(0, 0)
    assert g.stats.end_time is not None
    assert g.stats.elapsed >= 0


def test_view_hides_mines():
    g = strip_game()
    g.toggle_flag(0, 5)
    g.reveal(0, 4)
    v = g.view()
    assert v.cells == ((None, None, None, None, 1, None),)
    assert v.flags == frozenset({(0, 5)})
    assert v.total_mines == 1
    assert v.number((0, 4)) == 1
    assert v.is_hidden((0, 0)) and not v.is_hidden((0, 5)) and not v.is_hidden((0, 4))
    assert v.hidden_cells() == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert v.neighbors((0, 0)) == [(0, 1)]
    assert not hasattr(v, "mines") and not hasattr(v, "board")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_game.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.core.game'`

- [ ] **Step 3: Implement** — `minesweeper/core/game.py`

```python
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
```

`minesweeper/core/__init__.py`:
```python
"""Pure game logic. Must not import gui, solver or analysis."""
from minesweeper.core.board import Board, Cell, neighbors
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, GameStats, PlayerView, RevealResult, Status

__all__ = [
    "Board", "Cell", "neighbors",
    "PRESETS", "FirstClick", "FloodFill", "GameConfig",
    "CellState", "Game", "GameStats", "PlayerView", "RevealResult", "Status",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS (config, board, game)

- [ ] **Step 5: Commit**

```bash
git add minesweeper/core tests/test_game.py
git commit -m "feat: Game rules with BFS/DFS flood fill, flags and first-click rules

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Chord

**Files:**
- Modify: `minesweeper/core/game.py` (add `chord` method to `Game`, in the "actions" section after `toggle_flag`)
- Test: `tests/test_chord.py`

**Interfaces:**
- Consumes: `Game._open`, `Game._nothing`, `neighbors` (Task 3).
- Produces: `Game.chord(r, c) -> RevealResult`.

- [ ] **Step 1: Write the failing tests** — `tests/test_chord.py`

```python
import pytest

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import CellState, Game, Status


def make_game(rows, cols, mines, **kw) -> Game:
    kw.setdefault("first_click", FirstClick.UNSAFE)
    cfg = GameConfig(rows, cols, len(mines), **kw)
    return Game(cfg, board=Board.from_mines(rows, cols, mines))


# 3x3, one mine top-left:
#   * 1 0
#   1 1 0
#   0 0 0
def corner_game(**kw) -> Game:
    return make_game(3, 3, [(0, 0)], **kw)


def test_chord_reveals_unflagged_neighbours():
    g = make_game(3, 4, [(0, 0), (2, 3)])
    g.reveal(1, 1)                      # number 1
    g.toggle_flag(0, 0)
    res = g.chord(1, 1)
    # every unflagged neighbour opens; zeros among them keep flood-filling
    assert {(0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)} <= set(res.revealed)
    assert g.state(0, 0) is CellState.FLAGGED
    assert g.stats.clicks == 2


def test_chord_refused_when_flag_count_differs():
    g = corner_game()
    g.reveal(1, 1)
    assert g.chord(1, 1).revealed == ()  # 0 flags, number is 1


def test_chord_refused_on_hidden_cell():
    g = corner_game()
    g.reveal(1, 1)
    assert g.chord(2, 2).revealed == ()


def test_chord_disabled_by_config():
    g = corner_game(chord=False)
    g.reveal(1, 1)
    g.toggle_flag(0, 0)
    assert g.chord(1, 1).revealed == ()
    assert g.status is Status.PLAYING


def test_chord_with_wrong_flag_loses():
    g = corner_game()
    g.reveal(1, 1)
    g.toggle_flag(0, 1)                 # wrong flag
    res = g.chord(1, 1)
    assert res.hit_mine == (0, 0)
    assert g.status is Status.LOST


def test_chord_can_win():  # Review Focus 3
    g = corner_game()
    g.reveal(1, 1)
    g.toggle_flag(0, 0)
    res = g.chord(1, 1)
    assert res.status is Status.WON
    assert g.revealed_count == 8


def test_chord_after_game_over_is_noop():
    g = corner_game()
    g.reveal(1, 1)
    g.reveal(0, 0)
    assert g.chord(1, 1).revealed == ()


def test_chord_out_of_bounds():
    with pytest.raises(IndexError):
        corner_game().chord(5, 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_chord.py -v`
Expected: FAIL — `AttributeError: 'Game' object has no attribute 'chord'`

- [ ] **Step 3: Implement** — add to `Game` in `minesweeper/core/game.py`, directly after `toggle_flag`:

```python
    def chord(self, r: int, c: int) -> RevealResult:
        """On a revealed number whose flagged neighbours equal it, reveal the rest."""
        self._check(r, c)
        if not self.config.chord or self.is_over or self._state[r][c] is not CellState.REVEALED:
            return self._nothing()
        around = neighbors(r, c, self.rows, self.cols)
        flagged = sum(self._state[nr][nc] is CellState.FLAGGED for nr, nc in around)
        hidden = [(nr, nc) for nr, nc in around if self._state[nr][nc] is CellState.HIDDEN]
        if flagged != self._board.adjacent[r][c] or not hidden:
            return self._nothing()
        result = self._open(hidden)
        self.stats.clicks += 1
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/core/game.py tests/test_chord.py
git commit -m "feat: configurable chord action

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Solver interface, `apply_move`, random baseline

**Files:**
- Create: `minesweeper/solver/__init__.py`, `minesweeper/solver/base.py`, `minesweeper/solver/random_solver.py`
- Test: `tests/test_solver.py`

**Interfaces:**
- Consumes: `Game`, `PlayerView`, `CellState`, `Cell` (Task 3).
- Produces:
  - `Move(action: Literal["reveal", "flag"], cell: Cell, reason: str, certain: bool)` frozen
  - `Solver` Protocol: class attr `name: str`; `__init__(self, rng: random.Random)`; `next_move(self, view: PlayerView) -> Move`
  - `apply_move(game: Game, move: Move) -> bool` — True if applied; False if illegal (out of bounds, reveal on non-hidden cell, flag on revealed cell, unknown action, game over)
  - `RandomSolver` (`name = "random"`)
  - `SOLVERS: dict[str, type[Solver]]` = `{"random": RandomSolver}`

- [ ] **Step 1: Write the failing tests** — `tests/test_solver.py`

```python
import random

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import CellState, Game, Status
from minesweeper.solver import SOLVERS
from minesweeper.solver.base import Move, apply_move
from minesweeper.solver.random_solver import RandomSolver


def strip_game() -> Game:  # 0 0 0 0 1 *
    cfg = GameConfig(1, 6, 1, first_click=FirstClick.UNSAFE)
    return Game(cfg, board=Board.from_mines(1, 6, [(0, 5)]))


def test_registry():
    assert SOLVERS["random"] is RandomSolver
    assert RandomSolver.name == "random"


def test_random_solver_only_picks_hidden_unflagged():
    g = strip_game()
    g.reveal(0, 4)
    g.toggle_flag(0, 0)
    solver = RandomSolver(random.Random(0))
    picks = {solver.next_move(g.view()).cell for _ in range(200)}
    assert picks == {(0, 1), (0, 2), (0, 3), (0, 5)}


def test_random_solver_move_shape():
    move = RandomSolver(random.Random(0)).next_move(strip_game().view())
    assert move.action == "reveal"
    assert move.certain is False
    assert move.reason == "random pick"


def test_random_solver_deterministic_with_seed():
    view = Game(GameConfig(9, 9, 10, seed=3)).view()
    a = [RandomSolver(random.Random(5)).next_move(view).cell for _ in range(3)]
    b = [RandomSolver(random.Random(5)).next_move(view).cell for _ in range(3)]
    assert a == b


def test_apply_move_reveal_and_flag():
    g = strip_game()
    assert apply_move(g, Move("reveal", (0, 4), "", True))
    assert g.state(0, 4) is CellState.REVEALED
    assert apply_move(g, Move("flag", (0, 5), "", True))
    assert g.state(0, 5) is CellState.FLAGGED


def test_apply_move_rejects_illegal():
    g = strip_game()
    g.reveal(0, 4)
    assert not apply_move(g, Move("reveal", (0, 4), "", True))   # already revealed
    assert not apply_move(g, Move("flag", (0, 4), "", True))     # revealed
    assert not apply_move(g, Move("reveal", (3, 3), "", True))   # out of bounds
    assert not apply_move(g, Move("dance", (0, 0), "", True))    # type: ignore[arg-type]
    g.toggle_flag(0, 0)
    assert not apply_move(g, Move("reveal", (0, 0), "", True))   # flagged


def test_apply_move_after_game_over():
    g = strip_game()
    g.reveal(0, 5)
    assert g.status is Status.LOST
    assert not apply_move(g, Move("reveal", (0, 0), "", True))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_solver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.solver'`

- [ ] **Step 3: Implement**

`minesweeper/solver/base.py`:
```python
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
```

`minesweeper/solver/random_solver.py`:
```python
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
```

`minesweeper/solver/__init__.py`:
```python
"""Solvers. Each sees only a PlayerView, never the mine layout."""
from minesweeper.solver.base import Move, Solver, apply_move
from minesweeper.solver.random_solver import RandomSolver

SOLVERS: dict[str, type[Solver]] = {
    RandomSolver.name: RandomSolver,
}

__all__ = ["SOLVERS", "Move", "Solver", "apply_move", "RandomSolver"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/solver tests/test_solver.py
git commit -m "feat: solver interface, apply_move and random baseline

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Shared CLI arguments → `GameConfig`

**Files:**
- Create: `minesweeper/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `GameConfig`, `PRESETS`, `FirstClick`, `FloodFill` (Task 1).
- Produces:
  - `parse_density(text: str) -> list[float]` — `"0.15"` → `[0.15]`; `"0.10:0.25:0.03"` → `[0.1, 0.13, 0.16, 0.19, 0.22, 0.25]` (stop inclusive); raises `argparse.ArgumentTypeError` on bad input
  - `add_game_args(parser: argparse.ArgumentParser, *, multi: bool) -> None` — adds `--preset` (append if `multi`), `--rows`, `--cols`, `--mines`, `--density`, `--first-click`, `--no-chord`, `--flood-fill`, `--seed`
  - `configs_from_args(args) -> list[GameConfig]` — raises `ValueError` with a readable message on conflicting/invalid options. No size options → beginner size.

- [ ] **Step 1: Write the failing tests** — `tests/test_cli.py`

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.cli'`

- [ ] **Step 3: Implement** — `minesweeper/cli.py`

```python
"""Command-line options shared by the GUI and the batch runner."""
from __future__ import annotations

import argparse

from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig

_DEFAULT_SIZE = PRESETS["beginner"]


def parse_density(text: str) -> list[float]:
    """'0.15' → [0.15]; 'start:stop:step' → inclusive range."""
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid density {text!r}") from None
    if len(parts) == 1:
        return parts
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("density range must be start:stop:step")
    start, stop, step = parts
    if step <= 0 or stop < start:
        raise argparse.ArgumentTypeError("density range needs step > 0 and stop >= start")
    values = []
    i = 0
    while (value := round(start + i * step, 10)) <= stop + 1e-9:
        values.append(value)
        i += 1
    return values


def add_game_args(parser: argparse.ArgumentParser, *, multi: bool) -> None:
    board = parser.add_argument_group("board")
    board.add_argument(
        "--preset",
        choices=list(PRESETS),
        action="append" if multi else "store",
        help="board preset" + (" (repeatable)" if multi else ""),
    )
    board.add_argument("--rows", type=int)
    board.add_argument("--cols", type=int)
    board.add_argument("--mines", type=int)
    board.add_argument(
        "--density", type=parse_density, help="mine density, e.g. 0.15 or 0.10:0.25:0.03"
    )
    rules = parser.add_argument_group("rules")
    rules.add_argument(
        "--first-click", choices=[f.name for f in FirstClick], default=FirstClick.OPENING.name
    )
    rules.add_argument("--no-chord", action="store_true", help="disable chording")
    rules.add_argument(
        "--flood-fill", choices=[f.name for f in FloodFill], default=FloodFill.BFS.name
    )
    rules.add_argument("--seed", type=int)


def configs_from_args(args: argparse.Namespace) -> list[GameConfig]:
    rules = dict(
        first_click=FirstClick[args.first_click],
        chord=not args.no_chord,
        flood_fill=FloodFill[args.flood_fill],
        seed=args.seed,
    )
    presets = args.preset if isinstance(args.preset, list) else [args.preset] if args.preset else []
    if args.mines is not None and args.density is not None:
        raise ValueError("use either --mines or --density, not both")

    if presets:
        if args.rows is not None or args.cols is not None:
            raise ValueError("use either --preset or --rows/--cols, not both")
        sizes = [(PRESETS[p].rows, PRESETS[p].cols, PRESETS[p].mines) for p in presets]
    elif args.rows is not None and args.cols is not None:
        if args.mines is None and args.density is None:
            raise ValueError("--rows/--cols need --mines or --density")
        sizes = [(args.rows, args.cols, args.mines)]
    elif args.rows is None and args.cols is None:
        sizes = [(_DEFAULT_SIZE.rows, _DEFAULT_SIZE.cols, _DEFAULT_SIZE.mines)]
    else:
        raise ValueError("--rows and --cols must be given together")

    configs = []
    for rows, cols, mines in sizes:
        if args.density is not None:
            configs += [GameConfig.from_density(rows, cols, d, **rules) for d in args.density]
        else:
            configs.append(
                GameConfig(rows, cols, args.mines if args.mines is not None else mines, **rules)
            )
    return configs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/cli.py tests/test_cli.py
git commit -m "feat: shared CLI options to build GameConfigs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Batch runner, CSV, summary, analysis CLI

**Files:**
- Create: `minesweeper/analysis/__init__.py`, `minesweeper/analysis/batch.py`, `minesweeper/analysis/__main__.py`
- Test: `tests/test_batch.py`

**Interfaces:**
- Consumes: `Game`, `Status` (Task 3); `SOLVERS`, `Solver`, `apply_move`, `Move` (Task 5); `add_game_args`, `configs_from_args` (Task 6).
- Produces:
  - `GameRecord` frozen dataclass, fields in CSV order: `seed, rows, cols, mines, density, first_click, chord, flood_fill, solver, result, moves, guesses, cells_revealed, time_ms`
  - `CSV_FIELDS: list[str]`
  - `run_game(config: GameConfig, solver_cls: type[Solver]) -> GameRecord` — `config.seed` must be set
  - `run_batch(configs, solver_name: str, games: int, base_seed: int) -> list[GameRecord]`
  - `write_csv(records, file: TextIO) -> None`
  - `wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]`
  - `Summary` dataclass + `summarize(records) -> list[Summary]`, `format_summary(summaries) -> str`
  - `main(argv: list[str] | None = None) -> int` in `analysis/__main__.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_batch.py`

```python
import csv
import io
import random

import pytest

from minesweeper.analysis.__main__ import main
from minesweeper.analysis.batch import (
    CSV_FIELDS,
    format_summary,
    run_batch,
    run_game,
    summarize,
    wilson_interval,
    write_csv,
)
from minesweeper.core.config import GameConfig
from minesweeper.solver.base import Move
from minesweeper.solver.random_solver import RandomSolver


def test_run_game_record_fields():
    rec = run_game(GameConfig(9, 9, 10, seed=3), RandomSolver)
    assert rec.seed == 3 and (rec.rows, rec.cols, rec.mines) == (9, 9, 10)
    assert rec.first_click == "OPENING" and rec.flood_fill == "BFS" and rec.chord is True
    assert rec.solver == "random"
    assert rec.result in {"won", "lost"}
    assert rec.moves >= 1 and rec.guesses == rec.moves
    assert rec.cells_revealed >= 1
    assert rec.time_ms >= 0


def test_run_game_requires_seed():
    with pytest.raises(ValueError, match="seed"):
        run_game(GameConfig(9, 9, 10), RandomSolver)


def test_batch_is_reproducible():
    cfgs = [GameConfig(9, 9, 10)]
    a = run_batch(cfgs, "random", games=20, base_seed=100)
    b = run_batch(cfgs, "random", games=20, base_seed=100)
    strip = lambda recs: [r.__dict__ | {"time_ms": 0} for r in recs]
    assert strip(a) == strip(b)
    assert [r.seed for r in a] == list(range(100, 120))


def test_batch_cartesian_product():
    recs = run_batch([GameConfig(5, 5, 3), GameConfig(9, 9, 10)], "random", 4, 0)
    assert len(recs) == 8


class StuckSolver:
    name = "stuck"

    def __init__(self, rng: random.Random) -> None:
        pass

    def next_move(self, view):
        return Move("flag", (0, 0), "toggle forever", certain=True)


class IllegalSolver(StuckSolver):
    name = "illegal"

    def next_move(self, view):
        return Move("reveal", (99, 99), "off the board", certain=True)


class CrashingSolver(StuckSolver):
    name = "crash"

    def next_move(self, view):
        raise RuntimeError("boom")


@pytest.mark.parametrize("solver_cls", [StuckSolver, IllegalSolver, CrashingSolver])
def test_misbehaving_solvers_stall(solver_cls):
    rec = run_game(GameConfig(5, 5, 3, seed=1), solver_cls)
    assert rec.result == "stalled"
    assert rec.moves <= 5 * 5 * 2


def test_wilson_interval_known_values():
    assert wilson_interval(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert wilson_interval(0, 10) == pytest.approx((0.0, 0.2775), abs=1e-4)
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_write_csv_header_and_rows():
    recs = run_batch([GameConfig(5, 5, 3)], "random", 3, 0)
    buf = io.StringIO()
    write_csv(recs, buf)
    rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
    assert list(rows[0]) == CSV_FIELDS
    assert len(rows) == 3


def test_summarize_groups_by_config():
    recs = run_batch([GameConfig(5, 5, 3), GameConfig(9, 9, 10)], "random", 10, 0)
    summaries = summarize(recs)
    assert len(summaries) == 2
    s = summaries[0]
    assert s.games == 10
    assert s.wins == sum(r.result == "won" for r in recs[:10])
    assert s.ci_low <= s.win_rate <= s.ci_high
    text = format_summary(summaries)
    assert "5x5" in text and "9x9" in text


def test_main_writes_csv(tmp_path, capsys):
    out = tmp_path / "r.csv"
    code = main(["--preset", "tiny", "--games", "5", "--seed", "0", "--out", str(out)])
    assert code == 0
    assert len(out.read_text().splitlines()) == 6
    assert "win rate" in capsys.readouterr().out.lower()


def test_main_invalid_config_exits_2(capsys):  # Review Focus 4
    with pytest.raises(SystemExit) as exc:
        main(["--preset", "tiny", "--density", "0.9", "--games", "1"])
    assert exc.value.code == 2
    assert "too many mines" in capsys.readouterr().err


def test_main_rejects_zero_games(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--games", "0"])
    assert exc.value.code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_batch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.analysis'`

- [ ] **Step 3: Implement**

`minesweeper/analysis/__init__.py`:
```python
"""Headless batch runs for solver statistics."""
```

`minesweeper/analysis/batch.py`:
```python
"""Run many headless games and aggregate the results."""
from __future__ import annotations

import csv
import logging
import math
import random
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import TextIO

from minesweeper.core.config import GameConfig
from minesweeper.core.game import Game, Status
from minesweeper.solver import SOLVERS, Solver, apply_move

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameRecord:
    seed: int
    rows: int
    cols: int
    mines: int
    density: float
    first_click: str
    chord: bool
    flood_fill: str
    solver: str
    result: str  # won / lost / stalled
    moves: int
    guesses: int
    cells_revealed: int
    time_ms: float


CSV_FIELDS = [f.name for f in fields(GameRecord)]


def run_game(config: GameConfig, solver_cls: type[Solver]) -> GameRecord:
    if config.seed is None:
        raise ValueError("run_game needs config.seed for reproducibility")
    game = Game(config)
    solver = solver_cls(random.Random(config.seed))
    limit = config.rows * config.cols * 2
    moves = guesses = 0
    result = None
    start = time.perf_counter()
    while not game.is_over:
        if moves >= limit:
            log.warning("seed %s: %s exceeded %d moves", config.seed, solver_cls.name, limit)
            result = "stalled"
            break
        try:
            move = solver.next_move(game.view())
        except Exception:
            log.warning("seed %s: %s raised", config.seed, solver_cls.name, exc_info=True)
            result = "stalled"
            break
        if not apply_move(game, move):
            log.warning("seed %s: illegal move %s", config.seed, move)
            result = "stalled"
            break
        moves += 1
        guesses += not move.certain
    elapsed_ms = (time.perf_counter() - start) * 1000
    if result is None:
        result = "won" if game.status is Status.WON else "lost"
    return GameRecord(
        seed=config.seed,
        rows=config.rows,
        cols=config.cols,
        mines=config.mines,
        density=round(config.density, 4),
        first_click=config.first_click.name,
        chord=config.chord,
        flood_fill=config.flood_fill.name,
        solver=solver_cls.name,
        result=result,
        moves=moves,
        guesses=guesses,
        cells_revealed=game.revealed_count,
        time_ms=round(elapsed_ms, 3),
    )


def run_batch(
    configs: Iterable[GameConfig], solver_name: str, games: int, base_seed: int
) -> list[GameRecord]:
    solver_cls = SOLVERS[solver_name]
    return [
        run_game(replace(config, seed=base_seed + i), solver_cls)
        for config in configs
        for i in range(games)
    ]


def write_csv(records: Iterable[GameRecord], file: TextIO) -> None:
    writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for record in records:
        writer.writerow(asdict(record))


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a win rate (Wilson score interval)."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass(frozen=True)
class Summary:
    label: str
    games: int
    wins: int
    stalled: int
    win_rate: float
    ci_low: float
    ci_high: float
    mean_moves: float
    mean_guesses: float
    mean_time_ms: float


def summarize(records: Sequence[GameRecord]) -> list[Summary]:
    groups: dict[tuple, list[GameRecord]] = {}
    for r in records:
        key = (r.rows, r.cols, r.mines, r.first_click, r.chord, r.flood_fill, r.solver)
        groups.setdefault(key, []).append(r)
    summaries = []
    for (rows, cols, mines, first, chord, flood, solver), recs in groups.items():
        n = len(recs)
        wins = sum(r.result == "won" for r in recs)
        low, high = wilson_interval(wins, n)
        summaries.append(
            Summary(
                label=(
                    f"{rows}x{cols} {mines} mines ({mines / (rows * cols):.1%}) "
                    f"{first} chord={'on' if chord else 'off'} {flood} [{solver}]"
                ),
                games=n,
                wins=wins,
                stalled=sum(r.result == "stalled" for r in recs),
                win_rate=wins / n,
                ci_low=low,
                ci_high=high,
                mean_moves=sum(r.moves for r in recs) / n,
                mean_guesses=sum(r.guesses for r in recs) / n,
                mean_time_ms=sum(r.time_ms for r in recs) / n,
            )
        )
    return summaries


def format_summary(summaries: Iterable[Summary]) -> str:
    lines = []
    for s in summaries:
        lines.append(s.label)
        lines.append(
            f"  games={s.games} win rate={s.win_rate:.1%} "
            f"(95% CI {s.ci_low:.1%}-{s.ci_high:.1%}) stalled={s.stalled}"
        )
        lines.append(
            f"  mean moves={s.mean_moves:.1f} guesses={s.mean_guesses:.1f} "
            f"time={s.mean_time_ms:.2f} ms"
        )
    return "\n".join(lines)
```

`minesweeper/analysis/__main__.py`:
```python
"""python -m minesweeper.analysis — run headless games and report statistics."""
from __future__ import annotations

import argparse
import sys

from minesweeper.analysis.batch import format_summary, run_batch, summarize, write_csv
from minesweeper.cli import add_game_args, configs_from_args
from minesweeper.solver import SOLVERS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m minesweeper.analysis",
        description="Run many headless games with a solver and summarise the results.",
    )
    add_game_args(parser, multi=True)
    parser.add_argument("--solver", choices=list(SOLVERS), default="random")
    parser.add_argument("--games", type=int, default=100, help="games per configuration")
    parser.add_argument("--out", help="write per-game rows to this CSV file")
    args = parser.parse_args(argv)
    if args.games < 1:
        parser.error("--games must be at least 1")
    try:
        configs = configs_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    base_seed = args.seed if args.seed is not None else 0
    records = run_batch(configs, args.solver, args.games, base_seed)
    if args.out:
        with open(args.out, "w", newline="") as f:
            write_csv(records, f)
    print(format_summary(summarize(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Smoke-run the CLI**

Run: `uv run python -m minesweeper.analysis --preset tiny --preset beginner --games 200 --seed 0`
Expected: two summary blocks with win rates; no traceback.

- [ ] **Step 6: Commit**

```bash
git add minesweeper/analysis tests/test_batch.py
git commit -m "feat: headless batch runner with CSV output and Wilson CI summary

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: GUI pure helpers (`render.py`)

**Files:**
- Create: `minesweeper/gui/__init__.py`, `minesweeper/gui/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Game`, `CellState`, `Status` (Task 3); `Board` (Task 2).
- Produces:
  - `Appearance(text: str, fg: str, bg: str, raised: bool)` frozen
  - `cell_appearance(game: Game, r: int, c: int) -> Appearance`
  - `pixel_to_cell(x: float, y: float, cell_size: int, rows: int, cols: int) -> Cell | None`
  - `cell_size_for(rows, cols, max_w, max_h) -> int` — clamp(min(max_w // cols, max_h // rows), 16, 40)
  - Constants: `FLAG = "⚑"`, `MINE = "✹"`, `WRONG_FLAG = "✗"`, `FACES = {Status.READY: "☺", Status.PLAYING: "☺", Status.WON: "✌", Status.LOST: "☹"}`, `NUMBER_COLORS`, `HIDDEN_BG`, `REVEALED_BG`, `HIT_BG`

- [ ] **Step 1: Write the failing tests** — `tests/test_render.py`

```python
import pytest

from minesweeper.core.board import Board
from minesweeper.core.config import FirstClick, GameConfig
from minesweeper.core.game import Game
from minesweeper.gui.render import (
    FLAG,
    HIDDEN_BG,
    HIT_BG,
    MINE,
    NUMBER_COLORS,
    REVEALED_BG,
    WRONG_FLAG,
    cell_appearance,
    cell_size_for,
    pixel_to_cell,
)


def game_3x3() -> Game:
    #   * 1 0
    #   1 1 0
    #   0 0 0
    cfg = GameConfig(3, 3, 1, first_click=FirstClick.UNSAFE)
    return Game(cfg, board=Board.from_mines(3, 3, [(0, 0)]))


def test_hidden_cell():
    a = cell_appearance(game_3x3(), 1, 1)
    assert (a.text, a.bg, a.raised) == ("", HIDDEN_BG, True)


def test_revealed_number_and_blank():
    g = game_3x3()
    g.reveal(1, 1)
    a = cell_appearance(g, 1, 1)
    assert (a.text, a.fg, a.bg, a.raised) == ("1", NUMBER_COLORS[1], REVEALED_BG, False)
    g.reveal(2, 2)
    assert cell_appearance(g, 2, 2).text == ""


def test_flag():
    g = game_3x3()
    g.toggle_flag(0, 0)
    assert cell_appearance(g, 0, 0).text == FLAG


def test_lost_shows_mines_hit_and_wrong_flags():
    cfg = GameConfig(3, 3, 2, first_click=FirstClick.UNSAFE)
    g = Game(cfg, board=Board.from_mines(3, 3, [(0, 0), (2, 2)]))
    g.toggle_flag(1, 1)  # wrong flag
    g.reveal(0, 0)       # hit
    hit = cell_appearance(g, 0, 0)
    assert (hit.text, hit.bg) == (MINE, HIT_BG)
    other = cell_appearance(g, 2, 2)
    assert other.text == MINE and other.bg == REVEALED_BG
    assert cell_appearance(g, 1, 1).text == WRONG_FLAG


def test_won_shows_hidden_mines_as_flags():
    g = game_3x3()
    g.reveal(2, 2)
    assert g.is_over
    assert cell_appearance(g, 0, 0).text == FLAG


def test_all_numbers_have_colours():
    assert set(NUMBER_COLORS) == set(range(1, 9))


@pytest.mark.parametrize(
    "x,y,expected",
    [(0, 0, (0, 0)), (39, 39, (0, 0)), (40, 0, (0, 1)), (119, 79, (1, 2)),
     (120, 0, None), (0, 80, None), (-1, 5, None), (5, -1, None)],
)
def test_pixel_to_cell(x, y, expected):  # Review Focus 5
    assert pixel_to_cell(x, y, 40, rows=2, cols=3) == expected


def test_cell_size_clamped():
    assert cell_size_for(9, 9, 2000, 2000) == 40
    assert cell_size_for(100, 100, 1000, 1000) == 16
    assert cell_size_for(16, 30, 900, 800) == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'minesweeper.gui'`

- [ ] **Step 3: Implement**

`minesweeper/gui/__init__.py`:
```python
"""tkinter front-end."""
```

`minesweeper/gui/render.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/gui tests/test_render.py
git commit -m "feat: pure GUI rendering helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: tkinter app, GUI entry point, README

**Files:**
- Create: `minesweeper/gui/app.py`, `minesweeper/__main__.py`, `README.md`

**Interfaces:**
- Consumes: everything above — `GameConfig`, `PRESETS`, `FirstClick`, `FloodFill`, `Game`, `CellState`, `Status`, `SOLVERS`, `apply_move`, `add_game_args`, `configs_from_args`, render helpers.
- Produces: `minesweeper.gui.app.run(config: GameConfig) -> None`; `python -m minesweeper` entry (`minesweeper.__main__.main(argv=None)`).

No unit tests (widget code is kept thin; logic lives in tested modules). Verification is a headless import check plus a manual play-check.

- [ ] **Step 1: Implement** — `minesweeper/gui/app.py`

```python
"""tkinter front-end. Thin: all rules live in core, all drawing decisions in render."""
from __future__ import annotations

import random
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox

from minesweeper.core.board import Cell
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, Status
from minesweeper.gui.render import FACES, cell_appearance, cell_size_for, pixel_to_cell
from minesweeper.solver import SOLVERS, Solver, apply_move

AI_HIGHLIGHT = "#ff8c00"
GRID_LINE = "#808080"


class App:
    def __init__(self, root: tk.Tk, config: GameConfig) -> None:
        self.root = root
        self.config = config
        self.game: Game
        self.solver: Solver | None = None
        self._ai_cell: Cell | None = None
        self._auto_job: str | None = None
        self._timer_job: str | None = None
        self._rects: dict[Cell, int] = {}
        self._texts: dict[Cell, int] = {}

        root.title("Minesweeper")
        root.resizable(False, False)
        self._build_menu()
        self._build_header()
        self.canvas = tk.Canvas(root, highlightthickness=0, bg=GRID_LINE)
        self.canvas.pack(padx=8, pady=4)
        self._build_ai_panel()
        self.status_var = tk.StringVar()
        tk.Entry(
            root, textvariable=self.status_var, state="readonly", relief="flat"
        ).pack(fill="x", padx=8, pady=(0, 6))  # readonly Entry so the seed can be copied
        self._bind_mouse()
        self.new_game()

    # --- construction ----------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="New", accelerator="F2", command=self.new_game)
        presets = tk.Menu(game_menu, tearoff=0)
        for name, p in PRESETS.items():
            presets.add_command(
                label=f"{name.capitalize()} ({p.rows}x{p.cols}, {p.mines} mines)",
                command=lambda p=p: self.new_game(
                    replace(self.config, rows=p.rows, cols=p.cols, mines=p.mines, seed=None)
                ),
            )
        game_menu.add_cascade(label="Presets", menu=presets)
        game_menu.add_command(label="Custom…", command=self._custom)
        game_menu.add_separator()
        game_menu.add_command(label="Quit", command=self.root.destroy)
        menubar.add_cascade(label="Game", menu=game_menu)
        self.root.config(menu=menubar)
        self.root.bind("<F2>", lambda _e: self.new_game())

    def _build_header(self) -> None:
        header = tk.Frame(self.root)
        header.pack(fill="x", padx=8, pady=(6, 0))
        self.mines_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.face_var = tk.StringVar()
        tk.Label(header, textvariable=self.mines_var, width=10, anchor="w").pack(side="left")
        tk.Label(header, textvariable=self.time_var, width=10, anchor="e").pack(side="right")
        tk.Button(
            header, textvariable=self.face_var, font=("TkDefaultFont", 14), width=3,
            command=self.new_game,
        ).pack()

    def _build_ai_panel(self) -> None:
        panel = tk.Frame(self.root)
        panel.pack(fill="x", padx=8)
        tk.Label(panel, text="AI:").pack(side="left")
        self.solver_var = tk.StringVar(value=next(iter(SOLVERS)))
        tk.OptionMenu(
            panel, self.solver_var, *SOLVERS, command=lambda _v: self._reset_solver()
        ).pack(side="left")
        tk.Button(panel, text="Step", command=self.ai_step).pack(side="left", padx=2)
        self.auto_btn = tk.Button(panel, text="Auto", width=6, command=self.toggle_auto)
        self.auto_btn.pack(side="left", padx=2)
        self.speed = tk.Scale(
            panel, from_=50, to=1000, resolution=50, orient="horizontal",
            label="ms / move", length=140,
        )
        self.speed.set(300)
        self.speed.pack(side="left", padx=6)
        self.reason_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.reason_var, anchor="w", justify="left", wraplength=500
        ).pack(fill="x", padx=8)

    def _bind_mouse(self) -> None:
        # On macOS (aqua) right-click is Button-2 and middle-click is Button-3.
        aqua = self.root.tk.call("tk", "windowingsystem") == "aqua"
        flag_btn, chord_btn = ("<Button-2>", "<Button-3>") if aqua else ("<Button-3>", "<Button-2>")
        self.canvas.bind("<Button-1>", self._on_left)
        self.canvas.bind(flag_btn, self._on_flag)
        self.canvas.bind(chord_btn, self._on_chord)

    # --- game lifecycle ----------------------------------------------------------

    def new_game(self, config: GameConfig | None = None) -> None:
        if config is not None:
            self.config = config
        self._stop_auto()
        if self._timer_job is not None:
            self.root.after_cancel(self._timer_job)
            self._timer_job = None
        self.game = Game(self.config)
        self._reset_solver()
        self._ai_cell = None

        rows, cols = self.config.rows, self.config.cols
        self.cell_size = s = cell_size_for(
            rows, cols,
            int(self.root.winfo_screenwidth() * 0.85),
            int(self.root.winfo_screenheight() * 0.85) - 200,
        )
        self.canvas.delete("all")
        self.canvas.config(width=cols * s, height=rows * s)
        font = ("TkDefaultFont", max(8, s // 2), "bold")
        self._rects.clear()
        self._texts.clear()
        for r in range(rows):
            for c in range(cols):
                x, y = c * s, r * s
                self._rects[(r, c)] = self.canvas.create_rectangle(x, y, x + s, y + s)
                self._texts[(r, c)] = self.canvas.create_text(x + s / 2, y + s / 2, font=font)
        self._redraw_all()
        self._update_header()
        self.reason_var.set("")
        cfg = self.config
        self.status_var.set(
            f"seed={self.game.seed}   {rows}x{cols}, {cfg.mines} mines ({cfg.density:.1%})   "
            f"first click: {cfg.first_click.name}, chord {'on' if cfg.chord else 'off'}, "
            f"{cfg.flood_fill.name}"
        )

    def _custom(self) -> None:
        dialog = CustomDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self.new_game(dialog.result)

    # --- drawing -------------------------------------------------------------------

    def _draw_cell(self, cell: Cell) -> None:
        a = cell_appearance(self.game, *cell)
        highlighted = cell == self._ai_cell
        self.canvas.itemconfig(
            self._rects[cell],
            fill=a.bg,
            outline=AI_HIGHLIGHT if highlighted else ("#f4f4f4" if a.raised else GRID_LINE),
            width=3 if highlighted else 1,
        )
        self.canvas.itemconfig(self._texts[cell], text=a.text, fill=a.fg)
        if highlighted:
            self.canvas.tag_raise(self._rects[cell])
            self.canvas.tag_raise(self._texts[cell])

    def _redraw_all(self) -> None:
        for cell in self._rects:
            self._draw_cell(cell)

    def _update_header(self) -> None:
        self.mines_var.set(f"Mines: {self.game.mines_remaining}")
        self.time_var.set(f"Time: {int(self.game.stats.elapsed):03d}")
        self.face_var.set(FACES[self.game.status])

    def _tick(self) -> None:
        self._timer_job = None
        self._update_header()
        if self.game.status is Status.PLAYING:
            self._timer_job = self.root.after(250, self._tick)

    def _after_move(self, cells) -> None:
        if self.game.is_over:
            self._redraw_all()
            self._stop_auto()
        else:
            for cell in cells:
                self._draw_cell(cell)
        self._update_header()
        if self._timer_job is None and self.game.status is Status.PLAYING:
            self._tick()

    # --- mouse ---------------------------------------------------------------------

    def _cell_at(self, event: tk.Event) -> Cell | None:
        if self.game.is_over:
            return None
        return pixel_to_cell(event.x, event.y, self.cell_size, self.config.rows, self.config.cols)

    def _on_left(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is None:
            return
        if self.game.state(*cell) is CellState.REVEALED:
            result = self.game.chord(*cell)
        else:
            result = self.game.reveal(*cell)
        self._after_move(result.revealed)

    def _on_flag(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None and self.game.toggle_flag(*cell):
            self._after_move([cell])

    def _on_chord(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None:
            self._after_move(self.game.chord(*cell).revealed)

    # --- AI ------------------------------------------------------------------------

    def _reset_solver(self) -> None:
        self.solver = None  # created lazily with the game's seed on the next step

    def ai_step(self) -> bool:
        """Ask the solver for one move and apply it. Returns True if a move was made."""
        if self.game.is_over:
            return False
        if self.solver is None:
            self.solver = SOLVERS[self.solver_var.get()](random.Random(self.game.seed))
        try:
            move = self.solver.next_move(self.game.view())
        except Exception as exc:  # show solver bugs instead of crashing the GUI
            self.reason_var.set(f"solver error: {exc}")
            self._stop_auto()
            return False
        if not apply_move(self.game, move):
            self.reason_var.set(f"illegal move: {move.action} {move.cell}")
            self._stop_auto()
            return False
        self._ai_cell = move.cell
        prefix = "" if move.certain else "guess: "
        self.reason_var.set(f"{move.action} {move.cell} — {prefix}{move.reason}")
        self._redraw_all()  # a move can reveal many cells; full redraw keeps it simple
        self._after_move([])
        return True

    def toggle_auto(self) -> None:
        if self._auto_job is not None:
            self._stop_auto()
        else:
            self.auto_btn.config(text="Pause")
            self._auto_tick()

    def _auto_tick(self) -> None:
        self._auto_job = None
        if self.ai_step() and not self.game.is_over:
            self._auto_job = self.root.after(self.speed.get(), self._auto_tick)
        else:
            self._stop_auto()

    def _stop_auto(self) -> None:
        if self._auto_job is not None:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if hasattr(self, "auto_btn"):
            self.auto_btn.config(text="Auto")


class CustomDialog(tk.Toplevel):
    """Modal dialog for every GameConfig option. `result` is None if cancelled."""

    def __init__(self, parent: tk.Misc, config: GameConfig) -> None:
        super().__init__(parent)
        self.title("Custom game")
        self.transient(parent)
        self.resizable(False, False)
        self.result: GameConfig | None = None

        self.rows = tk.StringVar(value=str(config.rows))
        self.cols = tk.StringVar(value=str(config.cols))
        self.count_mode = tk.StringVar(value="mines")
        self.mines = tk.StringVar(value=str(config.mines))
        self.density = tk.StringVar(value=f"{config.density:.3f}")
        self.first_click = tk.StringVar(value=config.first_click.name)
        self.chord = tk.BooleanVar(value=config.chord)
        self.flood = tk.StringVar(value=config.flood_fill.name)
        self.seed = tk.StringVar(value="" if config.seed is None else str(config.seed))

        form = tk.Frame(self, padx=12, pady=10)
        form.pack()
        grid = dict(sticky="w", padx=4, pady=2)
        tk.Label(form, text="Rows").grid(row=0, column=0, **grid)
        tk.Entry(form, textvariable=self.rows, width=8).grid(row=0, column=1, **grid)
        tk.Label(form, text="Columns").grid(row=1, column=0, **grid)
        tk.Entry(form, textvariable=self.cols, width=8).grid(row=1, column=1, **grid)
        tk.Radiobutton(form, text="Mines", variable=self.count_mode, value="mines").grid(
            row=2, column=0, **grid)
        tk.Entry(form, textvariable=self.mines, width=8).grid(row=2, column=1, **grid)
        tk.Radiobutton(form, text="Density", variable=self.count_mode, value="density").grid(
            row=3, column=0, **grid)
        tk.Entry(form, textvariable=self.density, width=8).grid(row=3, column=1, **grid)
        tk.Label(form, text="First click").grid(row=4, column=0, **grid)
        tk.OptionMenu(form, self.first_click, *[f.name for f in FirstClick]).grid(
            row=4, column=1, **grid)
        tk.Label(form, text="Flood fill").grid(row=5, column=0, **grid)
        tk.OptionMenu(form, self.flood, *[f.name for f in FloodFill]).grid(
            row=5, column=1, **grid)
        tk.Checkbutton(form, text="Allow chord", variable=self.chord).grid(
            row=6, column=0, columnspan=2, **grid)
        tk.Label(form, text="Seed (blank = random)").grid(row=7, column=0, **grid)
        tk.Entry(form, textvariable=self.seed, width=12).grid(row=7, column=1, **grid)

        buttons = tk.Frame(self, pady=6)
        buttons.pack()
        tk.Button(buttons, text="OK", width=8, command=self._ok).pack(side="left", padx=4)
        tk.Button(buttons, text="Cancel", width=8, command=self.destroy).pack(side="left", padx=4)
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def _ok(self) -> None:
        try:
            rows, cols = int(self.rows.get()), int(self.cols.get())
            seed_text = self.seed.get().strip()
            rules = dict(
                first_click=FirstClick[self.first_click.get()],
                chord=self.chord.get(),
                flood_fill=FloodFill[self.flood.get()],
                seed=int(seed_text) if seed_text else None,
            )
            if self.count_mode.get() == "mines":
                config = GameConfig(rows, cols, int(self.mines.get()), **rules)
            else:
                config = GameConfig.from_density(rows, cols, float(self.density.get()), **rules)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self)
            return
        self.result = config
        self.destroy()


def run(config: GameConfig) -> None:
    root = tk.Tk()
    App(root, config)
    root.mainloop()
```

- [ ] **Step 2: Implement** — `minesweeper/__main__.py`

```python
"""python -m minesweeper — play in the GUI."""
from __future__ import annotations

import argparse

from minesweeper.cli import add_game_args, configs_from_args


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m minesweeper", description="Play Minesweeper.")
    add_game_args(parser, multi=False)
    args = parser.parse_args(argv)
    try:
        configs = configs_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))
    if len(configs) != 1:
        parser.error("the GUI takes a single --density value, not a range")

    from minesweeper.gui.app import run  # import tkinter only when actually launching

    run(configs[0])


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `README.md`**

````markdown
# Minesweeper

Configurable Minesweeper with a tkinter GUI, a solver interface, and a headless
batch runner for statistics. Standard library only.

## Play

```bash
python -m minesweeper                       # beginner 9x9, 10 mines
python -m minesweeper --preset expert
python -m minesweeper --rows 12 --cols 20 --density 0.18 --first-click SAFE --seed 42
```

Left-click reveals, right-click flags, left-click on a number (or middle-click)
chords. *Game ▸ Custom…* exposes every option. The status bar shows the seed
so any board can be replayed with `--seed`.

AI panel: pick a solver, **Step** makes one move (the cell is outlined and the
reason shown), **Auto** keeps stepping at the chosen speed.

## Options

| Option | Values | Default |
|---|---|---|
| `--preset` | tiny (5x5/3), beginner (9x9/10), intermediate (16x16/40), expert (16x30/99) | beginner |
| `--rows --cols` + `--mines` or `--density` | custom size | — |
| `--first-click` | `UNSAFE` (can lose), `SAFE` (cell safe), `OPENING` (cell + neighbours safe) | `OPENING` |
| `--no-chord` | disable chording | chord on |
| `--flood-fill` | `BFS`, `DFS` | `BFS` |
| `--seed` | integer | random |

## Batch analysis

```bash
python -m minesweeper.analysis --solver random --preset tiny --preset beginner \
    --games 1000 --seed 0 --out results.csv
python -m minesweeper.analysis --preset beginner --density 0.10:0.25:0.03 --games 500
```

Game *i* uses seed `--seed + i`, so runs are reproducible. Prints win rate
(95% Wilson CI), mean moves, guesses and time per configuration; `--out`
writes one CSV row per game.

## Development

```bash
uv run pytest
```
````

- [ ] **Step 4: Verify the full suite and imports**

Run: `uv run pytest -v`
Expected: all PASS

Run: `uv run python -c "import minesweeper.gui.app, minesweeper.__main__; print('ok')"`
Expected: `ok`

Run: `uv run python -m minesweeper --preset tiny --density 0.1:0.2:0.05`
Expected: exits with code 2 and `error: the GUI takes a single --density value, not a range`

- [ ] **Step 5: Manual play-check** (needs a display; ask the user if running headless)

Run: `uv run python -m minesweeper --preset beginner`
Check:
1. First left-click opens an area; numbers are coloured; right-click toggles ⚑ and the mine counter changes (can go negative).
2. Left-click on a satisfied number chords.
3. Hitting a mine: red ✹ on the hit cell, other mines shown, wrong flags show ✗, face ☹, timer stops, clicks ignored.
4. Winning: face ✌, remaining mines shown as ⚑.
5. Game ▸ Presets ▸ Expert resizes the board; Custom… with 5x5 + 20 mines shows the "too many mines" error and stays open.
6. AI panel: Step outlines a cell in orange and shows "reveal (r, c) — guess: random pick"; Auto plays until the game ends and the button reverts to "Auto".
7. Restart with the face button using a fixed `--seed` → same board.

- [ ] **Step 6: Commit**

```bash
git add minesweeper/gui/app.py minesweeper/__main__.py README.md
git commit -m "feat: tkinter GUI with AI step/auto panel and custom game dialog

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
