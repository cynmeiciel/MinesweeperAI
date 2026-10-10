# What heuristics could be used in Minesweeper?

This note explains the heuristics a Minesweeper AI can use, from the simplest
rule to the strongest search, using the team's solvers (`lv1`, `lv2`, `lv3`)
as worked examples. It ends with ideas for a `lv4` and the measured results.

Notation in the small diagrams:

```
A B C   hidden cells we reason about
1 2     revealed numbers
.       revealed empty / already-known cells
|       board edge
```

---

## 0. Two kinds of move

Every move an AI makes is one of two kinds:

| Kind | Meaning | Risk |
|---|---|---|
| **Deduction** | The cell is *proven* safe (or proven a mine) from the visible numbers. | None |
| **Guess** | No cell can be proven safe; pick the cell least likely to be a mine. | Can lose |

So there are two families of heuristics:

1. **Deduction heuristics** — find as many proven moves as possible, as cheaply
   as possible (sections 1–3).
2. **Guessing heuristics** — when nothing is provable, choose the guess that
   maximises the chance of *winning the game*, not just of surviving the next
   click (sections 4–5).

A solver always tries deduction first and guesses only when deduction is
stuck. That ordering is itself the first heuristic.

---

## 1. Single-cell rules (lv1)

Look at one revealed number at a time. Let

- `n` = the number shown,
- `F` = flagged neighbours,
- `H` = hidden (unflagged) neighbours.

**Rule 1 — all mines:** if `n − F = H`, every hidden neighbour is a mine.

```
| A B C
| 2 . .        the 2 touches only A and B as hidden cells
```
`2 − 0 = 2` hidden neighbours → **A and B are mines**.

**Rule 2 — all safe:** if `n − F = 0`, every hidden neighbour is safe.

```
| A B C
| 1 . .        A is already flagged
```
The 1 is "used up" by A → **B is safe**.

These two rules are cheap (they look at one cell) and solve most of an easy
board. They fail when every number touches more hidden cells than it has
mines left — then you have to combine numbers.

*Measured:* lv1 alone wins 62% on Beginner but 0% on Expert, because it
stops (stalls) instead of guessing.

---

## 2. Subset / difference rule (lv2)

Turn each number into a **constraint**: "these hidden cells contain exactly
k mines". Then compare constraints.

**If constraint X's cells are a subset of constraint Y's cells, the extra
cells of Y contain `k_Y − k_X` mines.**

```
| A B C
| 1 1 .        board edge on the left
```

- The left `1` sees `{A, B}` → `A + B = 1`
- The right `1` sees `{A, B, C}` → `A + B + C = 1`

`{A, B}` is inside `{A, B, C}`, so `C = 1 − 1 = 0` → **C is safe**.
Neither number alone could prove this. If the difference is all mines
(`k_Y − k_X` = number of extra cells), those cells are all **mines** instead.

lv2 repeats this until no new constraints appear. Famous patterns such as
"1-2-1" and "1-2-2-1" on a wall are special cases of this rule.

*Measured:* lv2 raises Intermediate from 24.5% to 57%.

---

## 3. Exhaustive search over the frontier — DFS (lv3)

Some deductions need three or more numbers at once. The general method:

1. **Frontier:** the hidden cells that touch at least one revealed number.
2. **Split the frontier into independent groups (components):** two cells
   are in the same group if some number touches both. Groups can be solved
   separately, which makes the search much smaller.
3. **Depth-first search (backtracking)** over each group: assign *mine* or
   *safe* to one cell at a time; after each assignment, **propagate** (apply
   rules 1 and 2 inside the search to force other cells); backtrack as soon
   as a number is violated. Every complete assignment that satisfies all
   numbers is a valid layout.
4. **Read the answer:** a cell that is safe in *every* valid layout is
   proven safe; a cell that is a mine in every layout is a proven mine.

Heuristics *inside* the search make it fast:

- **Most-constrained cell first** — branch on the cell that appears in the
  most unfinished constraints (lv3 does this). Contradictions show up early,
  so dead branches are cut sooner.
- **Constraint propagation** after each branch — often fixes many cells
  without branching.
- **Component splitting** — searching two groups of 20 cells is vastly
  cheaper than one group of 40.

### Mine probabilities and the global mine count

Counting layouts also gives **probabilities**, but layouts are *not* equally
likely: the rest of the board must hold the remaining mines.

Let `M` = mines not yet flagged, `U` = hidden cells *off* the frontier.
A frontier layout using `k` mines leaves `M − k` mines for the `U` other
cells, which can be arranged in `C(U, M − k)` ways. So each layout has
**weight `C(U, M − k)`**.

> Example: two layouts fit the numbers — X uses 1 mine, Y uses 2 mines.
> With `M = 3` and `U = 10`: weight(X) = C(10, 2) = 45, weight(Y) = C(10, 1) = 10.
> X is 4.5× more likely, even though both "fit".

