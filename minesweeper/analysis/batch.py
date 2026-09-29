"""Run many headless games and aggregate the results."""
from __future__ import annotations

import csv
import logging
import math
import random
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, fields, replace
from typing import TextIO

from minesweeper.core.config import GameConfig
from minesweeper.core.game import Game, Status
from minesweeper.solver import SOLVERS, Solver, apply_move

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameRecord:
    seed: int
    rows: int
    cols: int
    mines: int
    density: float
    first_click: str
    chord: bool
    flood_fill: str
    solver: str
    result: str  # won / lost / stalled
    moves: int
    guesses: int
    cells_revealed: int
    time_ms: float


CSV_FIELDS = [f.name for f in fields(GameRecord)]


def run_game(config: GameConfig, solver_cls: type[Solver]) -> GameRecord:
    if config.seed is None:
        raise ValueError("run_game needs config.seed for reproducibility")
    game = Game(config)
    solver = solver_cls(random.Random(config.seed))
    limit = config.rows * config.cols * 2
    moves = guesses = 0
    result = None
    start = time.perf_counter()
    while not game.is_over:
        if moves >= limit:
            log.warning("seed %s: %s exceeded %d moves", config.seed, solver_cls.name, limit)
            result = "stalled"
            break
        try:
            move = solver.next_move(game.view())
        except Exception:
            log.warning("seed %s: %s raised", config.seed, solver_cls.name, exc_info=True)
            result = "stalled"
            break
        if not apply_move(game, move):
            log.warning("seed %s: illegal move %s", config.seed, move)
            result = "stalled"
            break
        moves += 1
        guesses += not move.certain
    elapsed_ms = (time.perf_counter() - start) * 1000
    if result is None:
        result = "won" if game.status is Status.WON else "lost"
    return GameRecord(
        seed=config.seed,
        rows=config.rows,
        cols=config.cols,
        mines=config.mines,
        density=round(config.density, 4),
        first_click=config.first_click.name,
        chord=config.chord,
        flood_fill=config.flood_fill.name,
        solver=solver_cls.name,
        result=result,
        moves=moves,
        guesses=guesses,
        cells_revealed=game.revealed_count,
        time_ms=round(elapsed_ms, 3),
    )


def run_batch(
    configs: Iterable[GameConfig], solver_name: str, games: int, base_seed: int
) -> list[GameRecord]:
    solver_cls = SOLVERS[solver_name]
    return [
        run_game(replace(config, seed=base_seed + i), solver_cls)
        for config in configs
        for i in range(games)
    ]


def write_csv(records: Iterable[GameRecord], file: TextIO) -> None:
    writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for record in records:
        writer.writerow(asdict(record))


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval for a win rate (Wilson score interval)."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass(frozen=True)
class Summary:
    label: str
    games: int
    wins: int
    stalled: int
    win_rate: float
    ci_low: float
    ci_high: float
    mean_moves: float
    mean_guesses: float
    mean_time_ms: float


def summarize(records: Sequence[GameRecord]) -> list[Summary]:
    groups: dict[tuple, list[GameRecord]] = {}
    for r in records:
        key = (r.rows, r.cols, r.mines, r.first_click, r.chord, r.flood_fill, r.solver)
        groups.setdefault(key, []).append(r)
    summaries = []
    for (rows, cols, mines, first, chord, flood, solver), recs in groups.items():
        n = len(recs)
        wins = sum(r.result == "won" for r in recs)
        low, high = wilson_interval(wins, n)
        summaries.append(
            Summary(
                label=(
                    f"{rows}x{cols} {mines} mines ({mines / (rows * cols):.1%}) "
                    f"{first} chord={'on' if chord else 'off'} {flood} [{solver}]"
                ),
                games=n,
                wins=wins,
                stalled=sum(r.result == "stalled" for r in recs),
                win_rate=wins / n,
                ci_low=low,
                ci_high=high,
                mean_moves=sum(r.moves for r in recs) / n,
                mean_guesses=sum(r.guesses for r in recs) / n,
                mean_time_ms=sum(r.time_ms for r in recs) / n,
            )
        )
    return summaries


def format_summary(summaries: Iterable[Summary]) -> str:
    lines = []
    for s in summaries:
        lines.append(s.label)
        lines.append(
            f"  games={s.games} win rate={s.win_rate:.1%} "
            f"(95% CI {s.ci_low:.1%}-{s.ci_high:.1%}) stalled={s.stalled}"
        )
        lines.append(
            f"  mean moves={s.mean_moves:.1f} guesses={s.mean_guesses:.1f} "
            f"time={s.mean_time_ms:.2f} ms"
        )
    return "\n".join(lines)
