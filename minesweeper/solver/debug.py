"""Optional overlay data a solver can attach to a Move for the GUI.

Never imports tkinter. Batch runs ignore it; the GUI validates and sanitises
it so a bug in a solver's debug output can never crash the program.
"""
from __future__ import annotations

import math
import numbers
import reprlib
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
    """Any real number in [0, 1] (int, float, Fraction, numpy scalars…), but not bool."""
    if not isinstance(p, numbers.Real) or isinstance(p, bool):
        return False
    try:
        value = float(p)
    except (OverflowError, ValueError, TypeError):
        return False
    return math.isfinite(value) and 0 <= value <= 1


def _short(obj: object, limit: int = 60) -> str:
    """repr() for error messages: bounded length, never raises."""
    try:
        text = reprlib.repr(obj)
    except Exception:
        text = f"<unprintable {type(obj).__name__}>"
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _check(debug: Debug, rows: int, cols: int) -> tuple[Debug, list[str]]:
    """Like _check_entries, but a solver's hostile data can never raise out of here."""
    try:
        return _check_entries(debug, rows, cols)
    except Exception as exc:
        return Debug(), [_short(f"overlay data unreadable: {type(exc).__name__}: {exc}", 110)]


def _check_entries(debug: Debug, rows: int, cols: int) -> tuple[Debug, list[str]]:
    """Return (copy with invalid entries dropped, problems found)."""
    problems: list[str] = []

    probabilities: dict[Cell, float] = {}
    if isinstance(debug.probabilities, Mapping):
        for cell, p in debug.probabilities.items():
            if not _on_board(cell, rows, cols):
                problems.append(f"probability cell {_short(cell)} is off the board")
            elif not _is_probability(p):
                problems.append(f"probability {_short(p)} at {cell} is not a number in [0, 1]")
            else:
                probabilities[cell] = float(p)
    else:
        problems.append("probabilities must be a dict")

    labels: dict[Cell, str] = {}
    if isinstance(debug.labels, Mapping):
        for cell, label in debug.labels.items():
            if not _on_board(cell, rows, cols):
                problems.append(f"label cell {_short(cell)} is off the board")
            elif not isinstance(label, str) or not label:
                problems.append(f"label {_short(label)} at {cell} must be a non-empty string")
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
                    problems.append(f"group {i} cell {_short(cell)} is off the board")
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


def enable_overlay(solver: object) -> None:
    """Tell a solver the GUI will draw its overlay: sets `solver.overlay_enabled = True`.

    Solvers check `getattr(self, "overlay_enabled", False)` to skip building a
    Debug during batch runs. Solvers that can't take the attribute (__slots__)
    are left alone.
    """
    try:
        solver.overlay_enabled = True
    except AttributeError:
        pass
