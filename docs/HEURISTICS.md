# What heuristics could be used in Minesweeper?

This note explains the rules and heuristics a Minesweeper AI can use, using
the team's solvers (`lv1`, `lv2`, `lv3`) as worked examples. It separates
what is **proven correct** from what is a **heuristic**, then gives measured
results and ideas for a `lv4`. The full mathematics is in
[`ALGORITHMS.md`](ALGORITHMS.md).

Notation in the small diagrams (rows not drawn are already revealed):

```
A B C   hidden cells we reason about
1 2     revealed numbers
.       revealed empty / already-known cells
|       board edge
```

---

## 0. What counts as a heuristic?

A **heuristic** is a rule of thumb that gives up a guarantee in exchange for
speed or simplicity. To classify any rule, ask:

> **Can this rule ever give a worse result than the exact method?**

| Answer | Category | Effect |
|---|---|---|
| No, and it is proven correct | **A. Sound inference / exact method**, *not* a heuristic | Always correct |
| No, but it is a bet about what is *faster* | **B. Search heuristic** | Changes speed, never the result |
| Yes, it can pick a worse move | **C. Decision heuristic** | Changes how often you win |

Every move an AI makes is either a **deduction** (the cell is proven safe or
proven a mine: no risk) or a **guess** (nothing is provable: risk). Group A
produces deductions, group B makes producing them faster, and group C
chooses guesses.

"Deduce before you guess" is **not** a heuristic: revealing a proven-safe
cell costs no risk and can only add information, so doing it first is
always right.

---

## A. Sound inference rules and exact methods (not heuristics)

These never mark a cell wrongly. lv1 → lv2 → lv3 is not "better
heuristics" but **more complete inference**: lv1 and lv2 are sound but
miss some deductions; lv3 finds all of them.

### A1. Single-cell rules (lv1)

Look at one revealed number at a time. Let

- `n` = the number shown,
- `F` = flagged neighbours,
- `H` = hidden (unflagged) neighbours.

**Rule 1: all mines.** If `n − F = H`, every hidden neighbour is a mine.

```
| A B C
| 2 . .        the 2 touches only A and B as hidden cells
```
`2 − 0 = 2` hidden neighbours → **A and B are mines**.

**Rule 2: all safe.** If `n − F = 0`, every hidden neighbour is safe.

```
| A B C
| 1 . .        A is already flagged
```
The 1 is "used up" by A → **B is safe**.

> **Why not a heuristic:** each rule is a short proof (a sum of 0/1 values
> equal to its maximum or to 0 forces every term). It is never wrong. It is
> *incomplete*, it fails when every number touches more hidden cells than
> it has mines left, but incomplete is not the same as heuristic.

*Measured:* lv1 alone wins 62% on Beginner but 0% on Expert, because it
stops (stalls) instead of guessing.

### A2. Subset / difference rule (lv2)

Turn each number into a **constraint**: "these hidden cells contain exactly
k mines". If constraint X's cells are a subset of constraint Y's cells, the
extra cells of Y contain `k_Y − k_X` mines.

```
| A B C
| 1 1 .        board edge on the left
```

- The left `1` sees `{A, B}` → `A + B = 1`
- The right `1` sees `{A, B, C}` → `A + B + C = 1`

`{A, B}` is inside `{A, B, C}`, so `C = 1 − 1 = 0` → **C is safe**. Neither
number alone could prove this. If the difference equals the number of extra
cells, those cells are all **mines** instead. lv2 repeats this until no new
constraint appears; patterns such as "1-2-1" on a wall are special cases.

> **Why not a heuristic:** it is a theorem
> (`sum(B) − sum(A) = sum(B \ A)`), so it is always correct. Like A1 it is
> incomplete: it only combines *nested* constraints.

*Measured:* lv2 raises Intermediate from 24.5% to 57%.

### A3. Exhaustive search of the frontier: DFS (lv3)

1. **Frontier:** the hidden cells that touch at least one revealed number.
2. **Components:** two frontier cells are in the same group if some number
   touches both. Groups are solved separately.
3. **Depth-first search (backtracking)** over each group: assign *mine* or
   *safe* to one cell at a time.
   - **Bound pruning:** backtrack as soon as some number can no longer be
     satisfied.
   - **Propagation:** after each assignment, apply A1 inside the search to
     force other cells.
4. **Read the answer:** a cell that is safe in *every* valid layout is
   proven safe; a mine in every layout is a proven mine.

