# Acceptance smoke only

Beginner 9×9–10, seeds 0–9, OPENING, chord, BFS, center,
include_outside=False; statistics enabled for all variants.

- 10 baseline collection games; 1 unique DFS frontier.
- 10 paired baseline/no_info seeds (20 game rows), matching initial-board fingerprints.
- 3 replay rows: baseline, no_degree, no_propagation.
- One warmup and five measured repetitions per variant; exact solution sets
  and Fraction probabilities matched on every execution.
- All phases complete; summarizer validated raw CSV/JSONL and source checksums.

This sample validates execution and output, not heuristic effectiveness.
The full planned ablation sample was subsequently run and validated in
`../ablation_full_20261011`; keep this smoke separate.
The existing report's main benchmark numbers remain unchanged.
