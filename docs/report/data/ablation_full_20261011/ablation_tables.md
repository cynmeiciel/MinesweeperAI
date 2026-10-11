# Ablation results

Sample override: None; unique-state weighting; excluded snapshots: 0.
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
| baseline | 2524 | 0 | 0 | 2524 | 589.006735340729 | 25.0 | 1180.3999999999996 | 1.6291600633914423 | 680.3019017432647 | 0.32729650000000005 | 25.733025199999947 | 1.0 | 1.0 |
| no_degree | 2524 | 0 | 0 | 2524 | 654.4314580031696 | 31.0 | 1454.6999999999998 | 34.341521394611725 | 1305.5994453248811 | 0.263748 | 26.115222049999975 | 1.111076357428398 | 1.013761492818356 |
| no_propagation | 2524 | 0 | 0 | 2524 | 3656.9726624405707 | 235.0 | 7217.049999999999 | 1535.6121236133122 | 0 | 1.827087 | 109.32005284999984 | 6.208711111469859 | 5.392678909055576 |

## info

| config_id | preset | variant | games | wins | losses | stalled | win_rate | ci_low | ci_high | mean_moves | mean_guesses | mean_time_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 34bcd556ea7ef52c | beginner | baseline | 1000 | 961 | 39 | 0 | 0.961 | 0.9471303986994359 | 0.971341200803912 | 26.74 | 0.107 | 2.619114 |
| 34bcd556ea7ef52c | beginner | no_info | 1000 | 969 | 31 | 0 | 0.969 | 0.956334233864468 | 0.9780761352614977 | 26.758 | 0.108 | 2.611844 |
| c09edb17b74c9774 | intermediate | baseline | 1000 | 870 | 130 | 0 | 0.87 | 0.8477315380448507 | 0.8894365570012204 | 118.39 | 0.426 | 34.543629 |
| c09edb17b74c9774 | intermediate | no_info | 1000 | 853 | 147 | 0 | 0.853 | 0.8297018143400393 | 0.873596395257969 | 118.206 | 0.448 | 32.954923 |
| 384756484b523c92 | expert | baseline | 300 | 144 | 156 | 0 | 0.48 | 0.4240757908015887 | 0.5364299463983206 | 277.7633333333333 | 2.6733333333333333 | 282.5388066666667 |
| 384756484b523c92 | expert | no_info | 300 | 154 | 146 | 0 | 0.5133333333333333 | 0.4569629909718754 | 0.5693665175615182 | 279.0133333333333 | 2.7066666666666666 | 268.42101333333335 |

## info_pair

| config_id | preset | games | b | c | mcnemar_exact_p | win_difference_pp |
|---|---|---|---|---|---|---|
| 34bcd556ea7ef52c | beginner | 1000 | 6 | 14 | 0.11531829833984375 | 0.8 |
| c09edb17b74c9774 | intermediate | 1000 | 39 | 22 | 0.03961701489849968 | -1.7 |
| 384756484b523c92 | expert | 300 | 12 | 22 | 0.12144948495551944 | 3.3333333333333335 |