> **Why not a heuristic:** the search visits every consistent layout, so its
> deductions are **complete**: no rule can find a safe frontier cell that it
> misses. Pruning only cuts branches that provably contain no solution, and
> component splitting is a theorem (the solutions of independent groups
> combine as a Cartesian product), so neither changes the result. They are
> exact speed-ups, not heuristics. Only the *order* in which cells are
> branched on is a heuristic (see B2).

### A4. Exact mine probabilities with the global mine count (lv3)

Counting layouts also gives **probabilities**, but layouts are *not*
equally likely: the rest of the board must hold the remaining mines.

Let `M` = mines not yet flagged, `U` = hidden cells *off* the frontier. A
frontier layout using `k` mines leaves `M − k` mines for the `U` other cells,
which can be arranged in `C(U, M − k)` ways. So each layout has **weight
`C(U, M − k)`**.

> Example: two layouts fit the numbers. X uses 1 mine, Y uses 2 mines.
> With `M = 3` and `U = 10`: weight(X) = C(10, 2) = 45, weight(Y) = C(10, 1) = 10.
> X is 4.5× more likely, even though both "fit".

`P(cell is a mine)` = (total weight of layouts where it is a mine) ÷ (total
weight). lv3 combines the groups with this formula, which also catches
**endgame deductions** that only the total mine count can prove.

> **Why not a heuristic:** it follows exactly from Bayes' theorem and the
> fact that boards are generated uniformly at random (proof in
> `ALGORITHMS.md` §7). The probabilities are exact, not estimates. What a
> solver *does* with them is where heuristics start (group C).

*Measured:* lv3 raises Expert from 4% to 49.5% and never stalls.

---

## B. Search heuristics (change speed, never the result)

### B1. Cheap rules first, search only when stuck

lv3 tries A1, then A2, and runs the DFS (A3) only when both are stuck.

> **Why it is a heuristic:** the DFS alone would find every move A1 and A2
> find. Running them first is a bet that it is usually faster, because most
> positions are solved by the cheap rules. It never changes which cells are
> proven, only how long it takes.

### B2. Most-constrained cell first (inside the DFS)

Branch on the cell that appears in the most unfinished constraints (lv3
does this). Wrong choices then violate a number sooner, so bad branches are
cut near the top of the search tree.

> **Why it is a heuristic:** any branching order gives exactly the same set
> of layouts. This order is only *expected* to be faster; there is no
> guarantee it is on every position.

---

## C. Decision heuristics (choosing a guess)

When nothing is provable, the player must guess. The true goal is to
**maximise the probability of winning the whole game**. The exact best guess
comes from searching the full game tree of future clicks, which is far too
expensive except at the very end. Every rule below is a cheaper
approximation of that exact choice, so each can sometimes pick a worse move.

### C1. Lowest mine probability (lv3)

Reveal the cell with the smallest `P(mine)` (from A4).

> **Why it is a heuristic:** it is *greedy*. It maximises survival of the
> *next* click, not the chance of winning the game. A slightly riskier cell
> can be better if its number unlocks the rest of the board.

### C2. Tie-break by information (lv3)

Among equally safe cells, prefer the one involved in more constraints (lv3's
`INFO`).

> **Why it is a heuristic:** it assumes such a cell's number will unlock more
> deductions. Plausible, but not proven for every position.

### C3. Consider off-frontier cells; prefer corners and edges

A hidden cell that touches no number has probability

```
P(off-frontier mine) = (M − expected frontier mines) / U
```

Early on Expert this is often *lower* than every frontier cell. lv3 computes
it but currently never guesses there. Among off-frontier cells, prefer
**corners, then edges**: with fewer neighbours, a safe corner shows a 0 about
3× as often as an interior cell on Expert, opening an area for free.

> **Why it is a heuristic:** the probability itself is exact, but "prefer
> corners" rests on an approximation (`(1 − ρ)^3` vs `(1 − ρ)^8`, with `ρ` the
> mine density) and on the assumption that an opening is worth more than a
> slightly lower risk elsewhere.

### C4. The first click

Under this project's default `OPENING` rule the first click is always a 0,
so any cell works; lv1 picks the centre. Under the `SAFE` or `UNSAFE` rules,
corners are usually better (more likely to be a 0).

> **Why it is a heuristic:** under `OPENING` the choice does not matter;
> under the other rules, "corner first" is a rule of thumb based on the same
> approximation as C3. (The first click is only a *certain* move under
> `SAFE`/`OPENING`; under `UNSAFE` it is a guess.)

### C5. Safety + progress (one-step lookahead)

For each candidate, use the layout counting to compute the probability of
each number it could show, and how many new proven moves each would give.
Among cells within a few percent of the lowest risk, pick the one with the
best `P(safe) × P(it leads to progress)`. Strong published solvers rely
mostly on this idea.

