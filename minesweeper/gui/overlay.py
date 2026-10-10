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
    elif style.fill is not None and appearance.text:
        fg = "#000000"  # a red ⚑/✗ would vanish on a red overlay fill
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


def group_notes(debug: Debug, limit: int = 12) -> str:
    """'① note  ② note …', at most `limit` groups and 40 chars per note."""
    notes = [
        f"{circled(i)} {clip(group.note, 40)}".rstrip()
        for i, group in enumerate(debug.groups[:limit], 1)
    ]
    if len(debug.groups) > limit:
        notes.append(f"… +{len(debug.groups) - limit} more")
    return "  ".join(notes)


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


def clip(text: str, n: int) -> str:
    """Shorten to at most n characters, ending with … when cut."""
    return text if len(text) <= n else text[: n - 1] + "…"
