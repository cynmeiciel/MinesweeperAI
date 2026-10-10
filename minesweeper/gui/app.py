"""tkinter front-end. Thin: rules live in core, drawing decisions in render/overlay."""
from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox

from minesweeper.core.board import Cell
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, Status
from minesweeper.gui.hint_runner import HintResult, HintRunner
from minesweeper.gui.overlay import (
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
from minesweeper.gui.render import (
    FACES,
    cell_appearance,
    cell_font_size,
    cell_size_for,
    mouse_buttons,
    pixel_to_cell,
)
from minesweeper.solver import SOLVERS, Move, Solver, SolverStuck, apply_move, solver_rng
from minesweeper.solver.debug import Debug, enable_overlay, prepare_debug

AI_HIGHLIGHT = "#ff8c00"
GRID_LINE = "#808080"
LEGEND_LIMIT = 8  # label swatches shown; more would widen the window past the screen
POLL_MS = 50      # how often the Tk thread checks for a background solver's answer


class App:
    def __init__(self, root: tk.Tk, config: GameConfig) -> None:
        self.root = root
        self.config = config
        self.game: Game
        self.solver: Solver | None = None
        self._ai_cell: Cell | None = None
        self._timer_job: str | None = None
        self._rects: dict[Cell, int] = {}
        self._texts: dict[Cell, int] = {}
        self.debug: Debug | None = None  # overlay from the last AI answer
        self.runner = HintRunner()
        self._intent = "hint"            # what to do with the running job's answer
        self._poll_job: str | None = None

        root.title("Minesweeper")
        root.resizable(False, False)
        self._build_menu()
        self._build_header()
        self.canvas = tk.Canvas(root, highlightthickness=0, bg=GRID_LINE)
        self.canvas.pack(padx=8, pady=4)
        self._build_ai_panel()
        self.status_var = tk.StringVar()
        tk.Entry(
            root, textvariable=self.status_var, state="readonly", relief="flat"
        ).pack(fill="x", padx=8, pady=(0, 6))  # readonly Entry so the seed can be copied
        self._bind_mouse()
        self.new_game()

    # --- construction ----------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="New", accelerator="F2", command=self.new_game)
        presets = tk.Menu(game_menu, tearoff=0)
        for name, p in PRESETS.items():
            presets.add_command(
                label=f"{name.capitalize()} ({p.rows}x{p.cols}, {p.mines} mines)",
                command=lambda p=p: self.new_game(
                    replace(self.config, rows=p.rows, cols=p.cols, mines=p.mines, seed=None)
                ),
            )
        game_menu.add_cascade(label="Presets", menu=presets)
        game_menu.add_command(label="Custom…", command=self._custom)
        game_menu.add_separator()
        game_menu.add_command(label="Quit", command=self.root.destroy)
        menubar.add_cascade(label="Game", menu=game_menu)
        self.root.config(menu=menubar)
        self.root.bind("<F2>", lambda _e: self.new_game())
        self.root.bind("<KeyPress-h>", lambda _e: self.ai_step())
        self.root.bind("<KeyPress-H>", lambda _e: self.ai_step())
        self.root.bind("<KeyPress-s>", lambda _e: self.ai_solve())
        self.root.bind("<KeyPress-S>", lambda _e: self.ai_solve())

    def _build_header(self) -> None:
        header = tk.Frame(self.root)
        header.pack(fill="x", padx=8, pady=(6, 0))
        self.mines_var = tk.StringVar()
        self.time_var = tk.StringVar()
        self.face_var = tk.StringVar()
        tk.Label(header, textvariable=self.mines_var, width=10, anchor="w").pack(side="left")
        tk.Label(header, textvariable=self.time_var, width=10, anchor="e").pack(side="right")
        tk.Button(
            header, textvariable=self.face_var, font=("TkDefaultFont", 14), width=3,
            command=self.new_game,
        ).pack()

    def _build_ai_panel(self) -> None:
        panel = tk.Frame(self.root)
        panel.pack(fill="x", padx=8)
        tk.Label(panel, text="AI:").pack(side="left")
        self.solver_var = tk.StringVar(value=next(iter(SOLVERS)))
        tk.OptionMenu(
            panel, self.solver_var, *SOLVERS, command=lambda _v: self._solver_changed()
        ).pack(side="left")
        self.hint_btn = tk.Button(panel, text="Hint", command=self.ai_step)
        self.hint_btn.pack(side="left", padx=2)
        self.solve_btn = tk.Button(panel, text="Solve", command=self.ai_solve)
        self.solve_btn.pack(side="left", padx=2)
        self.cancel_btn = tk.Button(
            panel, text="Cancel", command=self.cancel_hint, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=2)
        self.show_overlay = tk.BooleanVar(value=True)
        tk.Checkbutton(
            panel, text="Show overlay (O)", variable=self.show_overlay,
            command=self._refresh_overlay,
        ).pack(side="left", padx=6)
        self.root.bind("<KeyPress-o>", self._toggle_overlay)
        self.root.bind("<KeyPress-O>", self._toggle_overlay)

        self.reason_var = tk.StringVar()
        tk.Entry(
            self.root, textvariable=self.reason_var, state="readonly", relief="flat"
        ).pack(fill="x", padx=8)
        wrap = dict(anchor="w", justify="left", wraplength=500)
        self.groups_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.groups_var, **wrap).pack(fill="x", padx=8)
        self.legend = tk.Frame(self.root)
        self.legend.pack(fill="x", padx=8)
        self.hover_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.hover_var, anchor="w", fg="#555555").pack(
            fill="x", padx=8
        )

    def _bind_mouse(self) -> None:
        system = self.root.tk.call("tk", "windowingsystem")
        aqua = system == "aqua"
        flag_btn, chord_btn = mouse_buttons(system, tk.TkVersion)
        self.canvas.bind("<Button-1>", self._on_left)
        self.canvas.bind(flag_btn, self._on_flag)
        self.canvas.bind(chord_btn, self._on_chord)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda _e: self.hover_var.set(""))
        if aqua:  # many Mac users have no right button
            self.canvas.bind("<Control-Button-1>", self._on_flag)

    # --- game lifecycle ----------------------------------------------------------

    def new_game(self, config: GameConfig | None = None) -> None:
        if config is not None:
            self.config = config
        self._abandon_hint()
        if self._timer_job is not None:
            self.root.after_cancel(self._timer_job)
            self._timer_job = None
        self.game = Game(self.config)
        self._reset_solver()
        self._ai_cell = None
        self.debug = None

        rows, cols = self.config.rows, self.config.cols
        self.cell_size = s = cell_size_for(
            rows, cols,
            int(self.root.winfo_screenwidth() * 0.85),
            int(self.root.winfo_screenheight() * 0.85) - 200,
            scale=self.root.winfo_fpixels("1i") / 96,
        )
        self.canvas.delete("all")
        self.canvas.config(width=cols * s, height=rows * s)
        font = ("TkDefaultFont", cell_font_size(s), "bold")
        self._rects.clear()
        self._texts.clear()
        for r in range(rows):
            for c in range(cols):
                x, y = c * s, r * s
                self._rects[(r, c)] = self.canvas.create_rectangle(x, y, x + s, y + s)
                self._texts[(r, c)] = self.canvas.create_text(x + s / 2, y + s / 2, font=font)
        self._refresh_overlay()
        self.hover_var.set("")
        self._update_header()
        self.reason_var.set("")
        cfg = self.config
        self.status_var.set(
            f"seed={self.game.seed}   {rows}x{cols}, {cfg.mines} mines ({cfg.density:.1%})   "
            f"first click: {cfg.first_click.name}, chord {'on' if cfg.chord else 'off'}, "
            f"{cfg.flood_fill.name}"
        )

    def _custom(self) -> None:
        dialog = CustomDialog(self.root, self.config)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            self.new_game(dialog.result)

    # --- drawing -------------------------------------------------------------------

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
        self.legend.configure(width=1, height=1)  # let the emptied frame shrink again
        if not on:
            return
        entries = legend_entries(self.debug)
        for label, color in entries[:LEGEND_LIMIT]:
            tk.Label(self.legend, bg=color, width=2).pack(side="left", padx=(6, 2))
            tk.Label(self.legend, text=clip(label, 16)).pack(side="left")
        if len(entries) > LEGEND_LIMIT:
            tk.Label(self.legend, text=f"+{len(entries) - LEGEND_LIMIT} more").pack(
                side="left", padx=6
            )
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

    def _update_header(self) -> None:
        self.mines_var.set(f"Mines: {self.game.mines_remaining}")
        self.time_var.set(f"Time: {int(self.game.stats.elapsed):03d}")
        self.face_var.set(FACES[self.game.status])

    def _tick(self) -> None:
        self._timer_job = None
        self._update_header()
        if self.game.status is Status.PLAYING:
            self._timer_job = self.root.after(250, self._tick)

    def _after_move(self, cells) -> None:
        if self.game.is_over:
            self._redraw_all()
        else:
            for cell in cells:
                self._draw_cell(cell)
        self._update_header()
        if self._timer_job is None and self.game.status is Status.PLAYING:
            self._tick()

    # --- mouse ---------------------------------------------------------------------

    def _cell_at(self, event: tk.Event) -> Cell | None:
        if self.game.is_over:
            return None
        return pixel_to_cell(event.x, event.y, self.cell_size, self.config.rows, self.config.cols)

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
        """A player move makes a pending or shown AI answer stale."""
        if cells:
            self._abandon_hint()
            old, self._ai_cell = self._ai_cell, None
            if self.debug is not None:
                self.debug = None
                self._refresh_overlay()
            elif old is not None:
                self._draw_cell(old)  # drop the orange outline
        self._after_move(cells)

    # --- AI ------------------------------------------------------------------------

    def _reset_solver(self) -> None:
        self.solver = None  # created lazily with the game's seed on the next request

    def _solver_changed(self) -> None:
        self._abandon_hint()
        self._reset_solver()
        self._ai_cell = None
        self.debug = None
        self._refresh_overlay()

    def ai_step(self) -> bool:
        """Hint: ask the solver in the background; show its move without playing it."""
        return self._ask_solver("hint")

    def ai_solve(self) -> bool:
        """Solve: ask the solver in the background, then play exactly that one move."""
        return self._ask_solver("solve")

    def cancel_hint(self) -> None:
        if self.runner.busy:
            self._abandon_hint()
            self.reason_var.set("Cancelled")

    def _ask_solver(self, intent: str) -> bool:
        if self.game.is_over or self.runner.busy:
            return False
        if self.solver is None:
            self.solver = SOLVERS[self.solver_var.get()](solver_rng(self.game.seed))
            enable_overlay(self.solver)
        self._intent = intent
        self.runner.start(self.solver, self.game.view())
        self._set_thinking(True)
        self._poll_hint()
        return True

    def _abandon_hint(self) -> None:
        """Stop waiting for a running solver; its late answer is ignored."""
        if self.runner.busy:
            self.runner.cancel()
            self.solver = None  # the abandoned thread may still be using this instance
        if self._poll_job is not None:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None
        self._set_thinking(False)

    def _set_thinking(self, on: bool) -> None:
        self.hint_btn.config(state="disabled" if on else "normal")
        self.solve_btn.config(state="disabled" if on else "normal")
        self.cancel_btn.config(state="normal" if on else "disabled")

    def _poll_hint(self) -> None:
        self._poll_job = None
        result = self.runner.poll()
        if result is None:
            if self.runner.busy:
                self.reason_var.set(f"Thinking… {self.runner.elapsed:.1f} s")
                self._poll_job = self.root.after(POLL_MS, self._poll_hint)
            return
        self._set_thinking(False)
        self._finish_hint(result)

    def _finish_hint(self, result: HintResult) -> None:
        if result.error is not None:
            self._ai_cell = None
            self.debug = None
            if isinstance(result.error, SolverStuck):
                self.reason_var.set("AI -> STUCK")
            else:
                self.reason_var.set(f"solver error: {result.error}")
            self._refresh_overlay()
            return
        move: Move = result.move
        self._ai_cell = move.cell
        self.debug, problems = prepare_debug(move.debug, self.game.rows, self.game.cols)
        label = "Hint" if self._intent == "hint" else "Solve"
        if self._intent == "solve" and not apply_move(self.game, move):
            text = f"illegal move: {move.action} {move.cell}"
        else:
            prefix = "" if move.certain else "guess: "
            text = (
                f"{label} ({result.seconds:.1f} s): {move.action} {move.cell}"
                f" — {prefix}{move.reason}"
            )
        if problems:
            text += f"  [overlay: {problems[0]}]"
        self.reason_var.set(text)
        self._refresh_overlay()
        if self._intent == "solve":
            self._after_move([])