> **Why it is a heuristic:** it looks only one click ahead, and the margin
> ("within a few percent") is an arbitrary choice.

### C6. Avoid "dead" cells

If a cell, *when safe*, can only ever show one possible number, revealing it
teaches nothing. Do not spend a guess on it unless it is the only option.

> **Why it is a heuristic:** it is almost always right, but not proven to be
> the best choice in every position.

### C7. Endgame search

When only a few layouts remain, search every possible sequence of guesses
and pick the one with the highest probability of **winning the game**. This
matters for 50/50 situations: some can be avoided or resolved by guessing in
the right order, or by guessing a cell that splits the remaining layouts.

> **Heuristic or not?** The search itself is **exact**: it computes the true
> best move. Only the decision *when* to switch to it ("few layouts left")
> is a heuristic threshold.

---

## D. Summary

| Item | Category | Used by |
|---|---|---|
| A1 Single-cell rules | Sound inference (not a heuristic) | lv1, lv2, lv3 |
| A2 Subset rule | Sound inference (not a heuristic) | lv2, lv3 |
| A3 DFS of the frontier, pruning, components | Exact method (not a heuristic) | lv3 |
| A4 Exact probabilities, global mine count | Exact method (not a heuristic) | lv3 |
| "Deduce before you guess" | Provably right (not a heuristic) | all |
| B1 Cheap rules first | Search heuristic | lv2, lv3 |
| B2 Most-constrained cell first | Search heuristic | lv3 |
| C1 Lowest mine probability | Decision heuristic | lv3 |
| C2 Information tie-break | Decision heuristic | lv3 |
| C3 Off-frontier, corners and edges | Decision heuristic | lv4 idea |
| C4 First click | Decision heuristic | lv1, lv2, lv3 (centre) |
| C5 Safety + progress | Decision heuristic | lv4 idea |
| C6 Avoid dead cells | Decision heuristic | lv4 idea |
| C7 Endgame search | Exact search, heuristic switch point | lv4 idea |

The key consequence: **lv3's deduction is already complete**, so a better
solver can only gain in two places: speed (group B) and guessing (group C).

---

## E. What cannot be fixed

Some boards force a pure 50/50: two layouts that no number can ever
distinguish. **No solver wins 100%.** On Expert, the best public solvers
are reported somewhere in the mid-50s % (with slightly different rules, so
treat it as a rough ceiling, not a target).

---

## F. Where BFS and DFS appear

| Where | Algorithm | Why |
|---|---|---|
| Revealing a 0 (flood fill, game engine) | **BFS** (queue) by default, **DFS** (stack) via `--flood-fill DFS` | Opens every connected 0 and its border; same cells either way, different order |
| Grouping the frontier into components (lv3) | Graph traversal | Cells linked by shared numbers |
| Enumerating layouts (lv3) | **DFS / backtracking** | Explores mine/safe choices depth-first, prunes on contradiction |

---

## G. Measured results

Default rules (`OPENING` first click), 200 games per board, seeds 0–199,
same boards for every solver:

| Solver | Uses | Beginner 9×9/10 | Intermediate 16×16/40 | Expert 16×30/99 |
|---|---|---|---|---|
| random | nothing | 0% | 0% | 0% |
| lv1 | A1, C4 | 62.0% | 24.5% | 0.0% |
| lv2 | A1–A2, B1, C4 | 79.0% | 57.0% | 4.0% |
| lv3 | A1–A4, B1–B2, C1–C2, C4 | **95.5%** | **84.5%** | **49.5%** |

Where lv3 still loses (fatal guess's mine probability):

| | Intermediate (300 games) | Expert (200 games) |
|---|---|---|
| Lost on a ~50/50 guess | 26 of 42 | 49 of 101 |
| Lost on a 20–49% guess | 7 | 24 |
| Lost on a <20% guess | 9 | 28 |

A quick experiment letting lv3 also guess off-frontier cells (C3) gave
52.5% vs 49.5% on Expert: promising but within noise for 200 games.

Reproduce with:

```bash
python -m minesweeper.analysis --solver lv3 --preset beginner --preset intermediate \
    --preset expert --games 200 --seed 0
```

To compare two versions fairly, use the **same seeds and at least 1,000
games**, and change **one heuristic at a time**.

---

## H. Ideas for lv4, in order of value for effort

1. Make the layout search faster (count layouts per mine count instead of
   storing each one). An exact speed-up: removes the slow ~20 s moves and
   makes 2–5 affordable.
2. Guess off-frontier cells too, preferring corners and edges (C3).
3. Safety + progress lookahead (C5).
4. Avoid dead cells (C6).
5. Endgame search for 50/50s (C7).
