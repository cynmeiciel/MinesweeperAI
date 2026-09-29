"""tkinter front-end. Thin: all rules live in core, all drawing decisions in render."""
from __future__ import annotations

import random
import sys
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox

from minesweeper.core.board import Cell
from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig
from minesweeper.core.game import CellState, Game, Status
from minesweeper.gui.render import FACES, cell_appearance, cell_size_for, pixel_to_cell
from minesweeper.solver import SOLVERS, Solver, apply_move

AI_HIGHLIGHT = "#ff8c00"
GRID_LINE = "#808080"


class App:
    def __init__(self, root: tk.Tk, config: GameConfig) -> None:
        self.root = root
        self.config = config
        self.game: Game
        self.solver: Solver | None = None
        self._ai_cell: Cell | None = None
        self._auto_job: str | None = None
        self._timer_job: str | None = None
        self._rects: dict[Cell, int] = {}
        self._texts: dict[Cell, int] = {}

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
            panel, self.solver_var, *SOLVERS, command=lambda _v: self._reset_solver()
        ).pack(side="left")
        tk.Button(panel, text="Step", command=self.ai_step).pack(side="left", padx=2)
        self.auto_btn = tk.Button(panel, text="Auto", width=6, command=self.toggle_auto)
        self.auto_btn.pack(side="left", padx=2)
        self.speed = tk.Scale(
            panel, from_=50, to=1000, resolution=50, orient="horizontal",
            label="ms / move", length=140,
        )
        self.speed.set(300)
        self.speed.pack(side="left", padx=6)
        self.reason_var = tk.StringVar()
        tk.Label(
            self.root, textvariable=self.reason_var, anchor="w", justify="left", wraplength=500
        ).pack(fill="x", padx=8)

    def _bind_mouse(self) -> None:
        # On macOS (aqua) right-click is Button-2 and middle-click is Button-3.
        aqua = self.root.tk.call("tk", "windowingsystem") == "aqua"
        flag_btn, chord_btn = ("<Button-2>", "<Button-3>") if aqua else ("<Button-3>", "<Button-2>")
        self.canvas.bind("<Button-1>", self._on_left)
        self.canvas.bind(flag_btn, self._on_flag)
        self.canvas.bind(chord_btn, self._on_chord)
        if aqua:  # many Mac users have no right button
            self.canvas.bind("<Control-Button-1>", self._on_flag)

    # --- game lifecycle ----------------------------------------------------------

    def new_game(self, config: GameConfig | None = None) -> None:
        if config is not None:
            self.config = config
        self._stop_auto()
        if self._timer_job is not None:
            self.root.after_cancel(self._timer_job)
            self._timer_job = None
        self.game = Game(self.config)
        self._reset_solver()
        self._ai_cell = None

        rows, cols = self.config.rows, self.config.cols
        self.cell_size = s = cell_size_for(
            rows, cols,
            int(self.root.winfo_screenwidth() * 0.85),
            int(self.root.winfo_screenheight() * 0.85) - 200,
        )
        self.canvas.delete("all")
        self.canvas.config(width=cols * s, height=rows * s)
        font = ("TkDefaultFont", max(8, s // 2), "bold")
        self._rects.clear()
        self._texts.clear()
        for r in range(rows):
            for c in range(cols):
                x, y = c * s, r * s
                self._rects[(r, c)] = self.canvas.create_rectangle(x, y, x + s, y + s)
                self._texts[(r, c)] = self.canvas.create_text(x + s / 2, y + s / 2, font=font)
        self._redraw_all()
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

    def _draw_cell(self, cell: Cell) -> None:
        a = cell_appearance(self.game, *cell)
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
        for cell in self._rects:
            self._draw_cell(cell)

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
            self._stop_auto()
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
        self._after_move(result.revealed)

    def _on_flag(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None and self.game.toggle_flag(*cell):
            self._after_move([cell])

    def _on_chord(self, event: tk.Event) -> None:
        cell = self._cell_at(event)
        if cell is not None:
            self._after_move(self.game.chord(*cell).revealed)

    # --- AI ------------------------------------------------------------------------

    def _reset_solver(self) -> None:
        self.solver = None  # created lazily with the game's seed on the next step

    def ai_step(self) -> bool:
        """Ask the solver for one move and apply it. Returns True if a move was made."""
        if self.game.is_over:
            return False
        if self.solver is None:
            self.solver = SOLVERS[self.solver_var.get()](random.Random(self.game.seed))
        try:
            move = self.solver.next_move(self.game.view())
        except Exception as exc:  # show solver bugs instead of crashing the GUI
            self.reason_var.set(f"solver error: {exc}")
            self._stop_auto()
            return False
        if not apply_move(self.game, move):
            self.reason_var.set(f"illegal move: {move.action} {move.cell}")
            self._stop_auto()
            return False
        self._ai_cell = move.cell
        prefix = "" if move.certain else "guess: "
        self.reason_var.set(f"{move.action} {move.cell} — {prefix}{move.reason}")
        self._redraw_all()  # a move can reveal many cells; full redraw keeps it simple
        self._after_move([])
        return True

    def toggle_auto(self) -> None:
        if self._auto_job is not None:
            self._stop_auto()
        else:
            self.auto_btn.config(text="Pause")
            self._auto_tick()

    def _auto_tick(self) -> None:
        self._auto_job = None
        if self.ai_step() and not self.game.is_over:
            self._auto_job = self.root.after(self.speed.get(), self._auto_tick)
        else:
            self._stop_auto()

    def _stop_auto(self) -> None:
        if self._auto_job is not None:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if hasattr(self, "auto_btn"):
            self.auto_btn.config(text="Auto")


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