`P(cell is a mine)` = (total weight of layouts where it is a mine) ÷ (total
weight). lv3 combines the groups exactly with this formula (by convolving
the per-group mine counts), which also catches **endgame deductions** that
only the total mine count can prove.

*Measured:* lv3 raises Expert from 4% to 49.5% and never stalls.

---

## 4. Guessing heuristics

When nothing is provable, the choice of guess decides most wins and losses.

### 4.1 Lowest mine probability (lv3)
Reveal the cell with the smallest `P(mine)`. The baseline for every
probability-based solver.

### 4.2 Tie-break by information (lv3)
Among equally safe cells, prefer the one involved in more constraints
(lv3's `INFO`): its number is more likely to unlock new deductions.

### 4.3 Consider off-frontier cells
A hidden cell that touches no number has probability

```
P(off-frontier mine) = (M − expected frontier mines) / U
```

Early on Expert this is often *lower* than every frontier cell. lv3 computes
it but currently never guesses there. Among off-frontier cells, prefer
**corners, then edges**: fewer neighbours means a higher chance of a 0,
which opens a whole area for free.

### 4.4 The first click
Under this project's default `OPENING` rule the first click is always a 0,
so any cell works; lv1 picks the centre. Under the `SAFE` or `UNSAFE` rules,
corners are better (more likely to be a 0). Note the first click is only a
*certain* move under `SAFE`/`OPENING`.

### 4.5 Safety + progress (one-step lookahead)
Lowest risk is not always best: a safe-looking cell whose number will
reveal nothing just postpones the problem. For each candidate, use the same
layout counting to compute the probability of each number it could show,
and how many new proven moves each would give. Among cells within a few
percent of the lowest risk, pick the one with the best
`P(safe) × P(it leads to progress)`. Strong published solvers rely mostly
on this idea.

### 4.6 Avoid "dead" cells
If a cell, *when safe*, can only ever show one possible number, revealing it
teaches nothing. Do not spend a guess on it unless it is the only option.

### 4.7 Endgame search
When only a few layouts remain, search every possible sequence of guesses
and pick the one with the highest probability of **winning the game**, not
of surviving the next click. This matters for 50/50 situations: some can be
avoided or resolved by guessing in the right order, or by guessing a cell
that splits the remaining layouts.

---

## 5. What cannot be fixed

Some boards force a pure 50/50 — two layouts that no number can ever
distinguish. **No solver wins 100%**. On Expert, the best public solvers are
reported somewhere in the mid-50s % (with slightly different rules, so treat
it as a rough ceiling, not a target).

---

## 6. Where BFS and DFS appear

| Where | Algorithm | Why |
|---|---|---|
| Revealing a 0 (flood fill, game engine) | **BFS** (queue) by default, **DFS** (stack) via `--flood-fill DFS` | Opens every connected 0 and its border; same cells either way, different order |
| Grouping the frontier into components (lv3) | Graph traversal | Cells linked by shared numbers |
| Enumerating layouts (lv3) | **DFS / backtracking** | Explores mine/safe choices depth-first, prunes on contradiction |

---

## 7. Measured results

Default rules (`OPENING` first click), 200 games per board, seeds 0–199,
same boards for every solver:

| Solver | Heuristics | Beginner 9×9/10 | Intermediate 16×16/40 | Expert 16×30/99 |
|---|---|---|---|---|
| random | none | 0% | 0% | 0% |
| lv1 | §1 | 62.0% | 24.5% | 0.0% |
| lv2 | §1–2 | 79.0% | 57.0% | 4.0% |
| lv3 | §1–3, 4.1–4.2 | **95.5%** | **84.5%** | **49.5%** |

Where lv3 still loses (fatal guess's mine probability):

| | Intermediate (300 games) | Expert (200 games) |
|---|---|---|
| Lost on a ~50/50 guess | 26 of 42 | 49 of 101 |
| Lost on a 20–49% guess | 7 | 24 |
| Lost on a <20% guess | 9 | 28 |

A quick experiment letting lv3 also guess off-frontier cells (§4.3) gave
52.5% vs 49.5% on Expert — promising but within noise for 200 games.

Reproduce with:

```bash
python -m minesweeper.analysis --solver lv3 --preset beginner --preset intermediate \
    --preset expert --games 200 --seed 0
```

To compare two versions fairly, use the **same seeds and at least 1,000
games**, and change **one heuristic at a time**.

---

## 8. Ideas for lv4, in order of value for effort

1. Make the layout search faster (count layouts per mine count instead of
   storing each one) — removes the slow ~20 s moves and makes 2–5 affordable.
2. Guess off-frontier cells too, preferring corners and edges (§4.3).
3. Safety + progress lookahead (§4.5).
4. Avoid dead cells (§4.6).
5. Endgame search for 50/50s (§4.7).
