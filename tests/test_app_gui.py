"""A few end-to-end checks of the Tk wiring. Skipped when no display is available."""
import threading
import time

import pytest

tk = pytest.importorskip("tkinter")

from minesweeper.core.config import GameConfig  # noqa: E402
from minesweeper.gui.app import App  # noqa: E402
from minesweeper.solver import SOLVERS, Move  # noqa: E402

GATE = threading.Event()


class SlowSolver:
    name = "slow-test"

    def __init__(self, rng):
        pass

    def next_move(self, view):
        GATE.wait(5)
        return Move("reveal", view.hidden_cells()[0], "slow", certain=False)


@pytest.fixture
def app(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    monkeypatch.setitem(SOLVERS, "slow-test", SlowSolver)
    GATE.clear()
    app = App(root, GameConfig(9, 9, 10, seed=1))
    app.solver_var.set("slow-test")
    app._solver_changed()
    yield app
    GATE.set()
    root.destroy()


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.root.update()
        time.sleep(0.01)


def test_manual_move_clears_thinking_text(app):
    assert app.ai_step()
    pump(app, 0.1)
    assert app.reason_var.get().startswith("Thinking")
    app._manual_move(app.game.reveal(4, 4).revealed)
    assert not app.runner.busy
    assert not app.reason_var.get().startswith("Thinking")


def test_solver_change_clears_thinking_text(app):
    assert app.ai_step()
    pump(app, 0.1)
    app.solver_var.set("random")
    app._solver_changed()
    assert not app.reason_var.get().startswith("Thinking")


def test_cancel_button_says_cancelled(app):
    assert app.ai_step()
    pump(app, 0.1)
    app.cancel_hint()
    assert app.reason_var.get() == "Cancelled"
