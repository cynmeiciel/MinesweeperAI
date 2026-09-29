# Solver Debug Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a team-written solver attach per-cell probabilities, labels and highlighted groups to each `Move`, and paint them on the GUI board with a legend, group notes and hover details.

**Architecture:** A GUI-free data module (`solver/debug.py`) defines `Debug`/`Group` plus validation/sanitising. Pure style functions (`gui/overlay.py`, no tkinter) turn a `Debug` into colours/text/outlines. `gui/app.py` only wires those into canvas items and widgets. Batch runs never read the overlay.

**Tech Stack:** Python 3.13, tkinter (Tk 8.6), stdlib only; pytest via `uv`.

**Spec:** `docs/superpowers/specs/2026-09-29-solver-debug-overlay-design.md`

## Global Constraints

- No runtime dependencies; stdlib only. Must work on Linux, Windows and macOS (Tk 8.6+).
- GUI text uses only BMP characters (circled numbers ①–⑳ are U+2460–U+2473).
- `minesweeper/solver/debug.py` and `minesweeper/gui/overlay.py` must not import tkinter.
- Backwards compatible: `Move(action, cell, reason, certain)` still works; solvers without `debug` behave exactly as before.
- A malformed `Debug` must never crash the GUI or a batch run; batch runs never read `Move.debug`.
- This project adds **no solving logic**; the demo solver used for GUI checks lives in the scratchpad, not the repo.
- Run tests with `VIRTUAL_ENV= uv run pytest` from the project root.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Overlay toggled off then on** → drawing disappears, then the same overlay returns (data kept). Scripted GUI check in Task 3.
2. **Boundary probability values** (`0`, `1` as ints, `0.0`/`1.0`) accepted; `True`/`False` rejected as non-numbers. Tests in Task 1.
3. **Game ends while an overlay is shown** → mine ✹ / wrong-flag ✗ glyphs stay visible (overlay never replaces a glyph). Test in Task 2 (`merge_appearance`).
4. **Same cell listed twice in one group** → one outline, not two. Test in Task 2.
5. **Solver that can't take a `debug` attribute (`__slots__`) or returns a non-`Debug` object** → GUI keeps working, problem shown in the reason line. Test in Task 1 (`prepare_debug`) + scripted GUI check in Task 3.

## Spec deviations (intentional, small)

- Added `prepare_debug(obj, rows, cols) -> (Debug | None, list[str])` wrapping the "not a `Debug`" check + sanitize + validate, so the GUI makes one call.
- Added pure helpers `group_notes(debug) -> str` and `merge_appearance(appearance, style) -> Appearance` in `overlay.py`, so the notes text and the "never hide a glyph" rule are unit-tested.
- `overlay_style` takes an optional `colors` argument (precomputed `label_colors`) so a full-board redraw is O(cells), not O(cells × labels).
- Rule added: overlay text never replaces an existing cell glyph (✹, ✗, ⚑) — keeps game-over boards readable.
- When `sanitize_debug` drops an invalid group, later groups are renumbered (① refers to the position in the sanitized tuple).

## File Map

```
minesweeper/solver/debug.py      # Task 1 (new): Debug, Group, KNOWN_LABELS, validate/sanitize/prepare
minesweeper/solver/base.py       # Task 1: Move.debug field
minesweeper/solver/__init__.py   # Task 1: export Debug, Group
minesweeper/gui/overlay.py       # Task 2 (new): pure style functions
minesweeper/gui/app.py           # Task 3: widgets, canvas items, AI/manual wiring
README.md                        # Task 3: short "Solver overlay" section
tests/test_debug.py              # Task 1 (new)
tests/test_batch.py              # Task 1: batch ignores debug
tests/test_overlay.py            # Task 2 (new)
```

---

### Task 1: `Debug` data model and `Move.debug`

**Files:**
- Create: `minesweeper/solver/debug.py`
- Modify: `minesweeper/solver/base.py` (`Move`), `minesweeper/solver/__init__.py`
- Test: `tests/test_debug.py` (new), `tests/test_batch.py` (append)

**Interfaces:**
- Consumes: `Cell` from `minesweeper.core.board`; `Move`, `RandomSolver`, `run_game` (existing).
- Produces:
  - `KNOWN_LABELS: tuple[str, ...] = ("safe", "mine", "frontier", "considered")`
  - `Group(cells: tuple[Cell, ...], note: str = "")` frozen
  - `Debug(probabilities: Mapping[Cell, float] = {}, labels: Mapping[Cell, str] = {}, groups: tuple[Group, ...] = ())` frozen, dict defaults via `default_factory`
  - `validate_debug(debug, rows, cols) -> list[str]`; `sanitize_debug(debug, rows, cols) -> Debug`; `prepare_debug(obj, rows, cols) -> tuple[Debug | None, list[str]]`
  - Problem messages start with `"probability "`, `"label "`, `"group "`, or are `"probabilities must be a dict"`, `"labels must be a dict"`, `"groups must be a tuple of Group"`, `"debug must be a Debug, got <type name>"`.
  - `Move(..., debug: Debug | None = None)`; `from minesweeper.solver import Debug, Group` works.

