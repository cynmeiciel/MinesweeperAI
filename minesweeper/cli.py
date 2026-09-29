"""Command-line options shared by the GUI and the batch runner."""
from __future__ import annotations

import argparse

from minesweeper.core.config import PRESETS, FirstClick, FloodFill, GameConfig

_DEFAULT_SIZE = PRESETS["beginner"]


def parse_density(text: str) -> list[float]:
    """'0.15' → [0.15]; 'start:stop:step' → inclusive range."""
    try:
        parts = [float(p) for p in text.split(":")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid density {text!r}") from None
    if len(parts) == 1:
        return parts
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("density range must be start:stop:step")
    start, stop, step = parts
    if step <= 0 or stop < start:
        raise argparse.ArgumentTypeError("density range needs step > 0 and stop >= start")
    values = []
    i = 0
    while (value := round(start + i * step, 10)) <= stop + 1e-9:
        values.append(value)
        i += 1
    return values


def add_game_args(parser: argparse.ArgumentParser, *, multi: bool) -> None:
    board = parser.add_argument_group("board")
    board.add_argument(
        "--preset",
        choices=list(PRESETS),
        action="append" if multi else "store",
        help="board preset" + (" (repeatable)" if multi else ""),
    )
    board.add_argument("--rows", type=int)
    board.add_argument("--cols", type=int)
    board.add_argument("--mines", type=int)
    board.add_argument(
        "--density", type=parse_density, help="mine density, e.g. 0.15 or 0.10:0.25:0.03"
    )
    rules = parser.add_argument_group("rules")
    rules.add_argument(
        "--first-click", choices=[f.name for f in FirstClick], default=FirstClick.OPENING.name
    )
    rules.add_argument("--no-chord", action="store_true", help="disable chording")
    rules.add_argument(
        "--flood-fill", choices=[f.name for f in FloodFill], default=FloodFill.BFS.name
    )
    rules.add_argument("--seed", type=int)


def configs_from_args(args: argparse.Namespace) -> list[GameConfig]:
    rules = dict(
        first_click=FirstClick[args.first_click],
        chord=not args.no_chord,
        flood_fill=FloodFill[args.flood_fill],
        seed=args.seed,
    )
    presets = args.preset if isinstance(args.preset, list) else [args.preset] if args.preset else []
    if args.mines is not None and args.density is not None:
        raise ValueError("use either --mines or --density, not both")

    if presets:
        if args.rows is not None or args.cols is not None:
            raise ValueError("use either --preset or --rows/--cols, not both")
        sizes = [(PRESETS[p].rows, PRESETS[p].cols, PRESETS[p].mines) for p in presets]
    elif args.rows is not None and args.cols is not None:
        if args.mines is None and args.density is None:
            raise ValueError("--rows/--cols need --mines or --density")
        sizes = [(args.rows, args.cols, args.mines)]
    elif args.rows is None and args.cols is None:
        sizes = [(_DEFAULT_SIZE.rows, _DEFAULT_SIZE.cols, _DEFAULT_SIZE.mines)]
    else:
        raise ValueError("--rows and --cols must be given together")

    configs = []
    for rows, cols, mines in sizes:
        if args.density is not None:
            configs += [GameConfig.from_density(rows, cols, d, **rules) for d in args.density]
        else:
            configs.append(
                GameConfig(rows, cols, args.mines if args.mines is not None else mines, **rules)
            )
    return list(dict.fromkeys(configs))  # drop duplicates, keep order
