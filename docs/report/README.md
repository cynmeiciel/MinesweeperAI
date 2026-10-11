# Reproducible Minesweeper experiments

The updated Vietnamese report is available in
[reports/Bao_cao_Minesweeper_AI_cap_nhat_thuc_nghiem.docx](reports/Bao_cao_Minesweeper_AI_cap_nhat_thuc_nghiem.docx),
with report update and structure audits beside it. The validated full dataset
is [data/full_20261011](data/full_20261011). Word pagination was not rendered;
update the table of contents and page numbers in Word before submission.

These scripts generate the raw data, tables, and figures used by the report.
They resolve the repository root from their own location, so the commands do
not depend on the current working directory.

## Setup

The experiment runner and summarizer use the Python standard library. Plotting
requires matplotlib:

```powershell
python -m pip install matplotlib
```

The project test dependencies remain available through the existing `pytest`
setup. The scripts were written for Python 3.11 or newer.

## Run experiments

A small smoke run:

```powershell
python docs/report/scripts/run_experiments.py `
  --suite main `
  --games 5 `
  --out-dir docs/report/data/smoke_001
```

The full suite uses the sample sizes defined in the experiment specification:

```powershell
python docs/report/scripts/run_experiments.py `
  --suite all `
  --out-dir docs/report/data/run_001
```

`--out-dir` is required and must be empty or absent. Existing output is never
overwritten. Use a new directory for every run. Seeds for game `i` are
`seed_start + i`; `--seed-start` defaults to `0`.

Available suites are `all`, `main`, `first-click`, `density`, `flood-fill`,
`corner`, and `outside`. `--games N` overrides the sample size for smoke runs.
When `all` is used, identical configurations shared between groups are run
once and referenced by multiple group names in the manifest.

Each experiment writes one CSV row after every completed game and flushes the
file. The CSV contains the existing `GameRecord` fields plus:

- `experiment_id`
- `opening_strategy`
- `include_outside`

`guesses` counts moves with `certain=False`. Under `UNSAFE`, the opening move
is currently marked certain and is therefore not counted as a guess.

## Summarize

```powershell
python docs/report/scripts/summarize_results.py `
  --data-dir docs/report/data/run_001
```

The summarizer validates the manifest, CSV schema, expected row counts, result
values, duplicate seeds, and complete seed ranges. It refuses to create the
official tables from an interrupted run.

It writes:

- `summary.csv`: one row per complete configuration.
- `tables.md`: tables for solver/preset, first-click rules, density, flood fill,
  center/corner, outside-frontier, and LV3 timing.

Wilson 95% intervals use the existing `wilson_interval` implementation. The
95th percentile uses linear interpolation at position `(n - 1) * q`; this is
the fixed method used for all timing summaries. Times are in milliseconds.

## Plot

```powershell
python docs/report/scripts/plot_results.py `
  --data-dir docs/report/data/run_001
