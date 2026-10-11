"""LV3 solver using component-wise DFS and mine probabilities."""
from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from fractions import Fraction
from math import comb
from time import perf_counter_ns
from typing import Literal

from minesweeper.core.board import Cell
from minesweeper.core.game import PlayerView
from minesweeper.solver.base import Move, SolverStuck
from minesweeper.solver.constraint_solver import Constraint, ConstraintSolver


@dataclass(frozen=True)
class Component:
    cells: tuple[Cell, ...]
    constraints: tuple[Constraint, ...]


@dataclass
class DFSStats:
    """Counters for a component, move or game; times are disjoint intervals."""

    nodes_visited: int = 0
    branch_points: int = 0
    pruned_nodes: int = 0
    forced_assignments: int = 0
    constraint_checks: int = 0
    propagation_passes: int = 0
    max_depth: int = 0
    solutions_count: int = 0
    dfs_time_ms: float = 0.0
    probability_time_ms: float = 0.0
    components_count: int = 0
    largest_component_variables: int = 0

    def add(self, other: DFSStats) -> None:
        for item in fields(self):
            a, b = getattr(self, item.name), getattr(other, item.name)
            setattr(self, item.name, max(a, b) if item.name in ("max_depth", "largest_component_variables") else a + b)


class DfsSolver:
    """Run LV1/LV2, then use DFS probabilities for unresolved frontiers."""

    name = "lv3"

    def __init__(
        self,
        rng: random.Random,
        *,
        opening_strategy: str = "center",
        include_outside: bool = False,
        variable_order: str = "degree",
        use_propagation: bool = True,
        guess_tiebreak: str = "info",
        collect_stats: bool = False,
        frontier_observer: Callable[[PlayerView, tuple[Constraint, ...]], None] | None = None,
    ) -> None:
        if variable_order not in ("degree", "coordinate"):
            raise ValueError("variable_order must be degree or coordinate")
        if guess_tiebreak not in ("info", "coordinate"):
            raise ValueError("guess_tiebreak must be info or coordinate")
        self.last_level = 3
        self._lv2 = ConstraintSolver(rng, opening_strategy=opening_strategy)
        self._include_outside = include_outside
        self.variable_order = variable_order
        self.use_propagation = use_propagation
        self.guess_tiebreak = guess_tiebreak
        self.collect_stats = collect_stats
        self.frontier_observer = frontier_observer
        self.last_stats = DFSStats()
        self.component_stats: list[DFSStats] = []

    def next_move(self, view: PlayerView) -> Move:
        self.last_stats = DFSStats()
        self.component_stats = []
        try:
            move = self._lv2.next_move(view)
            self.last_level = self._lv2.last_level
            return move
        except SolverStuck:
            pass

        constraints = ConstraintSolver._build_constraints(view)
        if self.frontier_observer is not None:
            self.frontier_observer(view, tuple(constraints))
        components = self._components(constraints)
        component_solutions: list[list[dict[Cell, int]]] = []
        for component in components:
            stats = DFSStats() if self.collect_stats else None
            solutions = self._solve_component(component, variable_order=self.variable_order, use_propagation=self.use_propagation, stats=stats)
            if stats is not None:
                stats.components_count = 1
                stats.largest_component_variables = len(component.cells)
                self.component_stats.append(stats)
                self.last_stats.add(stats)
            if not solutions:
                raise SolverStuck("AI -> STUCK")
            component_solutions.append(solutions)

        self.last_level = 3
        mines_left = view.total_mines - len(view.flags)
        frontier = {cell for component in components for cell in component.cells}
        outside_frontier = set(view.hidden_cells()).difference(frontier)
        probability_start = perf_counter_ns() if self.collect_stats else 0
        probabilities, information = self._global_probabilities(
            components,
            component_solutions,
            outside_frontier,
            mines_left,
            include_outside=self._include_outside,
        )
        if self.collect_stats:
            self.last_stats.probability_time_ms = (perf_counter_ns() - probability_start) / 1_000_000
        if not probabilities:
            hidden = view.hidden_cells()
            if not hidden:
                raise SolverStuck("AI -> STUCK")
            probability = Fraction(view.total_mines - len(view.flags), len(hidden))
            cell = min(
                hidden,
                key=lambda candidate: (
                    abs(2 * candidate[0] - (view.rows - 1))
                    + abs(2 * candidate[1] - (view.cols - 1)),
                    candidate,
                ),
            )
            return self._move(
                action="reveal",
                cell=cell,
                probability=probability,
                information=0,
                mines_left=mines_left,
                certain=probability == 0,
            )
        return self._choose_move(probabilities, information, mines_left=mines_left, guess_tiebreak=self.guess_tiebreak)

    @classmethod
    def _global_probabilities(
        cls,
        components: list[Component],
        component_solutions: list[list[dict[Cell, int]]],
        outside_frontier: set[Cell],
        mines_left: int,
        *,
        include_outside: bool,
    ) -> tuple[dict[Cell, Fraction], dict[Cell, int]]:
        """Combine component solutions while enforcing the global mine budget."""
        distributions = [cls._mine_distribution(solutions) for solutions in component_solutions]
        prefix: list[dict[int, int]] = [{0: 1}]
        for distribution in distributions:
            prefix.append(cls._convolve(prefix[-1], distribution))
        suffix: list[dict[int, int]] = [{} for _ in range(len(distributions) + 1)]
        suffix[-1] = {0: 1}
        for index in range(len(distributions) - 1, -1, -1):
            suffix[index] = cls._convolve(distributions[index], suffix[index + 1])

        outside_count = len(outside_frontier)
        outside_distribution = {
            count: comb(outside_count, count) for count in range(outside_count + 1)
        }
        all_distribution = cls._convolve(prefix[-1], outside_distribution)
        total = all_distribution.get(mines_left, 0)
        if total == 0:
            return {}, {}

        probabilities: dict[Cell, Fraction] = {}
        information: dict[Cell, int] = {}
        for index, (component, solutions) in enumerate(zip(components, component_solutions)):
            context = cls._convolve(prefix[index], suffix[index + 1])
            context = cls._convolve(context, outside_distribution)
            for cell in component.cells:
                mine_weight = sum(
                    context.get(mines_left - sum(solution.values()), 0)
                    for solution in solutions
                    if solution[cell]
                )
                probabilities[cell] = Fraction(mine_weight, total)
                information[cell] = sum(cell in constraint.cells for constraint in component.constraints)

        if include_outside and outside_count:
            outside_mine_weight = sum(
                count * comb(outside_count, count) * prefix[-1].get(mines_left - count, 0)
                for count in range(outside_count + 1)
            )
            outside_probability = Fraction(outside_mine_weight, total * outside_count)
            for cell in outside_frontier:
                probabilities[cell] = outside_probability
                information[cell] = 0
        return probabilities, information

    @staticmethod
    def _mine_distribution(solutions: list[dict[Cell, int]]) -> dict[int, int]:
        distribution: dict[int, int] = {}
        for solution in solutions:
            count = sum(solution.values())
            distribution[count] = distribution.get(count, 0) + 1
        return distribution

    @staticmethod
    def _convolve(left: dict[int, int], right: dict[int, int]) -> dict[int, int]:
        result: dict[int, int] = {}
        for left_count, left_ways in left.items():
            for right_count, right_ways in right.items():
                count = left_count + right_count
                result[count] = result.get(count, 0) + left_ways * right_ways
        return result

    @classmethod
    def _choose_move(
        cls,
        probabilities: dict[Cell, Fraction],
        information: dict[Cell, int],
        *,
        mines_left: int = 0,
        guess_tiebreak: str = "info",
    ) -> Move:
        """Search every frontier for certainty before allowing a probability guess."""
        if not probabilities:
            raise SolverStuck("AI -> STUCK")

        certain = [cell for cell, probability in probabilities.items() if probability in (0, 1)]
        if certain:
            cell = min(certain)
            probability = probabilities[cell]
            action: Literal["reveal", "flag"] = "flag" if probability == 1 else "reveal"
            return cls._move(
                action, cell, probability, information[cell], mines_left=mines_left, certain=True
            )

        candidates = [
            (probability, -information[cell] if guess_tiebreak == "info" else 0, cell, probability)
            for cell, probability in probabilities.items()
        ]
        _, _, cell, probability = min(candidates)
        return cls._move(
            action="reveal",
            cell=cell,
            probability=probability,
            information=information[cell],
            mines_left=mines_left,
            certain=False,
        )

    @staticmethod
    def _components(constraints: Iterable[Constraint]) -> list[Component]:
        pending = list(constraints)
        components: list[Component] = []
        while pending:
            group = [pending.pop(0)]
            cells = set(group[0].cells)
            changed = True
            while changed:
                changed = False
                for constraint in pending[:]:
                    if cells.isdisjoint(constraint.cells):
                        continue
                    pending.remove(constraint)
                    group.append(constraint)
                    cells.update(constraint.cells)
                    changed = True
            components.append(
                Component(
                    cells=tuple(sorted(cells)),
                    constraints=tuple(sorted(group, key=lambda item: (min(item.cells), item.mines))),
                )
            )
        return sorted(components, key=lambda component: component.cells[0])

    @classmethod
    def _solve_component(
        cls, component: Component, *, variable_order: str = "degree",
        use_propagation: bool = True, stats: DFSStats | None = None,
    ) -> list[dict[Cell, int]]:
        if variable_order not in ("degree", "coordinate"):
            raise ValueError("invalid variable_order")
        solutions: list[dict[Cell, int]] = []
        start = perf_counter_ns() if stats is not None else 0

        def search(assignment: dict[Cell, int], depth: int = 0) -> None:
            if stats is not None:
                stats.nodes_visited += 1
                stats.max_depth = max(stats.max_depth, depth)
            assignment = dict(assignment)
            feasible = cls._propagate(assignment, component.constraints, stats=stats) if use_propagation else cls._feasible(assignment, component.constraints, stats=stats)
            if not feasible:
                if stats is not None:
                    stats.pruned_nodes += 1
                return
            if len(assignment) == len(component.cells):
                solutions.append(assignment)
                if stats is not None:
                    stats.solutions_count += 1
                return

            unassigned = [cell for cell in component.cells if cell not in assignment]
            if stats is not None:
                stats.branch_points += 1
            if variable_order == "coordinate":
                cell = min(unassigned)
            else:
                scores = {
                    cell: sum(
                        cell in constraint.cells
                        and any(candidate not in assignment for candidate in constraint.cells)
                        for constraint in component.constraints
                    )
                    for cell in unassigned
                }
                cell = min(unassigned, key=lambda candidate: (-scores[candidate], candidate))
            for value in (0, 1):
                branch = dict(assignment)
                branch[cell] = value
                search(branch, depth + 1)

        try:
            search({})
        finally:
            if stats is not None:
                stats.dfs_time_ms += (perf_counter_ns() - start) / 1_000_000
        return solutions

    @staticmethod
    def _feasible(assignment: dict[Cell, int], constraints: tuple[Constraint, ...], *, stats: DFSStats | None = None) -> bool:
        """Prune contradictions without assigning variables, including at leaves."""
        for constraint in constraints:
            if stats is not None:
                stats.constraint_checks += 1
            remaining = constraint.mines - sum(assignment[c] for c in constraint.cells if c in assignment)
            unknown = sum(c not in assignment for c in constraint.cells)
            if remaining < 0 or remaining > unknown:
                return False
        return True

    @staticmethod
    def _propagate(assignment: dict[Cell, int], constraints: tuple[Constraint, ...], *, stats: DFSStats | None = None) -> bool:
        changed = True
        while changed:
            if stats is not None:
                stats.propagation_passes += 1
            changed = False
            for constraint in constraints:
                if stats is not None:
                    stats.constraint_checks += 1
                assigned_mines = sum(assignment[cell] for cell in constraint.cells if cell in assignment)
                unassigned = [cell for cell in constraint.cells if cell not in assignment]
                remaining = constraint.mines - assigned_mines
                if remaining < 0 or remaining > len(unassigned):
                    return False
                if not unassigned:
                    continue
                if remaining not in (0, len(unassigned)):
                    continue
                value = 1 if remaining == len(unassigned) else 0
                for cell in unassigned:
                    assignment[cell] = value
                    if stats is not None:
                        stats.forced_assignments += 1
                    changed = True
        return True

    @staticmethod
    def _move(
        action: Literal["reveal", "flag"],
        cell: Cell,
        probability: Fraction,
        information: int,
        *,
        mines_left: int,
        certain: bool,
    ) -> Move:
        reason = (
            f"[LV3 DFS] MINES_LEFT={mines_left} P(MINE)={probability} INFO={information} "
            f"-> {action.upper()} {cell}"
        )
        return Move(action, cell, reason, certain=certain)
