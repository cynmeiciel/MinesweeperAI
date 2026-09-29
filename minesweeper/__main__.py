"""python -m minesweeper — play in the GUI."""
from __future__ import annotations

import argparse

from minesweeper.cli import add_game_args, configs_from_args


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m minesweeper", description="Play Minesweeper.")
    add_game_args(parser, multi=False)
    args = parser.parse_args(argv)
    try:
        configs = configs_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))
    if len(configs) != 1:
        parser.error("the GUI takes a single --density value, not a range")

    from minesweeper.gui.app import run  # import tkinter only when actually launching

    run(configs[0])


if __name__ == "__main__":
    main()
