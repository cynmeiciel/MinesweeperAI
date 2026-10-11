# Ablation results

Sample override: 10; unique-state weighting; excluded snapshots: 0.
Smoke samples validate the pipeline, not population-level heuristic effects.
no_propagation disables automatic assignments but RETAINS feasibility pruning.
Times are ms: warm-up once, five measured repetitions by default; median per snapshot.
P95 uses linear interpolation at (n-1)*0.95. Ratios are ratios of TOTALS on identical feasible snapshots.
Infeasible states are counted separately, never treated as ordinary probabilities.
INFO game node totals cannot establish Degree/propagation effects.
McNemar exact: two-sided binomial on b+c at p0=0.5, unadjusted; no_info minus baseline in percentage points.
Wilson intervals describe each rate, not the paired difference; non-significance does not establish equivalence.
Stalled counts require diagnosis before strategic conclusions.

## replay

| variant | snapshots | infeasible_snapshots | excluded_snapshots | matched_snapshots | mean_nodes | median_nodes | p95_nodes | mean_pruned_nodes | mean_forced_assignments | median_dfs_time_ms | p95_dfs_time_ms | total_node_ratio | total_dfs_time_ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 1 | 0 | 0 | 1 | 3 | 3 | 3 | 0 | 2 | 0.007101 | 0.007101 | 1.0 | 1.0 |
| no_degree | 1 | 0 | 0 | 1 | 3 | 3 | 3 | 0 | 2 | 0.005237 | 0.005237 | 1.0 | 0.7375017603154486 |
| no_propagation | 1 | 0 | 0 | 1 | 7 | 7 | 7 | 2 | 0 | 0.012729 | 0.012729 | 2.3333333333333335 | 1.7925644275454162 |

## info

| config_id | preset | variant | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_moves | mean_guesses | mean_time_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 34bcd556ea7ef52c | beginner | baseline | 10 | 10 | 0 | 0 | 1.0 | 0.7224598312333834 | 1.0 | 25.9 | 0.1 | 2.1806 |
| 34bcd556ea7ef52c | beginner | no_info | 10 | 10 | 0 | 0 | 1.0 | 0.7224598312333834 | 1.0 | 25.9 | 0.1 | 2.1563 |

## info_pair

| config_id | preset | games | b | c | mcnemar_exact_p | win_difference_pp |
|---|---|---|---|---|---|---|
| 34bcd556ea7ef52c | beginner | 10 | 0 | 0 | 1.0 | 0.0 |

