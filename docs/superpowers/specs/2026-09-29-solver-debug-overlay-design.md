# Solver Debug Overlay — Design

Date: 2026-09-29
Status: Approved in conversation, pending written-spec review
Sub-project A of 4 (A overlay → B starter kit → D GUI polish → C analysis extras)

## 1. Goal

Let the team's own solver (which they write — this project adds no solving
logic) show *why* it chose a move by painting per-cell information on the GUI
board: mine probabilities, category labels, and highlighted groups of cells.
Used for debugging the solver and for screenshots in the report.

Out of scope: any solver algorithm; animation of search steps; overlay data
in batch CSV output.

## 2. Constraints

- Stdlib only; Linux, Windows and macOS (Tk 8.6+); BMP-only glyphs.
- Backwards compatible: solvers that never set `debug` behave exactly as now.
- `minesweeper/solver/debug.py` must not import tkinter or `gui`.
- A malformed `Debug` must never crash the GUI or a batch run.

## 3. Data model — `minesweeper/solver/debug.py`

```python
@dataclass(frozen=True)
class Group:
    cells: tuple[Cell, ...]
    note: str = ""

@dataclass(frozen=True)
class Debug:
    probabilities: Mapping[Cell, float] = field(default_factory=dict)
    labels: Mapping[Cell, str] = field(default_factory=dict)
    groups: tuple[Group, ...] = ()

KNOWN_LABELS = ("safe", "mine", "frontier", "considered")

def validate_debug(debug: Debug, rows: int, cols: int) -> list[str]
def sanitize_debug(debug: Debug, rows: int, cols: int) -> Debug
```

- `validate_debug` returns human-readable problems, in this order:
  probabilities (cell out of bounds; value not a real number in [0, 1]),
  labels (cell out of bounds; label not a non-empty str), groups (any cell
  out of bounds). Empty list = valid. It never raises, even on wrong types
  (e.g. a non-tuple cell is reported as out of bounds).
- `sanitize_debug` returns a copy with every invalid entry dropped (a group
  loses only its invalid cells; a group left empty is dropped). The GUI
  renders the sanitized copy.

### 3.1 `Move` change — `minesweeper/solver/base.py`

`Move` gains a last field `debug: Debug | None = None`. Positional
construction `Move(action, cell, reason, certain)` keeps working.

### 3.2 Debug flag

After constructing a solver, the GUI does `solver.debug = True`. The batch
runner never sets it. Solvers may check `getattr(self, "debug", False)` to
skip building overlay data. `apply_move` and the batch runner ignore
`Move.debug` entirely.

## 4. GUI rendering

### 4.1 Pure style functions — `minesweeper/gui/overlay.py` (no tkinter)

```python
PROB_LOW, PROB_MID, PROB_HIGH = "#3cb371", "#f2d64b", "#e04040"
LABEL_COLORS = {"safe": "#3cb371", "mine": "#e04040",
                "frontier": "#4a7fd6", "considered": "#9b59b6"}
AUTO_COLORS = ("#ff8c00", "#00a3a3", "#c71585", "#6b8e23",
               "#8b4513", "#1e90ff", "#b8860b", "#708090")
GROUP_COLORS = ("#ff1493", "#00ced1", "#ff8c00", "#7cfc00", "#9370db", "#ffd700")

def probability_color(p: float) -> str        # linear RGB interp low→mid (0–0.5), mid→high (0.5–1)
def label_colors(debug: Debug) -> dict[str, str]
    # known labels → fixed colour; other labels, sorted by name → AUTO_COLORS cycling
def circled(n: int) -> str                     # 1..20 → "①".."⑳" (U+2460+n-1); else f"({n})"

@dataclass(frozen=True)
class OverlayStyle:
    fill: str | None      # replaces the hidden-cell background, None = unchanged
    text: str | None      # replaces cell text, None = unchanged
    border: str | None    # inner border colour for a label when a probability also exists

def overlay_style(debug: Debug, cell: Cell, state: CellState, cell_size: int) -> OverlayStyle | None
def group_outlines(debug: Debug) -> list[tuple[Cell, str, int]]   # (cell, colour, inset px)
def legend_entries(debug: Debug) -> list[tuple[str, str]]         # (label, colour), labels in use
def hover_text(cell: Cell, debug: Debug | None) -> str
```