- [ ] **Step 1: Write the failing tests** — `tests/test_debug.py`

```python
import math

import pytest

from minesweeper.solver import Debug, Group, Move
from minesweeper.solver.debug import KNOWN_LABELS, prepare_debug, sanitize_debug, validate_debug


def test_defaults_empty():
    d = Debug()
    assert dict(d.probabilities) == {} and dict(d.labels) == {} and d.groups == ()


def test_defaults_not_shared():
    assert Debug().probabilities is not Debug().probabilities


def test_move_positional_and_default_debug():
    m = Move("reveal", (0, 0), "why", True)
    assert m.debug is None
    d = Debug(labels={(0, 0): "safe"})
    assert Move("reveal", (0, 0), "why", True, debug=d).debug is d


def test_known_labels():
    assert KNOWN_LABELS == ("safe", "mine", "frontier", "considered")


VALID = Debug(
    probabilities={(0, 0): 0.0, (0, 1): 1, (1, 1): 0.25, (1, 2): 0, (2, 0): 1.0},
    labels={(0, 0): "safe", (2, 2): "my-label"},
    groups=(Group(((0, 0), (0, 1)), "subset"), Group(((2, 2),))),
)


def test_valid_debug_has_no_problems():  # Review Focus 2: ints 0/1 are fine
    assert validate_debug(VALID, 3, 3) == []
    assert sanitize_debug(VALID, 3, 3) == VALID


@pytest.mark.parametrize(
    "debug,fragment",
    [
        (Debug(probabilities={(3, 0): 0.5}), "off the board"),
        (Debug(probabilities={(0, 0): -0.1}), "not a number in [0, 1]"),
        (Debug(probabilities={(0, 0): 1.5}), "not a number in [0, 1]"),
        (Debug(probabilities={(0, 0): math.nan}), "not a number in [0, 1]"),
        (Debug(probabilities={(0, 0): "0.5"}), "not a number in [0, 1]"),
        (Debug(probabilities={(0, 0): True}), "not a number in [0, 1]"),  # Review Focus 2
        (Debug(labels={(0, -1): "safe"}), "off the board"),
        (Debug(labels={(0, 0): ""}), "non-empty string"),
        (Debug(labels={(0, 0): 3}), "non-empty string"),
        (Debug(groups=(Group(((0, 0), (5, 5))),)), "group 1 cell (5, 5) is off the board"),
        (Debug(groups=(Group(([0, 0],)),)), "off the board"),  # list, not tuple
        (Debug(groups=("nope",)), "group 1 is not a Group"),
        (Debug(probabilities=[((0, 0), 0.5)]), "probabilities must be a dict"),
        (Debug(labels=None), "labels must be a dict"),
        (Debug(groups=None), "groups must be a tuple of Group"),
    ],
)
def test_each_problem_reported(debug, fragment):
    problems = validate_debug(debug, 3, 3)
    assert len(problems) == 1
    assert fragment in problems[0]


def test_problem_order():
    d = Debug(probabilities={(9, 9): 0.5}, labels={(9, 9): "x"}, groups=(Group(((9, 9),)),))
    assert [p.split()[0] for p in validate_debug(d, 3, 3)] == ["probability", "label", "group"]


def test_sanitize_drops_only_invalid():
    d = Debug(
        probabilities={(0, 0): 0.5, (0, 1): 2.0, (9, 9): 0.1},
        labels={(1, 1): "mine", (1, 2): ""},
        groups=(Group(((0, 0), (9, 9)), "keep"), Group(((9, 9),), "gone"), "junk"),
    )
    clean = sanitize_debug(d, 3, 3)
    assert dict(clean.probabilities) == {(0, 0): 0.5}
    assert dict(clean.labels) == {(1, 1): "mine"}
    assert clean.groups == (Group(((0, 0),), "keep"),)
    assert validate_debug(clean, 3, 3) == []


def test_prepare_debug():  # Review Focus 5
    assert prepare_debug(None, 3, 3) == (None, [])
    clean, problems = prepare_debug({"not": "debug"}, 3, 3)
    assert clean is None and problems == ["debug must be a Debug, got dict"]
    clean, problems = prepare_debug(Debug(labels={(0, 0): "safe", (7, 7): "x"}), 3, 3)
    assert dict(clean.labels) == {(0, 0): "safe"} and len(problems) == 1
```

Append to `tests/test_batch.py` (and add `from minesweeper.solver.debug import Debug` to its imports):

