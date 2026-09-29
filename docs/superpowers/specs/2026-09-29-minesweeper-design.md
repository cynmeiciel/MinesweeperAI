# Minesweeper — Game, GUI & Analysis Harness Design

Date: 2026-09-29
Status: Approved in conversation, pending written-spec review

## 1. Goal

A playable Minesweeper with a GUI (assignment requirement), built so that an AI
solver can be added later and evaluated both **visually** (step through the AI's
moves in the GUI, with reasons) and **statistically** (headless batch runs →
CSV). Every rule variant is configurable so it can be compared in the report.

### Assignment rules (must hold under default config)
- Left-click reveals a cell. A number = count of mines in the 8 neighbours;
  a blank (0) cell auto-reveals its neighbourhood.
- Right-click places/removes a flag.
- **Win:** all non-mine cells revealed (flags irrelevant).
- **Lose:** revealing a mine ends the game immediately.
- DFS/BFS used (flood fill now; solver search later).
- GUI supports different sizes (5x5, 9x9, …).

### Out of scope for this spec
- The real AI solver's algorithms (separate design pass later). This spec only
  defines the solver **interface** plus a random baseline.
- The PDF report itself.
- Charts/plots (CSV output only).

## 2. Environment

- Python 3.13, **tkinter** (already installed). No runtime dependencies.
- Dev dependency: pytest.
- Project is a git repository (initialised as part of this work).

## 3. Package layout

```
minesweeper/
  __init__.py
  __main__.py            # `python -m minesweeper` → GUI
  core/
    __init__.py
    config.py            # GameConfig, enums, PRESETS
    board.py             # Board (ground truth), neighbors()
    game.py              # Game (rules/state), RevealResult, PlayerView
  gui/
    __init__.py
    app.py               # tkinter App, canvas rendering, dialogs
    render.py            # pure: game state → cell appearance; pixel → cell
  solver/
    __init__.py          # SOLVERS registry
    base.py              # Move, Solver protocol
    random_solver.py     # baseline
  analysis/
    __init__.py
    __main__.py          # `python -m minesweeper.analysis`
    batch.py             # headless runner, CSV writer, summary
tests/
  test_config.py test_board.py test_game.py test_render.py
  test_solver_base.py test_batch.py
pyproject.toml
README.md
```

Dependency direction: `gui`, `solver`, `analysis` → `core`. `gui` and
`analysis` → `solver`. `core` depends on nothing in the package.

## 4. Core engine (`minesweeper/core`)

### 4.1 `config.py`

```python
class FirstClick(Enum):  UNSAFE, SAFE, OPENING
class FloodFill(Enum):   BFS, DFS

@dataclass(frozen=True)
class GameConfig:
    rows: int
    cols: int
    mines: int
    first_click: FirstClick = FirstClick.OPENING
    chord: bool = True
    flood_fill: FloodFill = FloodFill.BFS
    seed: int | None = None

    @classmethod
    def from_density(cls, rows, cols, density, **kw) -> "GameConfig"
        # mines = round(rows*cols*density), min 1
    @property
    def density(self) -> float
```

- `FirstClick.UNSAFE`: mines placed at game creation; first click may hit a mine.
- `FirstClick.SAFE`: mines placed on first reveal, excluding the clicked cell.
- `FirstClick.OPENING`: mines placed on first reveal, excluding the clicked cell
  and its in-bounds neighbours (so the first click reveals a 0).

**Validation (in `__post_init__`, raises `ValueError`):**
- `rows >= 1`, `cols >= 1`, `mines >= 1`.
- `mines <= rows*cols - reserve`, where `reserve` is 0 for UNSAFE, 1 for SAFE,
  9 for OPENING. (Using 9 for OPENING is conservative: corner/edge clicks
  exclude fewer cells, but config must be valid for any first click.)
  For boards smaller than 3x3, OPENING's reserve is `min(9, rows*cols)`.

**Presets:**

| name         | rows | cols | mines |
|--------------|------|------|-------|
| tiny         | 5    | 5    | 3     |
| beginner     | 9    | 9    | 10    |
| intermediate | 16   | 16   | 40    |
| expert       | 16   | 30   | 99    |

`PRESETS: dict[str, GameConfig]` with default rule options;
`GameConfig` is frozen, so variants are made via `dataclasses.replace`.

### 4.2 `board.py`

```python
Cell = tuple[int, int]   # (row, col)

def neighbors(r, c, rows, cols) -> list[Cell]   # up to 8, in-bounds

@dataclass
class Board:
    rows: int; cols: int
    mines: frozenset[Cell]
    adjacent: list[list[int]]      # precomputed neighbour-mine counts

    @classmethod
    def generate(cls, config, rng: random.Random,
                 exclude: set[Cell] = frozenset()) -> "Board"
        # rng.sample over sorted list of allowed cells → deterministic per seed
    @classmethod
    def from_mines(cls, rows, cols, mines) -> "Board"   # for tests
    def is_mine(cell) -> bool
```