**`overlay_style` rules** (returns `None` for REVEALED cells or when the
cell has no probability and no label):
- Probability only → `fill = probability_color(p)`; `text = f"{round(p*100)}"`
  if `cell_size >= 24` and the cell is HIDDEN (flagged cells keep ⚑), else None.
- Label only → `fill = label colour`, text None, border None.
- Both → fill and text from the probability, `border = label colour`.

**`group_outlines`:** group *i* (0-based) uses `GROUP_COLORS[i % 6]`. A cell's
k-th group membership (k = 0, 1, … in group order) gets inset `2 + 3k` px,
capped at `cell_size // 3` by the caller, so overlapping groups stay visible.

**`hover_text`:** `"(r, c)"`, then `  p=12%` if it has a probability, then
`  label=frontier`, then `  groups ①③` (1-based group numbers). With
`debug=None` just `"(r, c)"`.

### 4.2 Widgets — `minesweeper/gui/app.py`

- AI panel gains a **Show overlay** checkbutton (default on). `o`/`O` keys
  toggle it.
- Below the reason line: a **group notes** label listing
  `① note  ② note …` (groups with empty notes are listed by number only;
  hidden if no groups), a **legend** row (small colour squares + label names
  for `legend_entries`, plus a 100×10 px probability gradient bar labelled
  `0%` … `100%` when any probability is present), and a **hover** label
  showing `hover_text` for the cell under the mouse (`<Motion>`; cleared on
  `<Leave>`).
- Canvas: label borders and group outlines are extra rectangle items tagged
  `"overlay"`, deleted and recreated on every overlay change. Group outlines
  use `dash="-"` (a dash form supported on Windows GDI as well as X11/aqua),
  width 2. Cell fill/text come from `cell_appearance` then `overlay_style`.
- State: `self.debug: Debug | None`. Set from `move.debug` (sanitized) after
  each successful AI step; if `validate_debug` reported problems, the reason
  line appends `  [overlay: <first problem>]`. Cleared to `None` on any manual
  reveal/flag/chord that changed the board, and on `new_game`.
- Toggling the checkbox off hides overlay drawing but keeps `self.debug`, so
  toggling on restores it.

## 5. Error handling

- Invalid overlay entries: dropped, first problem shown, rest rendered.
- Solver returns `debug` that is not a `Debug` instance: treated as a problem
  (`"debug must be a Debug, got <type>"`), overlay cleared, move still applied.
- Batch runs never read `debug`, so overlay bugs cannot affect statistics.

## 6. Testing

- `tests/test_debug.py`: defaults are empty; `Move` positional construction
  unchanged and `debug` defaults to None; `validate_debug` reports each
  problem kind (out-of-bounds cell, p < 0, p > 1, NaN, non-number, empty
  label, non-str label, bad group cell, non-tuple cell) and returns `[]` for
  valid data; `sanitize_debug` drops exactly the invalid entries and empty
  groups.
- `tests/test_overlay.py`: `probability_color` at 0, 0.5, 1 and a midpoint
  (0.25 → halfway between low and mid); known and auto label colours
  (deterministic, sorted); `circled` 1, 20, 21; every `overlay_style` rule
  (revealed → None, prob only, label only, both, small cell → no text,
  flagged → no text); `group_outlines` colours and insets for overlapping
  groups; `legend_entries`; `hover_text` variants.
- Batch: a solver returning `Move(..., debug=Debug(...))` with invalid data
  runs to completion with identical results to the same solver without debug.
- GUI: scripted drive with a throwaway demo solver (in the scratchpad, not
  the repo) that emits probabilities, labels and two overlapping groups;
  screenshot check; toggle via `o`; manual move clears overlay.