```python


class NoisyDebugSolver(RandomSolver):
    """Random solver that attaches invalid overlay data to every move."""

    name = "noisy"

    def next_move(self, view):
        move = super().next_move(view)
        return Move(
            move.action, move.cell, move.reason, move.certain,
            debug=Debug(probabilities={(99, 99): 5.0}, labels={move.cell: ""}),
        )


def test_batch_ignores_debug_even_when_invalid():
    cfg = GameConfig(9, 9, 10, seed=11)
    keep = lambda r: {k: v for k, v in r.__dict__.items() if k not in ("solver", "time_ms")}
    assert keep(run_game(cfg, RandomSolver)) == keep(run_game(cfg, NoisyDebugSolver))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `VIRTUAL_ENV= uv run pytest tests/test_debug.py tests/test_batch.py -q`
Expected: collection ERROR in both files — `ImportError: cannot import name 'Debug' from 'minesweeper.solver'` / `ModuleNotFoundError: No module named 'minesweeper.solver.debug'`

- [ ] **Step 3: Implement** — `minesweeper/solver/debug.py`

```python
"""Optional overlay data a solver can attach to a Move for the GUI.

Never imports tkinter. Batch runs ignore it; the GUI validates and sanitises
it so a bug in a solver's debug output can never crash the program.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from minesweeper.core.board import Cell

KNOWN_LABELS = ("safe", "mine", "frontier", "considered")


@dataclass(frozen=True)
class Group:
    """Cells that belong together in one deduction, e.g. a subset rule."""

    cells: tuple[Cell, ...]
    note: str = ""


@dataclass(frozen=True)
class Debug:
    probabilities: Mapping[Cell, float] = field(default_factory=dict)  # 0.0 safe … 1.0 mine
    labels: Mapping[Cell, str] = field(default_factory=dict)
    groups: tuple[Group, ...] = ()


def _on_board(cell: object, rows: int, cols: int) -> bool:
    return (
        isinstance(cell, tuple)
        and len(cell) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in cell)
        and 0 <= cell[0] < rows
        and 0 <= cell[1] < cols
    )


def _is_probability(p: object) -> bool:
    return (
        isinstance(p, (int, float))
        and not isinstance(p, bool)
        and math.isfinite(p)
        and 0 <= p <= 1
    )


def _check(debug: Debug, rows: int, cols: int) -> tuple[Debug, list[str]]:
    """Return (copy with invalid entries dropped, problems found)."""
    problems: list[str] = []

    probabilities: dict[Cell, float] = {}
    if isinstance(debug.probabilities, Mapping):
        for cell, p in debug.probabilities.items():
            if not _on_board(cell, rows, cols):
                problems.append(f"probability cell {cell!r} is off the board")
            elif not _is_probability(p):
                problems.append(f"probability {p!r} at {cell} is not a number in [0, 1]")
            else:
                probabilities[cell] = float(p)
    else:
        problems.append("probabilities must be a dict")

    labels: dict[Cell, str] = {}
    if isinstance(debug.labels, Mapping):
        for cell, label in debug.labels.items():
            if not _on_board(cell, rows, cols):
                problems.append(f"label cell {cell!r} is off the board")
            elif not isinstance(label, str) or not label:
                problems.append(f"label {label!r} at {cell} must be a non-empty string")
            else:
                labels[cell] = label
    else:
        problems.append("labels must be a dict")

    groups: list[Group] = []
    if isinstance(debug.groups, (tuple, list)):
        for i, group in enumerate(debug.groups, 1):
            if not isinstance(group, Group) or not isinstance(group.cells, (tuple, list)):
                problems.append(f"group {i} is not a Group of cells")
                continue
            kept = []
            for cell in group.cells:
                if _on_board(cell, rows, cols):
                    kept.append(cell)
                else:
                    problems.append(f"group {i} cell {cell!r} is off the board")
            if kept:
                groups.append(Group(tuple(kept), str(group.note)))
    else:
        problems.append("groups must be a tuple of Group")

    return Debug(probabilities, labels, tuple(groups)), problems


def validate_debug(debug: Debug, rows: int, cols: int) -> list[str]:
    """Human-readable problems (probabilities, then labels, then groups). Never raises."""
    return _check(debug, rows, cols)[1]


def sanitize_debug(debug: Debug, rows: int, cols: int) -> Debug:
    """Copy with every invalid entry dropped; groups left empty are removed."""
    return _check(debug, rows, cols)[0]


def prepare_debug(obj: object, rows: int, cols: int) -> tuple[Debug | None, list[str]]:
    """What the GUI calls with Move.debug: (drawable Debug or None, problems)."""
    if obj is None:
        return None, []
    if not isinstance(obj, Debug):
        return None, [f"debug must be a Debug, got {type(obj).__name__}"]
    return _check(obj, rows, cols)
```

Modify `minesweeper/solver/base.py` — add import and field:

```python
from minesweeper.solver.debug import Debug
```
(place after `from minesweeper.core.game import CellState, Game, PlayerView`), and change `Move` to:

```python
@dataclass(frozen=True)
class Move:
    action: Literal["reveal", "flag"]
    cell: Cell
    reason: str    # human-readable, shown in the GUI and useful for the report
    certain: bool  # False = a guess
    debug: Debug | None = None  # optional overlay for the GUI; ignored by batch runs
```

Replace `minesweeper/solver/__init__.py` with:

```python
"""Solvers. Each sees only a PlayerView, never the mine layout."""
from minesweeper.solver.base import Move, Solver, apply_move, solver_rng
from minesweeper.solver.debug import Debug, Group
from minesweeper.solver.random_solver import RandomSolver

SOLVERS: dict[str, type[Solver]] = {
    RandomSolver.name: RandomSolver,
}

__all__ = [
    "SOLVERS", "Move", "Solver", "apply_move", "solver_rng", "Debug", "Group", "RandomSolver",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `VIRTUAL_ENV= uv run pytest -q`
Expected: all PASS (122 existing + new)

- [ ] **Step 5: Commit**

```bash
git add minesweeper/solver tests/test_debug.py tests/test_batch.py
git commit -m "feat: Debug overlay data on Move, with validation and sanitising

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Pure overlay style functions

**Files:**
- Create: `minesweeper/gui/overlay.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Consumes: `Debug`, `Group`, `KNOWN_LABELS` (Task 1); `CellState` (core); `Appearance` from `minesweeper.gui.render`.
- Produces:
  - Constants `PROB_LOW, PROB_MID, PROB_HIGH`, `LABEL_COLORS`, `AUTO_COLORS`, `GROUP_COLORS`
  - `probability_color(p: float) -> str`
  - `label_colors(debug) -> dict[str, str]`
  - `circled(n: int) -> str`
  - `OverlayStyle(fill: str | None, text: str | None, border: str | None)` frozen
  - `overlay_style(debug, cell, state, cell_size, colors=None) -> OverlayStyle | None`
  - `merge_appearance(appearance: Appearance, style: OverlayStyle | None) -> Appearance`
  - `group_outlines(debug) -> list[tuple[Cell, str, int]]`
  - `legend_entries(debug) -> list[tuple[str, str]]`
  - `group_notes(debug) -> str`
  - `hover_text(cell, debug | None) -> str`

- [ ] **Step 1: Write the failing tests** — `tests/test_overlay.py`

```python
import pytest

from minesweeper.core.game import CellState
from minesweeper.gui.overlay import (
    AUTO_COLORS,
    GROUP_COLORS,
    LABEL_COLORS,
    PROB_HIGH,
    PROB_LOW,
    PROB_MID,
    OverlayStyle,
    circled,
    group_notes,
    group_outlines,
    hover_text,
    label_colors,
    legend_entries,
    merge_appearance,
    overlay_style,
    probability_color,
)
from minesweeper.gui.render import Appearance
from minesweeper.solver.debug import KNOWN_LABELS, Debug, Group

HIDDEN, FLAGGED, REVEALED = CellState.HIDDEN, CellState.FLAGGED, CellState.REVEALED


def test_probability_color_endpoints_and_midpoint():
    assert probability_color(0) == PROB_LOW
    assert probability_color(0.5) == PROB_MID
    assert probability_color(1) == PROB_HIGH
    # halfway between #3cb371 and #f2d64b
    assert probability_color(0.25) == "#97c45e"


def test_label_colors_known_and_auto_sorted():
    d = Debug(labels={(0, 0): "zeta", (0, 1): "safe", (0, 2): "alpha", (0, 3): "zeta"})
    assert label_colors(d) == {
        "safe": LABEL_COLORS["safe"],
        "alpha": AUTO_COLORS[0],
        "zeta": AUTO_COLORS[1],
    }


def test_label_colors_cycle():
    d = Debug(labels={(0, i): f"l{i:02d}" for i in range(9)})
    assert label_colors(d)["l08"] == AUTO_COLORS[0]


def test_known_labels_all_have_colors():
    assert set(LABEL_COLORS) == set(KNOWN_LABELS)


def test_circled():
    assert circled(1) == "①"
    assert circled(20) == "⑳"
    assert circled(21) == "(21)"


D = Debug(
    probabilities={(0, 0): 0.12, (0, 1): 0.9},
    labels={(0, 1): "frontier", (1, 0): "safe"},
)


def test_style_revealed_is_none():
    assert overlay_style(D, (0, 0), REVEALED, 40) is None


def test_style_no_data_is_none():
    assert overlay_style(D, (2, 2), HIDDEN, 40) is None


def test_style_probability_only():
    assert overlay_style(D, (0, 0), HIDDEN, 40) == OverlayStyle(probability_color(0.12), "12", None)


def test_style_label_only():
    assert overlay_style(D, (1, 0), HIDDEN, 40) == OverlayStyle(LABEL_COLORS["safe"], None, None)


def test_style_probability_and_label():
    assert overlay_style(D, (0, 1), HIDDEN, 40) == OverlayStyle(
        probability_color(0.9), "90", LABEL_COLORS["frontier"]
    )


def test_style_small_cell_has_no_text():
    assert overlay_style(D, (0, 0), HIDDEN, 23).text is None
    assert overlay_style(D, (0, 0), HIDDEN, 24).text == "12"


def test_style_flagged_keeps_flag():
    style = overlay_style(D, (0, 0), FLAGGED, 40)
    assert style.text is None and style.fill == probability_color(0.12)


def test_style_uses_precomputed_colors():
    assert overlay_style(D, (1, 0), HIDDEN, 40, colors={"safe": "#123456"}).fill == "#123456"


def test_merge_none_keeps_appearance():
    a = Appearance("", "#000000", "#c0c0c0", True)
    assert merge_appearance(a, None) is a


def test_merge_applies_fill_and_text():
    a = Appearance("", "#111111", "#c0c0c0", True)
    assert merge_appearance(a, OverlayStyle("#abcdef", "12", None)) == Appearance(
        "12", "#000000", "#abcdef", True
    )


def test_merge_never_hides_a_glyph():  # Review Focus 3
    a = Appearance("✹", "#000000", "#e8e8e8", False)
    merged = merge_appearance(a, OverlayStyle("#abcdef", "40", None))
    assert merged.text == "✹" and merged.bg == "#abcdef"


def test_group_outlines_insets_colors_and_duplicates():  # Review Focus 4
    d = Debug(groups=(Group(((0, 0), (0, 1))), Group(((0, 1), (0, 1), (1, 1)))))
    assert group_outlines(d) == [
        ((0, 0), GROUP_COLORS[0], 2),
        ((0, 1), GROUP_COLORS[0], 2),
        ((0, 1), GROUP_COLORS[1], 5),
        ((1, 1), GROUP_COLORS[1], 2),
    ]


def test_group_colors_cycle():
    d = Debug(groups=tuple(Group(((i, 0),)) for i in range(7)))
    assert group_outlines(d)[6] == ((6, 0), GROUP_COLORS[0], 2)


def test_legend_entries_known_first_then_custom():
    d = Debug(labels={(0, 0): "zeta", (0, 1): "mine", (0, 2): "safe"})
    assert legend_entries(d) == [
        ("safe", LABEL_COLORS["safe"]),
        ("mine", LABEL_COLORS["mine"]),
        ("zeta", AUTO_COLORS[0]),
    ]


def test_group_notes():
    d = Debug(groups=(Group(((0, 0),), "subset A"), Group(((0, 1),))))
    assert group_notes(d) == "① subset A  ②"
    assert group_notes(Debug()) == ""


def test_hover_text():
    d = Debug(
        probabilities={(1, 2): 0.125},
        labels={(1, 2): "frontier"},
        groups=(Group(((1, 2),)), Group(((0, 0),)), Group(((1, 2),))),
    )
    assert hover_text((1, 2), d) == "(1, 2)  p=12%  label=frontier  groups ①③"
    assert hover_text((0, 0), d) == "(0, 0)  groups ②"
    assert hover_text((2, 2), None) == "(2, 2)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `VIRTUAL_ENV= uv run pytest tests/test_overlay.py -q`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'minesweeper.gui.overlay'`

- [ ] **Step 3: Implement** — `minesweeper/gui/overlay.py`

```python
"""Pure drawing rules for the solver debug overlay (no tkinter, unit-tested)."""
from __future__ import annotations

from dataclasses import dataclass

from minesweeper.core.board import Cell
from minesweeper.core.game import CellState
from minesweeper.gui.render import Appearance
from minesweeper.solver.debug import KNOWN_LABELS, Debug

PROB_LOW, PROB_MID, PROB_HIGH = "#3cb371", "#f2d64b", "#e04040"
LABEL_COLORS = {
    "safe": "#3cb371",
    "mine": "#e04040",
    "frontier": "#4a7fd6",
    "considered": "#9b59b6",
}
AUTO_COLORS = (
    "#ff8c00", "#00a3a3", "#c71585", "#6b8e23",
    "#8b4513", "#1e90ff", "#b8860b", "#708090",
)
GROUP_COLORS = ("#ff1493", "#00ced1", "#ff8c00", "#7cfc00", "#9370db", "#ffd700")
MIN_TEXT_CELL = 24  # px; smaller cells show colour only


def _mix(a: str, b: str, t: float) -> str:
    ra = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    rb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb))


def probability_color(p: float) -> str:
    """Green (0, safe) → yellow (0.5) → red (1, mine)."""
    p = min(1.0, max(0.0, p))
    if p <= 0.5:
        return _mix(PROB_LOW, PROB_MID, p / 0.5)
    return _mix(PROB_MID, PROB_HIGH, (p - 0.5) / 0.5)


def label_colors(debug: Debug) -> dict[str, str]:
    """Colour for every label in use: fixed for known labels, else AUTO_COLORS by name."""
    used = set(debug.labels.values())
    colors = {label: LABEL_COLORS[label] for label in KNOWN_LABELS if label in used}
    custom = sorted(used - LABEL_COLORS.keys())
    for i, label in enumerate(custom):
        colors[label] = AUTO_COLORS[i % len(AUTO_COLORS)]
    return colors


def circled(n: int) -> str:
    return chr(0x2460 + n - 1) if 1 <= n <= 20 else f"({n})"


@dataclass(frozen=True)
class OverlayStyle:
    fill: str | None    # replaces the cell background
    text: str | None    # replaces an empty cell text
    border: str | None  # inner border for a label when a probability is also shown


def overlay_style(
    debug: Debug,
    cell: Cell,
    state: CellState,
    cell_size: int,
    colors: dict[str, str] | None = None,
) -> OverlayStyle | None:
    if state is CellState.REVEALED:
        return None
    p = debug.probabilities.get(cell)
    label = debug.labels.get(cell)
    if p is None and label is None:
        return None
    if label is not None:
        label_color = (colors if colors is not None else label_colors(debug)).get(label)
    else:
        label_color = None
    if p is None:
        return OverlayStyle(label_color, None, None)
    text = f"{round(p * 100)}" if cell_size >= MIN_TEXT_CELL and state is CellState.HIDDEN else None
    return OverlayStyle(probability_color(p), text, label_color)


def merge_appearance(appearance: Appearance, style: OverlayStyle | None) -> Appearance:
    """Apply an overlay to a cell's normal look. Never hides an existing glyph."""
    if style is None:
        return appearance
    text, fg = appearance.text, appearance.fg
    if style.text is not None and not appearance.text:
        text, fg = style.text, "#000000"
    return Appearance(text, fg, style.fill or appearance.bg, appearance.raised)