`neighbors` is the only neighbourhood helper; all other modules use it.

### 4.3 `game.py`

```python
class CellState(Enum):  HIDDEN, FLAGGED, REVEALED
class Status(Enum):     READY, PLAYING, WON, LOST

@dataclass
class RevealResult:
    revealed: list[Cell]           # newly revealed, in reveal order
    hit_mine: Cell | None
    status: Status

class Game:
    def __init__(self, config: GameConfig, board: Board | None = None)
        # rng = random.Random(config.seed); if seed is None, a seed is drawn
        # from random.SystemRandom and stored in self.seed (so every game is
        # replayable). UNSAFE → board generated immediately.
        # `board` arg lets tests inject a fixed layout (skips generation).
    config, seed, status, rows, cols
    def state(r, c) -> CellState
    def number(r, c) -> int | None      # only if REVEALED, else None
    def reveal(r, c) -> RevealResult
    def toggle_flag(r, c) -> bool       # returns True if the state changed
    def chord(r, c) -> RevealResult
    def view() -> PlayerView
    flags_placed: int; mines_remaining: int  # mines - flags (may go negative)
    stats: GameStats
```

**`reveal(r, c)` algorithm:**
1. If status is WON/LOST, or cell is FLAGGED/REVEALED → return empty result.
2. If board not yet generated: generate with `exclude` = {} / {cell} /
   {cell} ∪ neighbors(cell) according to `first_click`. Status → PLAYING.
3. If cell is a mine → mark it REVEALED, status → LOST, `hit_mine = cell`.
4. Else flood fill from `cell` with a frontier container (deque; `popleft`
   for BFS, `pop` for DFS) and a `seen` set:
   - pop cell; if HIDDEN, mark REVEALED, append to `revealed`.
   - if its adjacent count is 0, push each neighbour that is HIDDEN and not
     in `seen` (FLAGGED neighbours are never auto-revealed).
5. If `revealed_count == rows*cols - mines` → status WON.
6. Update stats; return result.

Both BFS and DFS reveal the same *set* of cells; only order differs.
Iterative (not recursive) to avoid recursion limits on large boards.

**`toggle_flag`:** only on HIDDEN↔FLAGGED, only while status is READY or
PLAYING. Flagging in READY state is allowed but does not start the game.

**`chord(r, c)`:** if `config.chord` is False, or the cell is not REVEALED, or
the count of FLAGGED neighbours ≠ its number → empty result. Otherwise reveal
every HIDDEN neighbour (combined into one RevealResult; stops at first mine →
LOST). A wrong flag therefore can lose the game, as in standard Minesweeper.

**`PlayerView`** (frozen, what a solver may see):
```python
@dataclass(frozen=True)
class PlayerView:
    rows: int; cols: int; total_mines: int
    cells: tuple[tuple[int | None, ...], ...]   # revealed number, else None
    flags: frozenset[Cell]
    status: Status
    def hidden_cells() -> list[Cell]           # HIDDEN and not flagged
    def neighbors(cell) -> list[Cell]
```
It never contains mine positions.

**`GameStats`:** `clicks` (reveal + chord calls that changed state),
`flags` (toggle calls that changed state), `start_time`, `end_time`
(`time.perf_counter`; start at first reveal), `elapsed` property.

## 5. GUI (`minesweeper/gui`)

### 5.1 Layout
- Menu: *Game* ▸ New (F2), Presets ▸ (tiny/beginner/intermediate/expert),
  Custom…, Quit.
- Header: mines remaining counter · restart face button (🙂 / 😎 won / 😵 lost)
  · timer (seconds, updated via `after(250, …)` while PLAYING).
- Board: a single `tk.Canvas`; one rectangle + one text item per cell.
  Cell size = `clamp(min(max_w/cols, max_h/rows), 16, 40)` px, where max
  dims come from 85% of the screen size.
- Status bar: `seed=<n>  rules: OPENING, chord on, BFS`.
- AI panel: solver dropdown (from `SOLVERS`), **Step**, **Auto ▶/⏸**, speed
  slider (50–1000 ms), reason label. Last AI-chosen cell gets a highlight
  outline.

### 5.2 Input
- `<Button-1>` on HIDDEN → `reveal`; on REVEALED number → `chord` (if enabled).
- `<Button-2>` → `chord`; `<Button-3>` → `toggle_flag`. On macOS (`tk windowingsystem == "aqua"`)
  Button-2 is right-click: bind flag to Button-2 and chord to Button-3 swapped.
- Input ignored after WON/LOST (except restart/menu).