```

Figures are written to `figures/` as both 300 DPI PNG and SVG:

- `win_rate_by_solver`: grouped solver bars by preset with Wilson intervals.
- `win_rate_by_density`: LV3 win rate against actual mine density with Wilson
  intervals.

The intended report mapping is `win_rate_by_solver` to Figure 4.1 and
`win_rate_by_density` to Figure 4.2. Missing groups are reported instead of
being filled with guessed values.

## Manifest and interpretation limits

`manifest.json` records the schema version, Git commit, working-tree state,
Python executable/version, OS, CPU when available, timestamps with timezone,
command line, and every configuration's expected/completed counts and CSV
path. When the working tree is dirty, the run should be associated with the
working-tree patch saved beside the data by the runner.

The same seed only guarantees the same board when board-generation rules and
the opening cell are the same. Center/corner and `SAFE`/`OPENING` variants can
therefore generate different boards for the same seed. Timing depends on the
machine and environment. `stalled` may represent a solver stop, an illegal
move, an exception, or the batch move limit. Confidence intervals describe
sampling uncertainty; overlapping Wilson intervals alone are not a statistical
significance test.

## Verified cloud workflow and sample reuse

From the checkout root on Linux/macOS:

```bash
export UV_CACHE_DIR=/workspace/.cache/uv  # cloud home cache is read-only
uv sync --locked --extra report
uv run --no-sync pytest -q
uv run --no-sync python docs/report/scripts/run_experiments.py --suite all --games 5 --out-dir docs/report/data/smoke_new
uv run --no-sync python docs/report/scripts/summarize_results.py --data-dir docs/report/data/smoke_new
MPLCONFIGDIR=/workspace/.cache/matplotlib uv run --no-sync python docs/report/scripts/plot_results.py --data-dir docs/report/data/smoke_new
```

Use a **new** output directory for the full run and omit `--games`:

```bash
uv run --no-sync python docs/report/scripts/run_experiments.py --suite all --out-dir docs/report/data/run_new
uv run --no-sync python docs/report/scripts/summarize_results.py --data-dir docs/report/data/run_new
MPLCONFIGDIR=/workspace/.cache/matplotlib uv run --no-sync python docs/report/scripts/plot_results.py --data-dir docs/report/data/run_new
```

Absolute script and output paths also work from another directory. No display,
credentials, or running services are required. Plotting is headless. The cloud
run uses Python 3.12.14; the uv environment locks matplotlib 3.11.2.

| Group | Configurations | Games per configuration |
|---|---|---:|
| main | random/lv1/lv2/lv3 × 5×5–3, 9×9–10, 16×16–40 | 1,000 |
| main | same solvers × 16×30–99 | 300 |
| first-click | lv3 9×9–10 × OPENING/SAFE/UNSAFE | 1,000 |
| density | lv3 9×9 × 5–24 integer mines, inclusive | 500 |
| flood-fill | lv3 9×9–10 × BFS/DFS | 1,000 |
| corner | lv3 9×9–10 × center/corner × SAFE/OPENING | 1,000 |
| outside | lv3 9×9–10 and 16×16–40 × False/True | 1,000 |
| outside | lv3 16×30–99 × False/True | 300 |

Defaults are OPENING, chord enabled, BFS, center opening, outside=False.
Random retains its random first move, recorded as `opening_strategy=random`.
The all suite contains **43 unique configurations and 30,000 distinct game
records**. A shared CSV holds the largest requested sample, not a sum of
requests. For 9×9–10 LV3 baseline it holds 1,000 seeds; the density table uses
only its first 500 seeds. `group_games` records these distinct sample sizes.
The density baseline overlaps the main sample and is not independent.

The summarizer additionally writes `group_summary.csv`: group-specific views
retaining each requested seed prefix. Plots read these views, all computed
from validated CSVs, to preserve the 500-game density sample. They refuse
incomplete solver grids or missing density points. Solver hatches supplement
colors; titles give sample sizes and rules.

`mean_safe_coverage` is the arithmetic mean of
`cells_revealed / (rows * cols - mines)` over games;
`stalled_safe_coverage` restricts that mean to stalled games and is empty when
there are none. No mine cell is counted as revealed by this metric. Tables
include moves, guesses, coverage and mean/median/p95/max times.

Raw CSV keeps all GameRecord fields: seed, rows, cols, mines, density,
first_click, chord, flood_fill, solver, result, moves, guesses, cells_revealed,
mines_remaining, cells_remaining and time_ms, plus the three experiment fields
described above. Raw density follows GameRecord's four-decimal rounding;
summary density is computed from integer mines and dimensions. Time follows
the engine's three-decimal ms recording; statistics apply no further rounding
before calculation.

| Report section | Group / output |
|---|---|
| 4.2.1 and Figure 4.1 | main, win_rate_by_solver.png/.svg |
| 4.2.2 | first-click |
| 4.2.3 and Figure 4.2 | density, win_rate_by_density.png/.svg |
| 4.2.4 | flood-fill |
| 4.2.5 opening position | corner |
| 4.2.5 frontier candidates | outside |
| 4.2.6 whole-game LV3 timing | main, restricted to lv3 |
| 4.3 safe-cell progress | main, coverage columns |

Schema 2 records suite, seed start, games override, group sample sizes, CSV
SHA-256 checksums, and source SHA-256 hashes. `source_snapshot.zip` preserves
the Python application and experiment scripts actually used, including
untracked Python files; `working_tree.patch` preserves tracked edits. Output
files can make the working tree dirty without changing solver code.
Summarization checks the planned matrix, snapshot/CSV hashes, per-row
configuration, seed ranges and basic numeric invariants. Do not use interrupted
runs as official results or append their samples to another run.

The uploaded report's numbers remain historical until reconciled with a
complete validated run. `docs/HEURISTICS.md` describes a separate 200-game
sample and must not be merged into this dataset. Replication compares outcomes,
moves, guesses and revealed cells, excluding time_ms.

The original reproduction spec does not measure individual heuristic contributions.
The separate ablation workflow below implements those measurements. Coverage
remains descriptive.


## Ablation: Degree Heuristic, propagation and INFO

Specification: [Spec_ablation_Minesweeper.md](Spec_ablation_Minesweeper.md).
Run from the repository root after `uv sync --locked --extra report`:

```bash
# Acceptance smoke: beginner, seeds 0–9, one warmup + five measured replays.
uv run python docs/report/scripts/run_ablation.py --presets beginner --games 10 --out-dir docs/report/data/ablation_smoke_new
uv run python docs/report/scripts/summarize_ablation.py --data-dir docs/report/data/ablation_smoke_new