def group_outlines(debug: Debug) -> list[tuple[Cell, str, int]]:
    """(cell, colour, inset px) per group membership; repeated memberships nest inward."""
    depth: dict[Cell, int] = {}
    outlines = []
    for i, group in enumerate(debug.groups):
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        for cell in dict.fromkeys(group.cells):  # a cell listed twice gets one outline
            k = depth.get(cell, 0)
            depth[cell] = k + 1
            outlines.append((cell, color, 2 + 3 * k))
    return outlines


def legend_entries(debug: Debug) -> list[tuple[str, str]]:
    return list(label_colors(debug).items())


def group_notes(debug: Debug) -> str:
    return "  ".join(
        f"{circled(i)} {group.note}".rstrip() for i, group in enumerate(debug.groups, 1)
    )


def hover_text(cell: Cell, debug: Debug | None) -> str:
    parts = [f"({cell[0]}, {cell[1]})"]
    if debug is not None:
        p = debug.probabilities.get(cell)
        if p is not None:
            parts.append(f"p={round(p * 100)}%")
        label = debug.labels.get(cell)
        if label is not None:
            parts.append(f"label={label}")
        numbers = [circled(i) for i, g in enumerate(debug.groups, 1) if cell in g.cells]
        if numbers:
            parts.append("groups " + "".join(numbers))
    return "  ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `VIRTUAL_ENV= uv run pytest -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add minesweeper/gui/overlay.py tests/test_overlay.py
