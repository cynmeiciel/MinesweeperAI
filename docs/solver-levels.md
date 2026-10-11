# Minesweeper AI: LV1 to LV3

This document describes the deterministic rules and search algorithms used by
`lv1`, `lv2`, and `lv3`.

## Shared model

A solver receives only a `PlayerView`:

- Revealed cells expose their adjacent mine count.
- Hidden cells do not expose their contents.
- Flagged cells are visible as flags.
- Mine positions are never available to the solver.

A solver returns one `Move` at a time:

```text
reveal(cell) or flag(cell)
```

`certain=True` means the move is logically guaranteed. An uncertain LV3 move
is a probability-based reveal and is counted as a guess by the batch runner.

All solvers use row-major ordering for deterministic tie-breaking. On a fresh
board with no revealed number, the deterministic solvers open the available
cell nearest the board center. This is the opening move, not a constraint
 deduction.

## LV1: rule-based reasoning

LV1 scans revealed numbered cells in row-major order. For each source cell it
builds:

```text
unknown = hidden, unflagged neighbours
flagged = flagged neighbours
remaining_mines = number - flagged
```

It applies two local rules:

### Rule 1: all unknown neighbours are mines

If:

```text
len(unknown) == remaining_mines
```

then LV1 flags one unknown cell. Repeated calls flag the remaining cells.

### Rule 2: no mines remain around the number

If:

```text
remaining_mines == 0
```

then LV1 reveals one unknown cell. Repeated calls reveal the remaining cells.

If no rule applies, LV1 raises `SolverStuck` and returns the `STUCK` state to
its caller.

## LV2: constraint and subset reasoning

LV2 runs LV1 first. Only when LV1 is stuck does LV2 build constraints from
revealed numbered cells.

For every revealed number it stores:

```text
sum(unknown neighbours) = number - flagged neighbours
```

Each unknown cell is binary:

```text
0 = safe
1 = mine
```

Invalid constraints with a negative mine count or more mines than cells are
ignored.

### Difference rule

For two constraints:

```text
C1: sum(S1) = M1
C2: sum(S2) = M2
```

when `S1` is a proper subset of `S2`, LV2 derives:

```text
sum(S2 - S1) = M2 - M1
```

The process repeats until no new constraint is produced. Duplicate
constraints are removed.

### Guaranteed deductions

For every original or derived constraint:

```text
M == 0       -> every cell in S is safe
M == len(S)  -> every cell in S is a mine
```

LV2 returns one guaranteed reveal or flag at a time. If no derived constraint
is decisive, it raises `SolverStuck`.

## LV3: DFS, pruning, and probability

LV3 runs LV1 and then LV2 first. It performs DFS only when both lower levels
are stuck.

### 1. Build the frontier

The frontier is the set of hidden, unflagged cells that occur in at least one
number constraint. Cells outside the frontier are not DFS variables.

### 2. Split into components

Constraints are connected when they share a cell. LV3 groups connected
constraints into independent components:

```text
constraints -> connected components -> DFS per component
```

Solving components separately keeps each search space smaller.

### 3. DFS assignments

Each component is searched with binary assignments:

```text
cell = 0 -> safe
cell = 1 -> mine
```

At every recursive branch LV3:

1. Copies the current assignment.
2. Propagates constraints that are already forced.
3. Prunes impossible branches.
4. Selects the next variable using MCV.
5. Tries safe (`0`) and mine (`1`).

### Constraint pruning and propagation

For each constraint:

```text
assigned_mines = assigned cells with value 1
unassigned_cells = cells without an assignment
remaining_mines = required_mines - assigned_mines
```

The branch is invalid when:

```text
remaining_mines < 0
remaining_mines > len(unassigned_cells)
```

Propagation assigns:

```text
remaining_mines == 0
    -> all unassigned cells are safe

remaining_mines == len(unassigned_cells)
    -> all unassigned cells are mines
```

### MCV variable ordering

For every unassigned cell LV3 counts active constraints containing that cell.
It chooses the cell with the highest count. This tends to trigger propagation
earlier and prune invalid branches sooner.

### 4. Mine probabilities

For each component, LV3 keeps every valid DFS assignment. For a frontier
cell:

```text
P(mine) = valid assignments where cell is a mine
           -----------------------------------
                 all valid assignments
```

The implementation also uses the remaining mine budget when combining
component distributions. It counts compatible configurations across
components and the unsearched cells outside the frontier. This changes the
frontier probabilities, but the solver still chooses actions only from
frontier cells.

The remaining mine count shown in the move reason is:

```text
MINES_LEFT = total mines - placed flags
```

It is part of the global configuration used to filter valid assignments.

### 5. Choosing a move

LV3 selects in this order:

1. `P(mine) == 0` -> guaranteed `OPEN`.
2. `P(mine) == 1` -> guaranteed `FLAG`.
3. Otherwise, reveal the frontier cell with the smallest `P(mine)`.
4. If probabilities tie, choose the cell with the highest Information Gain.
5. If Information Gain also ties, use row-major order.

Uncertain high-probability cells are not flagged. Flags are reserved for
`P(mine) == 1`, because a wrong flag can corrupt later constraints.

### No-frontier fallback

If no frontier constraint exists but hidden cells remain, LV3 selects the
available hidden cell nearest the board center and reveals it. Its global
remaining-mine ratio is shown in the reason. This fallback prevents the
headless solver from stopping while unresolved cells remain outside every
known constraint.

## Solver pipeline

For every move the effective pipeline is:

```text
LV1 rules
  -> if stuck, LV2 subset constraints
  -> if stuck, LV3 component DFS
  -> probability selection
  -> one OPEN or FLAG action
  -> rebuild the view and repeat
```

A game ends with `WON` or `LOST`. A solver reports `STUCK` only when it has no
move to return, encounters an invalid state, or reaches the batch move limit.
