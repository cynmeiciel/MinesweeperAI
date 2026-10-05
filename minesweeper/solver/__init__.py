"""Solvers. Each sees only a PlayerView, never the mine layout."""
from minesweeper.solver.base import Move, Solver, SolverStuck, apply_move, solver_rng
from minesweeper.solver.constraint_solver import ConstraintSolver
from minesweeper.solver.random_solver import RandomSolver
from minesweeper.solver.rule_based_solver import RuleBasedSolver

SOLVERS: dict[str, type[Solver]] = {
    RandomSolver.name: RandomSolver,
    RuleBasedSolver.name: RuleBasedSolver,
    ConstraintSolver.name: ConstraintSolver,
}

__all__ = [
    "SOLVERS", "Move", "Solver", "SolverStuck", "apply_move", "solver_rng",
    "RandomSolver", "RuleBasedSolver", "ConstraintSolver",
]