git commit -m "feat: pure style rules for the solver debug overlay

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: GUI wiring and README

**Files:**
- Modify: `minesweeper/gui/app.py` (class `App` only; `CustomDialog`, `_enable_windows_dpi_awareness`, `run` unchanged)
- Modify: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1–2; existing `App` methods.
- Produces: `App.debug: Debug | None`, `App.show_overlay: tk.BooleanVar`, `App.groups_var`, `App.hover_var`, `App.legend: tk.Frame`; canvas items tagged `"overlay"`; `App._toggle_overlay(event=None)`.

GUI widget code has no unit tests (logic lives in Tasks 1–2); it is verified by a scripted drive (Step 3).

- [ ] **Step 1: Edit imports** in `minesweeper/gui/app.py` — change the module docstring and add the overlay/debug imports:

```python
"""tkinter front-end. Thin: rules live in core, drawing decisions in render/overlay."""
```

After the `from minesweeper.core.game import CellState, Game, Status` line add:

```python
from minesweeper.gui.overlay import (
    group_notes,
    group_outlines,
    hover_text,
    label_colors,
    legend_entries,
    merge_appearance,
    overlay_style,
    probability_color,
)
```

After the `from minesweeper.solver import SOLVERS, Solver, apply_move, solver_rng` line add:

