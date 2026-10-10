import threading
import time

import pytest

from minesweeper.gui.hint_runner import HintRunner, describe_error
from minesweeper.solver.base import Move, SolverStuck

MOVE = Move("reveal", (0, 0), "test", True)


class Instant:
    def next_move(self, view):
        return MOVE


class Blocking:
    """Blocks until released, so tests control when the answer arrives."""

    def __init__(self, move=MOVE):
        self.started = threading.Event()
        self.release = threading.Event()
        self.move = move

    def next_move(self, view):
        self.started.set()
        self.release.wait(5)
        return self.move


class Raising:
    def __init__(self, exc):
        self.exc = exc

    def next_move(self, view):
        raise self.exc


class ReturnsNone:
    def next_move(self, view):
        return None


def wait_result(runner, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = runner.poll()
        if result is not None:
            return result
        time.sleep(0.005)
    pytest.fail("no result within timeout")


def test_idle_runner():
    r = HintRunner()
    assert not r.busy and r.elapsed == 0.0 and r.poll() is None


def test_instant_result_returned_once():
    r = HintRunner()
    job = r.start(Instant(), view=None)
    res = wait_result(r)
    assert res.job == job and res.move is MOVE and res.error is None and res.seconds >= 0
    assert not r.busy and r.poll() is None


def test_view_passed_to_solver():
    seen = []

    class Spy:
        def next_move(self, view):
            seen.append(view)
            return MOVE

    r = HintRunner()
    r.start(Spy(), "VIEW")
    wait_result(r)
    assert seen == ["VIEW"]


def test_slow_solver_does_not_block_caller():
    r = HintRunner()
    s = Blocking()
    t0 = time.monotonic()
    r.start(s, None)
    assert time.monotonic() - t0 < 0.5
    assert s.started.wait(2)
    assert r.busy and r.poll() is None
    time.sleep(0.02)
    assert r.elapsed > 0
    s.release.set()
    assert wait_result(r).move is MOVE


@pytest.mark.parametrize("exc", [SolverStuck("AI -> STUCK"), RuntimeError("boom"), SystemExit(3)])
def test_exceptions_are_captured(exc):
    r = HintRunner()
    r.start(Raising(exc), None)
    res = wait_result(r)
    assert res.move is None and res.error is exc


def test_non_move_result_becomes_type_error():  # Review Focus 1
    r = HintRunner()
    r.start(ReturnsNone(), None)
    res = wait_result(r)
    assert res.move is None and isinstance(res.error, TypeError)
    assert "NoneType" in str(res.error)


def test_cancel_discards_late_result():
    r = HintRunner()
    s = Blocking()
    r.start(s, None)
    assert s.started.wait(2)
    r.cancel()
    assert not r.busy and r.elapsed == 0.0
    s.release.set()
    time.sleep(0.1)
    assert r.poll() is None


def test_restart_returns_only_newest_job():
    r = HintRunner()
    old = Blocking(Move("reveal", (1, 1), "old", True))
    r.start(old, None)
    assert old.started.wait(2)
    newer = r.start(Instant(), None)
    old.release.set()
    res = wait_result(r)
    assert res.job == newer and res.move is MOVE
    time.sleep(0.1)
    assert r.poll() is None


def test_worker_is_daemon_thread():  # Review Focus 2
    r = HintRunner()
    s = Blocking()
    job = r.start(s, None)
    assert s.started.wait(2)
    worker = next(t for t in threading.enumerate() if t.name == f"hint-{job}")
    assert worker.daemon
    s.release.set()


@pytest.mark.parametrize(
    "exc,expected",
    [
        (AssertionError(), "AssertionError"),
        (ValueError(), "ValueError"),
        (ValueError("bad cell"), "ValueError: bad cell"),
        (SolverStuck("AI -> STUCK"), "SolverStuck: AI -> STUCK"),
    ],
)
def test_describe_error(exc, expected):
    assert describe_error(exc) == expected