# Full planned sample: beginner 1000, intermediate 1000, expert 300.
uv run python docs/report/scripts/run_ablation.py --out-dir docs/report/data/ablation_full_new
uv run python docs/report/scripts/summarize_ablation.py --data-dir docs/report/data/ablation_full_new

# Alternatively, separate phases using exactly the same source and saved settings.
uv run python docs/report/scripts/run_ablation.py --phase collect --out-dir docs/report/data/ablation_phased_new
uv run python docs/report/scripts/run_ablation.py --phase replay --out-dir docs/report/data/ablation_phased_new
uv run python docs/report/scripts/run_ablation.py --phase games --out-dir docs/report/data/ablation_phased_new
uv run python docs/report/scripts/summarize_ablation.py --data-dir docs/report/data/ablation_phased_new
```

Initial options include `--seed-start`, `--repetitions` (default 5),
`--shuffle-seed` (default 0), `--opening-strategy`, `--include-outside`,
`--first-click` and `--flood-fill`. Defaults remain center, outside=False,
OPENING, BFS and chord=True. Continuations reject option overrides, modified
source, or an already-started phase. Failed/interrupted phases require a fresh
run directory; they are never overwritten or silently resumed. DFS has no
new timeout, approximation or cache, so difficult frontiers can take a long time.

`DfsSolver` accepts `variable_order="degree"`, `use_propagation=True`,
`guess_tiebreak="info"` and `collect_stats=False`. The latter disables counters
and timers in normal play. `last_stats` and `component_stats` reset on every
`next_move`, including moves handled by LV1/LV2. Ablation runners explicitly
turn statistics on for all variants.

| Variant | Variable order | Forced propagation | Guess tie break |
|---|---|---|---|
| baseline | Degree Heuristic | enabled | original constraint count (INFO) |
| no_degree | coordinate | enabled | INFO |
| no_propagation | Degree Heuristic | disabled | INFO |
| no_info | Degree Heuristic | enabled | coordinate |

Disabling propagation retains feasibility pruning at every DFS node. Removing
INFO affects only equal-probability guesses; certain safe cells and flags keep
their existing selection. Default game outcomes are checked against the first
ten beginner records of the historical benchmark, excluding elapsed time.

Collection runs baseline games and observes only states where LV1/LV2 are
stuck, before DFS. `frontiers.jsonl` contains observable PlayerView fields,
original constraints (including duplicates), configuration, canonical input
SHA-256, and seed/step occurrences. It contains no hidden mine layout.
Identical inputs are deduplicated; each unique snapshot contributes once to
replay summaries. Occurrences are preserved without acting as weights.
`collection_games.csv` is diagnostic and is not merged into the paired INFO sample.

Replay solves exactly the same snapshots using baseline, no_degree and
no_propagation. Exact component solution sets and global Fraction probabilities
must agree in every warmup and measured repetition. A mismatch stops the run
and blocks summarization. Component/global infeasibility is recorded separately
and excluded from performance ratios. Each snapshot has one warmup per variant
and five measured repetitions by default, with seeded shuffled variant order
and sequential execution. CSV counters represent one search; median DFS and
probability times represent measured repetitions, not their sum.

`ablation_games.csv` contains complete GameRecord fields, settings, aggregated
stats and initial-board fingerprints for baseline/no_info games. The fingerprint
is computed by the experiment harness after the first move and is never supplied
to inference. Pairing requires the same configuration, seed and fingerprint;
matching seeds alone is insufficient. `time_ms` is whole-game elapsed time;
collection callbacks have additional overhead and their timing is not the INFO
comparison. Execution errors are recorded and rejected by the summarizer.

| DFSStats field | Definition |
|---|---|
| nodes_visited | every entered node, including roots, rejected nodes and solutions |
| branch_points | nodes selecting a variable and exploring both 0/1 children |
| pruned_nodes | infeasible nodes, counted once per node |
| forced_assignments | new assignments from propagation, excluding branching |
| constraint_checks | constraints scanned by propagation/feasibility checking |
| propagation_passes | passes including the final unchanged pass; zero when disabled |
| max_depth | branching depth, root zero; maximum across components/moves |
| solutions_count | enumerated component solutions, summed across components |
| dfs_time_ms | component DFS elapsed time from perf_counter_ns, summed |
| probability_time_ms | separate global probability calculation time |
| components_count | number of components solved |
| largest_component_variables | maximum component size |

Move/game aggregation sums counters and times and takes maxima for depth and
component size. Timing DFS excludes the subsequent probability calculation.
Whole-game node counts are diagnostic: INFO changes later trajectories, so
those counts do not isolate the effect of Degree Heuristic or propagation.

Outputs include `ablation_frontiers.csv`, `ablation_games.csv`,
`ablation_summary.csv`, `ablation_tables.md` and `manifest.json`. The manifest
records planned samples, phases, replay status, variant settings, repetition
counts, commands, source hashes/snapshot/patch and raw-data checksums. The
summarizer verifies the matrix, paired boards, counters, provenance and complete
matched triples before writing tables. For an interrupted replay only,
`--allow-incomplete-replay` explicitly excludes entire incomplete triples;
collection and paired games must still be complete, and recorded mismatches
or failures are never accepted.

Replay tables report matched/feasible/infeasible/excluded snapshot counts,
mean/median/P95 nodes, mean pruning/forced assignments, median/P95 DFS time and
ratios of total nodes/time on the same feasible snapshots. INFO tables include
wins/losses/stalls, Wilson 95% win-rate intervals, moves/guesses, paired discordant
counts b (baseline-only win) and c (no_info-only win), the win-rate difference
(no_info minus baseline, percentage points), and exact two-sided McNemar p.
This p-value is unadjusted for multiple comparisons. Overlapping Wilson intervals
and non-significance do not establish equivalence.

Acceptance data in `data/ablation_smoke_20261011` is a ten-game beginner smoke,
not the full planned benchmark. Independent tests enumerate all binary vectors
for small components and full small boards, comparing solution sets and exact
mine probabilities without using solver propagation as an oracle. These finite
checks do not prove correctness for all boards. The full ablation run is now validated in `data/ablation_full_20261011`: 6900
game executions, 2300 INFO pairs and 2524 exact matched replay triples. The new
Word report is `reports/Bao_cao_Minesweeper_AI_cap_nhat_ablation.docx`; all main
benchmark tables and original images are preserved. See the full-run README
for effect sizes and multiple-comparison interpretation. The earlier report
remains available as the input template.


## Updating the Word report after full ablation

Validate the completed full sample first. To create a separate updated DOCX,
install `python-docx` alongside the optional matplotlib report dependency,
then run:

```bash
MPLCONFIGDIR=/tmp/minesweeper-matplotlib XDG_CACHE_HOME=/tmp/minesweeper-cache python docs/report/scripts/update_ablation_report.py --template docs/report/reports/Bao_cao_Minesweeper_AI_cap_nhat_thuc_nghiem.docx --data-dir docs/report/data/ablation_full_20261011 --out docs/report/reports/Bao_cao_Minesweeper_AI_cap_nhat_ablation.docx
```

The updater rejects smoke data, incomplete replay and non-default configurations.
It creates two PNG/SVG figures, adds ablation setup/results/paired comparisons,
updates stale limitations and the appendix, and verifies preservation of all
existing tables and illustrations. The accompanying `.audit.json` records
source report, output, manifest, summary, script and figure hashes. Output paths
must be new. Open the document in Word to refresh its table of contents and
page numbers; pagination is not rendered or verified in this environment.