```python
from minesweeper.solver.debug import Debug, prepare_debug
```

- [ ] **Step 2: Edit `App`**

(a) In `__init__`, after `self._texts: dict[Cell, int] = {}` add:

```python
        self.debug: Debug | None = None  # overlay from the last AI move
```

(b) In `_build_ai_panel`, replace everything from `self.speed.pack(side="left", padx=6)` to the end of the method with:

```python
        self.speed.pack(side="left", padx=6)
        self.show_overlay = tk.BooleanVar(value=True)
        tk.Checkbutton(
            panel, text="Show overlay (O)", variable=self.show_overlay,
            command=self._refresh_overlay,
        ).pack(side="left", padx=6)
        self.root.bind("<KeyPress-o>", self._toggle_overlay)
        self.root.bind("<KeyPress-O>", self._toggle_overlay)

        wrap = dict(anchor="w", justify="left", wraplength=500)
        self.reason_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.reason_var, **wrap).pack(fill="x", padx=8)
        self.groups_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.groups_var, **wrap).pack(fill="x", padx=8)
        self.legend = tk.Frame(self.root)
        self.legend.pack(fill="x", padx=8)
        self.hover_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.hover_var, anchor="w", fg="#555555").pack(
            fill="x", padx=8
        )
```

(c) In `_bind_mouse`, after the three `self.canvas.bind(...)` lines for buttons add:

