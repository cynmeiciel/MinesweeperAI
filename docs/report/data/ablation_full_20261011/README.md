# Full ablation run, 2026-10-11

Source solver commit: `eda8c6ca6d6b8607cc4b7da63f79c90a60929c31`.
All phases completed and validated. Defaults: OPENING, chord, BFS, center,
include_outside=False, seeds starting at zero, statistics enabled.

- Collection: beginner 1000, intermediate 1000, expert 300 baseline games.
- INFO: the same 2300 seeds/configurations, paired baseline/no_info: 4600 games.
- Total execution count 6900; collection is not an additional INFO sample.
- 2524 unique snapshots from 2526 occurrences: beginner 256, intermediate 831,
  expert 1437. Unique-state weighting, not occurrence or preset weighting.
- All 2524 baseline/no_degree/no_propagation triples matched exact component
  solutions and Fraction probabilities in one warmup and five measured repeats.
- No incomplete triples, infeasible snapshots, execution errors or stalled INFO games.
- 38 states have no frontier component (LV3 fallback), with zero DFS counters.
- Historical baseline outcomes/moves/guesses/coverage matched for all 2300 games;
  timing is not compared with the previous benchmark.

## Observed results

Relative to baseline on these snapshots, no_degree uses 1.111076× total nodes
and 1.013761× total median DFS time; no_propagation uses 6.208711× nodes and
5.392679× DFS time. No_propagation retains feasibility pruning.

| Preset | baseline wins | no_info wins | Difference no_info−baseline | Exact McNemar p |
|---|---:|---:|---:|---:|
| beginner | 961/1000 | 969/1000 | +0.8 pp | 0.115318 |
| intermediate | 870/1000 | 853/1000 | −1.7 pp | 0.039617 |
| expert | 144/300 | 154/300 | +3.333 pp | 0.121449 |

Intermediate meets nominal alpha=0.05 before correction. None meet the
Bonferroni threshold 0.05/3. Do not conclude equivalence or universal INFO
benefit. The timing difference for Degree is small and descriptive; it does
not establish a stable improvement across hardware. Frontier samples come
from baseline trajectories, not all possible states. Replay shares probability
code; independent brute-force tests cover finite small cases, not this entire
real-state sample.

`manifest.json` and `source_snapshot.zip` preserve measurement source and raw
checksums. `validation.json` records acceptance; `baseline_compatibility.json`
records the historical comparison. Summary CSV/Markdown and PNG/SVG figures
are derived from verified raw data. Word report and its separate hash audit are
in `../../reports/Bao_cao_Minesweeper_AI_cap_nhat_ablation.docx` and `.audit.json`.
Refresh TOC/page numbers in Word; pagination was not rendered here.
