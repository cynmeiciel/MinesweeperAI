import math

import pytest

from minesweeper.solver import Debug, Group, Move
from minesweeper.solver.debug import (
    KNOWN_LABELS,
    enable_overlay,
    prepare_debug,
    sanitize_debug,
    validate_debug,
)


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


class ExplodingMapping(dict):
    def items(self):
        raise RuntimeError("boom")

    def __iter__(self):
        raise RuntimeError("boom")


class BadStr:
    def __str__(self):
        raise RuntimeError("no str")


@pytest.mark.parametrize(
    "debug",
    [
        Debug(probabilities={(0, 0): 10**400}),          # math.isfinite overflows
        Debug(probabilities=ExplodingMapping({(0, 0): 0.5})),
        Debug(groups=(Group(((0, 0),), BadStr()),)),
    ],
)
def test_prepare_debug_never_raises(debug):
    clean, problems = prepare_debug(debug, 3, 3)
    assert problems  # reported, not raised
    assert clean is None or isinstance(clean, Debug)


def test_fraction_probability_accepted():
    from fractions import Fraction

    clean, problems = prepare_debug(Debug(probabilities={(0, 0): Fraction(1, 4)}), 3, 3)
    assert problems == [] and clean.probabilities[(0, 0)] == 0.25


def test_problem_text_is_clipped():
    problems = validate_debug(Debug(probabilities={(0, 0): [0.5] * 20000}), 3, 3)
    assert len(problems) == 1 and len(problems[0]) <= 120


class PlainSolver:
    pass


class SlotsSolver:
    __slots__ = ()


class SolverWithDebugMethod:
    def debug(self, msg):
        return msg


def test_enable_overlay_sets_specific_flag():
    s = PlainSolver()
    enable_overlay(s)
    assert s.overlay_enabled is True


def test_enable_overlay_tolerates_slots():
    enable_overlay(SlotsSolver())  # must not raise


def test_enable_overlay_leaves_debug_method_alone():
    s = SolverWithDebugMethod()
    enable_overlay(s)
    assert s.debug("hi") == "hi"