```python
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self.hover_var.set(""))
```

(d) In `new_game`, after `self._ai_cell = None` add `self.debug = None`; and replace the line `self._redraw_all()` (right after the create-items loop) with:

```python
        self._refresh_overlay()
        self.hover_var.set("")
```

(e) Replace `_draw_cell` and `_redraw_all` with:

```python
    def _overlay_on(self) -> bool:
        return self.debug is not None and self.show_overlay.get()

    def _draw_cell(self, cell: Cell, colors: dict[str, str] | None = None) -> None:
        a = cell_appearance(self.game, *cell)
        if self._overlay_on():
            state = self.game.state(*cell)
            a = merge_appearance(a, overlay_style(self.debug, cell, state, self.cell_size, colors))
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
        colors = label_colors(self.debug) if self._overlay_on() else None
        for cell in self._rects:
            self._draw_cell(cell, colors)
        self.canvas.tag_raise("overlay")  # keep borders/outlines above a raised AI cell

    # --- overlay -------------------------------------------------------------------

    def _refresh_overlay(self) -> None:
        self._redraw_all()
        self._draw_overlay_items()
        self._update_overlay_widgets()

    def _toggle_overlay(self, _event: tk.Event | None = None) -> None:
        self.show_overlay.set(not self.show_overlay.get())
        self._refresh_overlay()

    def _draw_overlay_items(self) -> None:
        self.canvas.delete("overlay")
        if not self._overlay_on():
            return
        s = self.cell_size
        colors = label_colors(self.debug)
        for cell in self.debug.labels:
            style = overlay_style(self.debug, cell, self.game.state(*cell), s, colors)
            if style is not None and style.border is not None:
                x, y = cell[1] * s, cell[0] * s
                self.canvas.create_rectangle(
                    x + 3, y + 3, x + s - 3, y + s - 3,
                    outline=style.border, width=3, tags="overlay",
                )
        for (r, c), color, inset in group_outlines(self.debug):
            inset = min(inset, s // 3)
            x, y = c * s, r * s
            self.canvas.create_rectangle(
                x + inset, y + inset, x + s - inset, y + s - inset,
                outline=color, width=2, dash="-", tags="overlay",
            )

    def _update_overlay_widgets(self) -> None:
        on = self._overlay_on()
        self.groups_var.set(group_notes(self.debug) if on else "")
        for widget in self.legend.winfo_children():
            widget.destroy()
        if not on:
            return
        for label, color in legend_entries(self.debug):
            tk.Label(self.legend, bg=color, width=2).pack(side="left", padx=(6, 2))
            tk.Label(self.legend, text=label).pack(side="left")
        if self.debug.probabilities:
            tk.Label(self.legend, text="0%").pack(side="left", padx=(12, 2))
            bar = tk.Canvas(self.legend, width=100, height=10, highlightthickness=0)
            for i in range(50):
                bar.create_rectangle(
                    i * 2, 0, i * 2 + 2, 10, width=0, fill=probability_color(i / 49)
                )
            bar.pack(side="left")
            tk.Label(self.legend, text="100%").pack(side="left", padx=2)

    def _on_motion(self, event: tk.Event) -> None:
        cell = pixel_to_cell(event.x, event.y, self.cell_size, self.config.rows, self.config.cols)
        debug = self.debug if self._overlay_on() else None
        self.hover_var.set(hover_text(cell, debug) if cell is not None else "")
```

(f) Manual moves clear the overlay. Replace `_on_left`, `_on_flag`, `_on_chord` with:

```python
    def _on_left(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is None:
            return
        if self.game.state(*cell) is CellState.REVEALED:
            result = self.game.chord(*cell)
        else:
            result = self.game.reveal(*cell)
        self._manual_move(result.revealed)

    def _on_flag(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None and self.game.toggle_flag(*cell):
            self._manual_move([cell])

    def _on_chord(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None:
            self._manual_move(self.game.chord(*cell).revealed)

    def _manual_move(self, cells) -> None:
        """A player move makes the last AI overlay stale, so drop it."""
        if cells and self.debug is not None:
            self.debug = None
            self._refresh_overlay()
        self._after_move(cells)
```

(g) In `ai_step`, replace the solver-creation block and everything after the `apply_move` check with:

```python
        if self.solver is None:
            self.solver = SOLVERS[self.solver_var.get()](solver_rng(self.game.seed))
            try:
                self.solver.debug = True  # the GUI is watching: build overlay data
            except AttributeError:
                pass  # e.g. a solver using __slots__; it just won't know
```

(keep the existing `try: move = ... except` and `if not apply_move(...)` blocks unchanged), then:

```python
        self._ai_cell = move.cell
        self.debug, problems = prepare_debug(
            getattr(move, "debug", None), self.game.rows, self.game.cols
        )
        prefix = "" if move.certain else "guess: "
        reason = f"{move.action} {move.cell} — {prefix}{move.reason}"
        if problems:
            reason += f"  [overlay: {problems[0]}]"
        self.reason_var.set(reason)
        self._refresh_overlay()
        self._after_move([])
        return True
```

