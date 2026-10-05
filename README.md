# Minesweeper

Configurable Minesweeper with a tkinter GUI, a solver interface, and a headless
batch runner for statistics. Standard library only.

## Play

```bash
python -m minesweeper                       # beginner 9x9, 10 mines
python -m minesweeper --preset expert
python -m minesweeper --rows 12 --cols 20 --density 0.18 --first-click SAFE --seed 42
```

Left-click reveals, right-click flags (Ctrl+click on macOS), left-click on a
number (or middle-click) chords. *Game ▸ Custom…* exposes every option. The status bar shows the seed
so any board can be replayed with `--seed`.

AI panel: pick a solver and click **Hint**. The suggested cell is outlined and
the reason is shown; the move must still be made by the player.

## Options

| Option | Values | Default |
|---|---|---|
| `--preset` | tiny (5x5/3), beginner (9x9/10), intermediate (16x16/40), expert (16x30/99) | beginner |
| `--rows --cols` + `--mines` or `--density` | custom size | — |
| `--first-click` | `UNSAFE` (can lose), `SAFE` (cell safe), `OPENING` (cell + neighbours safe) | `OPENING` |
| `--no-chord` | disable chording | chord on |
| `--flood-fill` | `BFS`, `DFS` | `BFS` |
| `--seed` | integer | random |

## Batch analysis

```bash
python -m minesweeper.analysis --solver random --preset tiny --preset beginner \
    --games 1000 --seed 0 --out results.csv
python -m minesweeper.analysis --solver lv2 --preset beginner --games 100
python -m minesweeper.analysis --preset beginner --density 0.10:0.25:0.03 --games 500
```

Game *i* uses seed `--seed + i`, so runs are reproducible. Prints win rate
(95% Wilson CI), mean moves, guesses and time per configuration; `--out`
writes one CSV row per game.

## Platform notes

Works on Linux, Windows and macOS with Python 3.11+ and tkinter.

- **Windows:** the python.org installer includes tkinter. Use `py -m minesweeper`
  if `python` is not on PATH.
- **macOS:** the python.org installer includes tkinter. With Homebrew Python,
  install it via `brew install python-tk`.
- **Linux:** install your distro's tk package if `import tkinter` fails
  (e.g. `sudo apt install python3-tk`, `sudo pacman -S tk`).

## Development

```bash
uv run pytest          # or: python -m pip install pytest && python -m pytest
```
