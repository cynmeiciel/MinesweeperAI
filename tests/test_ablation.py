"""Independent enumeration, stats definitions, and baseline compatibility."""
import csv
import random
from dataclasses import asdict
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest

from minesweeper.analysis.batch import run_game
from minesweeper.core.config import GameConfig
from minesweeper.core.game import PlayerView, Status
from minesweeper.solver.constraint_solver import Constraint
from minesweeper.solver.dfs_solver import Component, DFSStats, DfsSolver


def assignments(component):
    # Independent oracle: enumerate every vector and test sums directly.
    return {values for values in product((0, 1), repeat=len(component.cells))
            if all(sum(dict(zip(component.cells, values))[c] for c in constraint.cells) == constraint.mines
                   for constraint in component.constraints)}


@pytest.mark.parametrize("order,propagation", [("degree", True), ("coordinate", True), ("degree", False)])
def test_small_components_match_independent_exhaustive_oracle(order, propagation):
    rng = random.Random(831)
    for size in range(1, 7):
        cells = tuple((0, i) for i in range(size))
        for _ in range(15):
            constraints = tuple(Constraint(frozenset(rng.sample(cells, rng.randint(1, size))),
                                           rng.randint(0, size)) for _ in range(4))
            component = Component(cells, constraints)
            stats = DFSStats()
            solutions = DfsSolver._solve_component(component, variable_order=order,
                                                   use_propagation=propagation, stats=stats)
            assert {tuple(s[c] for c in cells) for s in solutions} == assignments(component)
            assert stats.solutions_count == len(solutions)
            assert stats.nodes_visited == 2 * stats.branch_points + 1
            assert stats.nodes_visited == stats.branch_points + stats.pruned_nodes + stats.solutions_count
            assert stats.dfs_time_ms >= 0
            if not propagation:
                assert stats.forced_assignments == stats.propagation_passes == 0


def test_exact_stats_for_root_propagation_and_feasibility_only():
    cells = ((0, 0), (0, 1))
    component = Component(cells, (Constraint(frozenset(cells), 0),))
    stats = DFSStats()
    DfsSolver._solve_component(component, stats=stats)
    assert (stats.nodes_visited, stats.branch_points, stats.pruned_nodes, stats.forced_assignments,
            stats.constraint_checks, stats.propagation_passes, stats.max_depth, stats.solutions_count) == (1, 0, 0, 2, 2, 2, 0, 1)
    stats = DFSStats()
    DfsSolver._solve_component(component, use_propagation=False, stats=stats)
    assert (stats.nodes_visited, stats.branch_points, stats.pruned_nodes, stats.forced_assignments,
            stats.constraint_checks, stats.propagation_passes, stats.max_depth, stats.solutions_count) == (5, 2, 2, 0, 5, 0, 2, 1)


def test_unsatisfiable_component_counts_each_pruned_node_once():
    cell = (0, 0)
    component = Component((cell,), (Constraint(frozenset({cell}), 0), Constraint(frozenset({cell}), 1)))
    stats = DFSStats()
    assert DfsSolver._solve_component(component, stats=stats) == []
    assert (stats.nodes_visited, stats.pruned_nodes, stats.forced_assignments,
            stats.constraint_checks, stats.propagation_passes) == (1, 1, 1, 2, 1)
    stats = DFSStats()
    assert DfsSolver._solve_component(component, use_propagation=False, stats=stats) == []
    assert (stats.nodes_visited, stats.branch_points, stats.pruned_nodes,
            stats.constraint_checks, stats.max_depth) == (3, 1, 2, 5, 1)


def test_global_fraction_probabilities_against_independent_board_enumeration():
    a, b, c, d, e, x, y = [(0, i) for i in range(7)]
    components = [Component((a, b, c), (Constraint(frozenset({a, b}), 1), Constraint(frozenset({b, c}), 1))),
                  Component((d, e), (Constraint(frozenset({d, e}), 1),))]
    all_cells = (a, b, c, d, e, x, y)
    layouts = [dict(zip(all_cells, values)) for values in product((0, 1), repeat=7)
               if sum(values) == 3 and values[0] + values[1] == 1 and values[1] + values[2] == 1 and values[3] + values[4] == 1]
    oracle = {cell: Fraction(sum(s[cell] for s in layouts), len(layouts)) for cell in all_cells}
    for order, propagate in [("degree", True), ("coordinate", True), ("degree", False)]:
        solutions = [DfsSolver._solve_component(comp, variable_order=order, use_propagation=propagate) for comp in components]
        probabilities, info = DfsSolver._global_probabilities(components, solutions, {x, y}, 3, include_outside=True)
        assert probabilities == oracle
        assert info[x] == info[y] == 0


def test_info_only_affects_equal_risk_guesses_and_preserves_certainties():
    probabilities = {(0, 0): Fraction(1, 2), (0, 1): Fraction(1, 2)}
    info = {(0, 0): 1, (0, 1): 5}
    assert DfsSolver._choose_move(probabilities, info).cell == (0, 1)
    assert DfsSolver._choose_move(probabilities, info, guess_tiebreak="coordinate").cell == (0, 0)
    probabilities[(0, 0)] = Fraction(1)
    probabilities[(0, 1)] = Fraction(0)
    assert DfsSolver._choose_move(probabilities, info) == DfsSolver._choose_move(probabilities, info, guess_tiebreak="coordinate")


def test_stats_reset_on_next_lv1_move():
    solver = DfsSolver(random.Random(0), collect_stats=True)
    view = PlayerView(1, 3, 1, ((None, 1, None),), frozenset(), Status.PLAYING)
    solver.next_move(view)
    assert solver.last_stats.nodes_visited > 0
    assert len(solver.component_stats) == 1
    opening = PlayerView(9, 9, 10, tuple((None,) * 9 for _ in range(9)), frozenset(), Status.READY)
    solver.next_move(opening)
    assert solver.last_stats == DFSStats()
    assert solver.component_stats == []


@pytest.mark.parametrize("options", [{}, {"collect_stats": True}, {"variable_order": "coordinate", "collect_stats": True},
                                    {"use_propagation": False, "collect_stats": True}])
def test_default_and_search_variants_preserve_pre_ablation_game_records(options):
    path = Path(__file__).resolve().parents[1] / "docs/report/data/full_20261011/lv3_9x9-10_opening_center_bfs_outside0.csv"
    previous = list(csv.DictReader(path.open()))[:10]
    for row in previous:
        record = run_game(GameConfig(9, 9, 10, seed=int(row["seed"])), DfsSolver,
                          solver_factory=lambda rng: DfsSolver(rng, **options))
        for key, value in asdict(record).items():
            if key != "time_ms":
                assert str(value) == row[key]


@pytest.mark.parametrize("options", [{"variable_order": "mrv"}, {"guess_tiebreak": "random"}])
def test_invalid_ablation_options_rejected(options):
    with pytest.raises(ValueError):
        DfsSolver(random.Random(0), **options)


def test_stats_aggregation_sums_counts_and_maximizes_depth():
    aggregate = DFSStats(nodes_visited=3, max_depth=4, largest_component_variables=6, dfs_time_ms=1)
    aggregate.add(DFSStats(nodes_visited=5, max_depth=2, largest_component_variables=9, dfs_time_ms=2))
    assert aggregate.nodes_visited == 8 and aggregate.max_depth == 4
    assert aggregate.largest_component_variables == 9 and aggregate.dfs_time_ms == 3