class CustomDialog(tk.Toplevel):
    """Modal dialog for every GameConfig option. `result` is None if cancelled."""

    def __init__(self, parent: tk.Misc, config: GameConfig) -> None:
        super().__init__(parent)
        self.title("Custom game")
        self.transient(parent)
        self.resizable(False, False)
        self.result: GameConfig | None = None

        self.rows = tk.StringVar(value=str(config.rows))
        self.cols = tk.StringVar(value=str(config.cols))
        self.count_mode = tk.StringVar(value="mines")
        self.mines = tk.StringVar(value=str(config.mines))
        self.density = tk.StringVar(value=f"{config.density:.3f}")
        self.first_click = tk.StringVar(value=config.first_click.name)
        self.chord = tk.BooleanVar(value=config.chord)
        self.flood = tk.StringVar(value=config.flood_fill.name)
        self.seed = tk.StringVar(value="" if config.seed is None else str(config.seed))

        form = tk.Frame(self, padx=12, pady=10)
        form.pack()
        grid = dict(sticky="w", padx=4, pady=2)
        tk.Label(form, text="Rows").grid(row=0, column=0, **grid)
        tk.Entry(form, textvariable=self.rows, width=8).grid(row=0, column=1, **grid)
        tk.Label(form, text="Columns").grid(row=1, column=0, **grid)
        tk.Entry(form, textvariable=self.cols, width=8).grid(row=1, column=1, **grid)
        tk.Radiobutton(form, text="Mines", variable=self.count_mode, value="mines").grid(
            row=2, column=0, **grid)
        tk.Entry(form, textvariable=self.mines, width=8).grid(row=2, column=1, **grid)
        tk.Radiobutton(form, text="Density", variable=self.count_mode, value="density").grid(
            row=3, column=0, **grid)
        tk.Entry(form, textvariable=self.density, width=8).grid(row=3, column=1, **grid)
        tk.Label(form, text="First click").grid(row=4, column=0, **grid)
        tk.OptionMenu(form, self.first_click, *[f.name for f in FirstClick]).grid(
            row=4, column=1, **grid)
        tk.Label(form, text="Flood fill").grid(row=5, column=0, **grid)
        tk.OptionMenu(form, self.flood, *[f.name for f in FloodFill]).grid(
            row=5, column=1, **grid)
        tk.Checkbutton(form, text="Allow chord", variable=self.chord).grid(
            row=6, column=0, columnspan=2, **grid)
        tk.Label(form, text="Seed (blank = random)").grid(row=7, column=0, **grid)
        tk.Entry(form, textvariable=self.seed, width=12).grid(row=7, column=1, **grid)

        buttons = tk.Frame(self, pady=6)
        buttons.pack()
        tk.Button(buttons, text="OK", width=8, command=self._ok).pack(side="left", padx=4)
        tk.Button(buttons, text="Cancel", width=8, command=self.destroy).pack(side="left", padx=4)
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.grab_set()

    def _ok(self) -> None:
        try:
            rows, cols = int(self.rows.get()), int(self.cols.get())
            seed_text = self.seed.get().strip()
            rules = dict(
                first_click=FirstClick[self.first_click.get()],
                chord=self.chord.get(),
                flood_fill=FloodFill[self.flood.get()],
                seed=int(seed_text) if seed_text else None,
            )
            if self.count_mode.get() == "mines":
                config = GameConfig(rows, cols, int(self.mines.get()), **rules)
            else:
                config = GameConfig.from_density(rows, cols, float(self.density.get()), **rules)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self)
            return
        self.result = config
        self.destroy()


def _enable_windows_dpi_awareness() -> None:
    """Avoid a blurry, bitmap-scaled window on Windows high-DPI displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass  # older Windows: keep default scaling


def run(config: GameConfig) -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    App(root, config)
    root.mainloop()
