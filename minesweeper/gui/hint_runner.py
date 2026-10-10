"""Run a solver's next_move off the Tk thread (no tkinter here; unit-tested).

The worker only computes and puts a HintResult on a queue. The GUI polls
from the Tk thread. Python cannot kill a thread, so cancel() just makes the
running job's eventual answer stale; it is dropped when it arrives.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from minesweeper.core.game import PlayerView
from minesweeper.solver.base import Move


@dataclass(frozen=True)
class HintResult:
    job: int
    move: Move | None             # set on success
    error: BaseException | None   # SolverStuck, a solver bug, or a bad return value
    seconds: float


class HintRunner:
    def __init__(self) -> None:
        self._results: queue.Queue[HintResult] = queue.Queue()
        self._job = 0
        self._busy = False
        self._started = 0.0

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._started if self._busy else 0.0

    def start(self, solver, view: PlayerView) -> int:
        """Run solver.next_move(view) in the background. Supersedes any running job."""
        self._job += 1
        job = self._job
        self._busy = True
        self._started = time.perf_counter()
        threading.Thread(
            target=self._work, args=(job, solver, view), name=f"hint-{job}", daemon=True
        ).start()
        return job

    def cancel(self) -> None:
        """Stop waiting for the current job; its answer will be ignored."""
        self._job += 1
        self._busy = False

    def poll(self) -> HintResult | None:
        """The current job's result, once; None while still running or when idle."""
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                return None
            if self._busy and result.job == self._job:
                self._busy = False
                return result
            # otherwise a cancelled or superseded job: drop it

    def _work(self, job: int, solver, view: PlayerView) -> None:
        start = time.perf_counter()
        move, error = None, None
        try:
            answer = solver.next_move(view)
            if isinstance(answer, Move):
                move = answer
            else:
                error = TypeError(
                    f"next_move returned {type(answer).__name__}, expected Move"
                )
        except BaseException as exc:  # never let a solver kill the worker silently
            error = exc
        self._results.put(HintResult(job, move, error, time.perf_counter() - start))
