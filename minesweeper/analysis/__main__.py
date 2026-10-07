"""python -m minesweeper.analysis — run headless games and report statistics."""
from __future__ import annotations

import argparse
import sys

from minesweeper.analysis.batch import (
    format_summary,
    run_batch,
    summarize,
    write_csv,
    write_game_log,
)
from minesweeper.cli import add_game_args, configs_from_args
from minesweeper.solver import SOLVERS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m minesweeper.analysis",
        description="Run many headless games with a solver and summarise the results.",
    )
    add_game_args(parser, multi=True)
    parser.add_argument("--solver", choices=list(SOLVERS), default="random")
    parser.add_argument("--games", type=int, default=100, help="games per configuration")
    parser.add_argument("--out", help="write per-game rows to this CSV file")
    parser.add_argument(
        "--log", default="analysis.log", help="write per-game details (default: analysis.log)"
    )
    args = parser.parse_args(argv)
    if args.games < 1:
        parser.error("--games must be at least 1")
    try:
        configs = configs_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    out = None
    if args.out:
        try:  # open before running so a bad path fails fast, not after every game
            out = open(args.out, "w", newline="", encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot write {args.out}: {exc.strerror}")
    try:
        failure_log = open(args.log, "w", encoding="utf-8")
    except OSError as exc:
        parser.error(f"cannot write {args.log}: {exc.strerror}")

    base_seed = args.seed if args.seed is not None else 0
    records = run_batch(configs, args.solver, args.games, base_seed)
    if out is not None:
        with out:
            write_csv(records, out)
    with failure_log:
        write_game_log(records, failure_log)
    print(format_summary(summarize(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
