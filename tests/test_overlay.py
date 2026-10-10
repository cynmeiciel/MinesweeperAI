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
    clip,
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


def test_merge_makes_glyph_readable_on_overlay_fill():
    flag = Appearance("⚑", "#ff0000", "#c0c0c0", True)
    merged = merge_appearance(flag, OverlayStyle(PROB_HIGH, None, None))
    assert merged.text == "⚑" and merged.bg == PROB_HIGH and merged.fg == "#000000"


def test_group_notes_capped():
    d = Debug(groups=tuple(Group(((0, 0),), f"note {i}") for i in range(30)))
    text = group_notes(d, limit=5)
    assert text.startswith("① note 0") and text.endswith("… +25 more")
    assert "note 5" not in text


def test_group_notes_clip_long_note():
    d = Debug(groups=(Group(((0, 0),), "x" * 500),))
    assert len(group_notes(d)) <= 70


def test_clip():
    assert clip("short", 10) == "short"
    assert clip("abcdefghijkl", 10) == "abcdefghi…"