### 5.3 Rendering (`render.py`, pure functions — unit tested)
- `cell_appearance(game, r, c, reveal_all: bool) -> Appearance(text, fg, bg)`
  - HIDDEN: raised grey; FLAGGED: "⚑" red.
  - REVEALED number: classic colours 1 blue, 2 green, 3 red, 4 navy,
    5 maroon, 6 teal, 7 black, 8 grey; 0 blank.
  - On LOST (`reveal_all`): unflagged mines "✹", the hit mine with red bg,
    wrong flags shown as "✗".
- `pixel_to_cell(x, y, cell_size, rows, cols) -> Cell | None`.
- After a move, only cells in `RevealResult.revealed` (plus the toggled cell)
  are redrawn; on game end the whole board is redrawn.

### 5.4 Custom dialog
Fields: rows, cols, mines **or** density (radio), first-click rule
(dropdown), chord (checkbox), flood fill (BFS/DFS), seed (blank = random).
On OK builds `GameConfig`; on `ValueError` shows the message and stays open.

### 5.5 AI integration
- **Step:** `move = solver.next_move(game.view())`; apply `reveal`/`toggle_flag`;
  highlight `move.cell`; show `move.reason` (prefix "guess:" if not certain).
- **Auto:** repeat Step via `after(speed_ms)` until the game ends or paused.
- Solver instance is re-created on new game.

### 5.6 Launch
`python -m minesweeper [--preset NAME] [--rows R --cols C (--mines M | --density D)]
[--first-click UNSAFE|SAFE|OPENING] [--no-chord] [--flood-fill BFS|DFS] [--seed N]`.
The same argument → `GameConfig` builder is shared with the batch CLI.

## 6. Solver interface (`minesweeper/solver`)

```python
@dataclass(frozen=True)
class Move:
    action: Literal["reveal", "flag"]
    cell: Cell
    reason: str
    certain: bool

class Solver(Protocol):
    name: str
    def __init__(self, rng: random.Random) -> None: ...
    def next_move(self, view: PlayerView) -> Move: ...

SOLVERS: dict[str, type[Solver]] = {"random": RandomSolver}
```

- Solvers receive only `PlayerView` — they cannot see mines.
- `RandomSolver`: reveals a uniformly random hidden, unflagged cell;
  `certain=False`, reason `"random pick"`.
- Future solver (separate spec): single-cell rules → subset reasoning →
  DFS/backtracking over the frontier for mine probabilities → guessing
  heuristics; each stage toggleable for ablation.

## 7. Analysis (`minesweeper/analysis`)

```
python -m minesweeper.analysis --solver random --preset beginner \
    --games 1000 --seed 0 [--first-click …] [--no-chord] [--flood-fill …] \
    [--density 0.10:0.25:0.03] [--out results.csv]
```

- Game *i* uses seed `base_seed + i`; the solver gets an independent but reproducible rng, `random.Random(f"solver:{seed}")` (`solver_rng`). Reusing the game seed directly would replay the board generator's draws and bias guesses onto mines.
- `--preset` may be repeated; `--density start:stop:step` (stop inclusive,
  applied to rows/cols of each preset or `--rows/--cols`) sweeps densities.
  The run is the cartesian product of configs × games.
- Safety cap: a game aborts as `"stalled"` if the solver exceeds
  `rows*cols*2` moves or returns an illegal move (logged, not raised).
- **CSV columns:** `seed, rows, cols, mines, density, first_click, chord,
  flood_fill, solver, result (won/lost/stalled), moves, guesses, cells_revealed,
  time_ms`.
- **Summary (stdout)** per config: games, win rate ± 95% CI (Wilson),
  mean moves, mean guesses, mean time_ms.
- `run_game(config, solver_cls) -> GameRecord` is a pure function reusable
  from notebooks.

## 8. Error handling
- Invalid config → `ValueError` at construction (GUI shows messagebox; CLI
  prints message, exit code 2).
- Out-of-bounds cell passed to `Game` methods → `IndexError`.
- Actions after game over → no-op (empty result), never raise.
- Solver exceptions in GUI → shown in reason label, Auto stops.

## 9. Testing (pytest)
- **config:** density rounding, validation boundaries for each first-click
  rule, presets valid.
- **board:** `neighbors` at corners/edges/centre; adjacency counts on a
  hand-made board; same seed → same board; exclusion zones respected.
- **game:** flood fill reveals exact expected set (BFS and DFS equal sets,
  different orders on a crafted board); flags block flood fill; win/lose
  detection; each first-click rule over many seeds (SAFE never loses on
  click 1, OPENING always reveals a 0); chord success/refuse/lose paths and
  chord disabled; no-ops after game over; `PlayerView` hides mines.
- **render:** appearance for every state; `pixel_to_cell` bounds.
- **solver:** RandomSolver only returns hidden unflagged cells.
- **batch:** reproducibility (same args → identical CSV rows except time),
  stalled detection with a misbehaving stub solver, Wilson CI values.
- GUI widgets: manual play-check.
