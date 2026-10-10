# Background Hints + Overlay Port — Design

Date: 2026-10-10
Status: Approved in conversation, pending written-spec review
Builds on: `2026-09-29-solver-debug-overlay-design.md` (overlay data model and
drawing rules are unchanged and not repeated here).

## 1. Goal

1. A slow solver (the team's lv3 DFS can take ~17–22 s on some Expert
   positions) must never freeze the GUI. Hint/Solve run in a background
   thread with a visible "Thinking…" state and a Cancel button.
2. The solver debug overlay (built on the old Step/Auto GUI, branch
   `feat/solver-overlay`) is ported onto the team's Hint/Solve GUI on `main`.
3. The standard chord rule is restored (team decision): chord only when the
   flag count equals the number.

Out of scope: solver logic (the team's), Auto play (pending team decision),
process-based cancellation.

## 2. Constraints

- Stdlib only; Linux, Windows, macOS (Tk 8.6+); BMP-only glyphs.
- Tk is touched only from the main thread. Worker threads never call Tk.
- Solver interface unchanged: `next_move(view) -> Move`, may raise
  `SolverStuck` or any exception.
- Existing Hint (show only) and Solve (apply one move) semantics, `h`/`s` key
  bindings and the `AI -> STUCK` message stay as the team built them.

## 3. `HintRunner` — `minesweeper/gui/hint_runner.py` (no tkinter)

```python
@dataclass(frozen=True)
class HintResult:
    job: int
    move: Move | None             # set on success
    error: BaseException | None   # SolverStuck or any other exception
    seconds: float

class HintRunner:
    def start(self, solver, view: PlayerView) -> int   # returns job id; cancels any running job first
    def cancel(self) -> None                            # abandon the current job (thread keeps running)
    def poll(self) -> HintResult | None                 # non-blocking; only the current job's result
    @property busy -> bool                              # a job started and not yet polled/cancelled
    @property elapsed -> float                          # seconds since start of current job, 0.0 if idle
```

- Each `start` increments a job counter and spawns a `threading.Thread(daemon=True)`
  that calls `solver.next_move(view)`, timing it with `time.perf_counter`,
  and puts a `HintResult` on a `queue.Queue`. Every exception (including
  `BaseException` subclasses other than `KeyboardInterrupt`/`SystemExit`) is
  captured into `error`; nothing propagates out of the thread.
- `poll` drains the queue, discards results whose `job` is not the current
  job, and returns the current job's result once (then `busy` is False).
- `cancel` marks the current job abandoned (its result will be discarded);
  `busy` becomes False immediately.
- `PlayerView` is a frozen snapshot, so the worker never sees later moves.

## 4. GUI behaviour — `minesweeper/gui/app.py`

- `ai_step()` (Hint) and `ai_solve()` (Solve) no longer compute inline. They
  create the solver lazily (as now, then `enable_overlay(solver)`), call
  `runner.start(solver, game.view())`, remember the intent (`"hint"` or
  `"solve"`) and schedule `_poll_hint` every 50 ms via `root.after`.
- While busy: Hint and Solve buttons disabled, **Cancel** button enabled, the
  `h`/`s` keys do nothing, the reason line shows `Thinking… 3.2 s`
  (one decimal, refreshed each poll).
- When a result arrives:
  - success, intent hint → show it as now, prefixed with the time:
    `Hint (2.1 s): reveal (3, 4) — guess: <reason>`; overlay from `move.debug`.
  - success, intent solve → `apply_move`; if illegal show
    `illegal move: <action> <cell>` (overlay still shown, it explains the
    choice); else show as above with `Solve (2.1 s): …` and `_after_move`.
  - `SolverStuck` → `AI -> STUCK`, AI highlight and overlay cleared.
  - other exception → `solver error: <exc>`, overlay cleared.
  - Buttons re-enabled, Cancel disabled.
- **Cancel** (button): `runner.cancel()`, discard the solver instance
  (`self.solver = None`, the abandoned thread may still use it), reason line
  `Cancelled`, buttons restored.
- Automatic cancel (same as Cancel but reason line unchanged): any manual
  board move that changed the board, `new_game` (covers New/F2/presets/
  Custom/face button), and changing the solver in the dropdown.
- Hint/Solve while the game is over: nothing happens (as now).

## 5. Overlay port

- Copied unchanged from `feat/solver-overlay` (final state, commit 039590d):
  `minesweeper/solver/debug.py`, `minesweeper/gui/overlay.py`,
  `tests/test_debug.py`, `tests/test_overlay.py`.
- `Move` gains `debug: Debug | None = None` alongside the team's
  `SolverStuck`; `minesweeper.solver` exports `Debug`, `Group`.
- GUI: overlay widgets and drawing exactly as in the overlay spec §4.2
  (Show overlay (O) checkbox, group notes, legend, hover line, canvas items
  tagged `"overlay"`, `merge_appearance`, caps), driven by Hint/Solve results.
  Overlay state is cleared on manual move, new game, solver change, stuck or
  error; kept when the toggle is switched off.
- The batch-ignores-debug test from the overlay branch is re-added to
  `tests/test_batch.py`.
- README: the overlay section is re-added, wording adapted to Hint/Solve.

## 6. Chord rule

`Game.chord` requires `flagged == number` (the team's uncommitted revert on
`main`). `tests/test_chord.py::test_chord_allows_more_flags_than_number` is
replaced by `test_chord_refused_with_more_flags_than_number`, which asserts
the chord does nothing.

## 7. Testing

- `tests/test_hint_runner.py`: instant solver → result with move and
  seconds ≥ 0; slow solver blocked on a `threading.Event` → `busy` True and
  `poll()` None until released; `SolverStuck` and `RuntimeError` captured in
  `error`; `cancel()` while running → `busy` False and the late result is
  never returned; `start` while running → only the newest job's result is
  returned; `elapsed` grows while busy and is 0.0 when idle. Tests wait with
  bounded loops (≤ 2 s) so a bug cannot hang the suite.
- Overlay tests carried over; chord test replaced.
- GUI: scripted drive (scratchpad, not repo) with a fake slow solver: window
  keeps processing events while thinking, Cancel restores buttons, manual
  move cancels, Solve applies the move, overlay appears for Hint; plus a
  screenshot.