- [ ] **Step 3: Verify**

Run: `VIRTUAL_ENV= uv run pytest -q`
Expected: all PASS

Run: `VIRTUAL_ENV= uv run python -c "import minesweeper.gui.app; print('ok')"`
Expected: `ok`

Scripted GUI drive (write to the scratchpad, **not** the repo), e.g. `$SCRATCH/overlay_drive.py`:

```python
import tkinter as tk

from minesweeper.core.config import GameConfig
from minesweeper.core.game import CellState
from minesweeper.gui.app import App
from minesweeper.solver import SOLVERS, Debug, Group, Move


class DemoSolver:
    """Throwaway: fake overlay data around the next hidden cell. Not a real solver."""

    name = "demo"

    def __init__(self, rng):
        self.rng = rng

    def next_move(self, view):
        hidden = view.hidden_cells()
        target = hidden[0]
        probs = {c: (i % 10) / 9 for i, c in enumerate(hidden[:40])}
        labels = {hidden[1]: "safe", hidden[2]: "mine", hidden[3]: "frontier", hidden[4]: "custom"}
        groups = (Group(tuple(hidden[:3]), "subset demo"), Group(tuple(hidden[1:4]), "overlap"))
        debug = Debug(probs, labels, groups) if getattr(self, "debug", False) else None
        return Move("reveal", target, "demo", certain=False, debug=debug)


class SlotsSolver:
    __slots__ = ("rng",)
    name = "slots"

    def __init__(self, rng):
        self.rng = rng

    def next_move(self, view):
        return Move("reveal", view.hidden_cells()[0], "slots", False, debug={"bad": 1})


SOLVERS["demo"] = DemoSolver
SOLVERS["slots"] = SlotsSolver
root = tk.Tk()
app = App(root, GameConfig(9, 9, 10, seed=7))
app.solver_var.set("demo")
root.update()
app.ai_step()
root.update()
n = len(app.canvas.find_withtag("overlay"))
print("overlay items:", n, "| groups:", app.groups_var.get(), "| legend widgets:", len(app.legend.winfo_children()))
assert n > 0 and app.groups_var.get() and app.legend.winfo_children()
app._toggle_overlay(); root.update()
assert not app.canvas.find_withtag("overlay") and not app.groups_var.get()   # Review Focus 1
app._toggle_overlay(); root.update()
assert len(app.canvas.find_withtag("overlay")) == n
s = app.cell_size
hid = next(c for c in app.debug.probabilities if app.game.state(*c) is CellState.HIDDEN)
app.canvas.event_generate("<Motion>", x=hid[1] * s + s // 2, y=hid[0] * s + s // 2); root.update()
print("hover:", app.hover_var.get()); assert "p=" in app.hover_var.get()
# screenshot here if a screenshot tool is available (grim on Wayland, import on X11)
app.canvas.event_generate("<Button-3>", x=hid[1] * s + s // 2, y=hid[0] * s + s // 2); root.update()
assert app.debug is None and not app.canvas.find_withtag("overlay")        # manual move clears
app.new_game(); app.solver_var.set("slots"); app._reset_solver(); root.update()
assert app.ai_step()                                                        # Review Focus 5
print("slots reason:", app.reason_var.get()); assert "[overlay: debug must be a Debug" in app.reason_var.get()
root.destroy()
print("OK")
```

Run: `VIRTUAL_ENV= uv run python $SCRATCH/overlay_drive.py`
Expected: prints overlay item count > 0, group notes `① subset demo  ② overlap`, a hover line containing `p=`, the slots reason with `[overlay: debug must be a Debug, got dict]`, then `OK`. Take a screenshot after the first `ai_step` and look at it: heat colours, percentages, a label border, two dashed group outlines, legend row.

- [ ] **Step 4: README** — insert before the `## Platform notes` heading:

````markdown
## Solver overlay (debugging your AI)

A solver can attach overlay data to any move; the GUI paints it on the board
(batch runs ignore it). The GUI sets `solver.debug = True`, so you can skip
building it otherwise.

```python
from minesweeper.solver import Debug, Group, Move

debug = Debug(
    probabilities={(3, 4): 0.12, (3, 5): 0.5},          # 0 safe … 1 mine → green…red
    labels={(2, 2): "safe", (5, 1): "mine", (4, 4): "frontier"},  # or any string
    groups=(Group(((2, 3), (3, 3)), note="subset rule"),),
)
return Move("reveal", (3, 4), "lowest mine probability", certain=False,
            debug=debug if getattr(self, "debug", False) else None)
```

Toggle with **Show overlay** or the `O` key; hover a cell for its values.
Invalid entries are skipped and the first problem is shown after the reason.
````

- [ ] **Step 5: Commit**

```bash
git add minesweeper/gui/app.py README.md
git commit -m "feat: draw solver debug overlay with legend, group notes and hover info

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
