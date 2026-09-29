"""Solvers. Each sees only a PlayerView, never the mine layout."""
from minesweeper.solver.base import Move, Solver, apply_move, solver_rng
from minesweeper.solver.random_solver import RandomSolver

SOLVERS: dict[str, type[Solver]] = {
    RandomSolver.name: RandomSolver,
}

__all__ = ["SOLVERS", "Move", "Solver", "apply_move", "solver_rng", "RandomSolver"]
