# Minesweeper: Algorithms, Theory and Mathematics

This document explains *why* the algorithms used in this project work: the
game as a mathematical object, the flood fill, board generation, logical
deduction, the depth-first search over mine layouts, exact mine
probabilities, decision-making under uncertainty, and the statistics used to
evaluate solvers. A shorter, example-driven overview of the heuristics is in
[`HEURISTICS.md`](HEURISTICS.md).

---

## 1. The game as a mathematical object

### 1.1 Board and neighbourhoods

A board has $R$ rows and $C$ columns. The set of cells is

$$
\mathcal{C} = \{(r, c) : 0 \le r < R,\ 0 \le c < C\}, \qquad N = |\mathcal{C}| = RC .
$$

The **neighbourhood** of a cell $x = (r, c)$ is the set of up to 8 cells
around it (the Moore neighbourhood, excluding $x$ itself):

$$
\mathcal{N}(x) = \{(r + \delta_r,\ c + \delta_c) \in \mathcal{C} : \delta_r, \delta_c \in \{-1, 0, 1\},\ (\delta_r, \delta_c) \ne (0, 0)\}.
$$

Interior cells have 8 neighbours, edge cells 5, corner cells 3.

### 1.2 Mines and numbers

A board hides a **mine set** $\mathcal{M} \subseteq \mathcal{C}$ with
$|\mathcal{M}| = M$. Equivalently, an indicator variable for every cell:

$$
m_x = \begin{cases} 1 & x \in \mathcal{M} \\ 0 & \text{otherwise.} \end{cases}
$$

The number shown on a safe cell $x$ is the count of mines around it:

$$
n(x) = \sum_{y \in \mathcal{N}(x)} m_y \qquad (0 \le n(x) \le |\mathcal{N}(x)|).
$$

The **mine density** is $\rho = M / N$ (Beginner 12.3%, Intermediate
15.6%, Expert 20.6%).

### 1.3 Win and loss

Let $\mathcal{R}$ be the set of revealed cells. The game is

- **lost** as soon as a cell $x \in \mathcal{M}$ is revealed;
- **won** when every safe cell is revealed:
  $|\mathcal{R}| = N - M$ with $\mathcal{R} \cap \mathcal{M} = \emptyset$.

Flags are only notes for the player; they play no part in the win
condition.

---

## 2. Flood fill (BFS / DFS)

### 2.1 Why revealing a 0 is safe to expand

If $n(x) = 0$ then $\sum_{y \in \mathcal{N}(x)} m_y = 0$, and since every
$m_y \ge 0$, **every neighbour of $x$ is safe**. Revealing them cannot
lose, so the game reveals them automatically. Any of those neighbours that
is itself a 0 makes *its* neighbours safe too, and so on.

### 2.2 As a graph problem

Build the graph $G_0$ whose vertices are safe cells and where an edge joins
$x$ and $y \in \mathcal{N}(x)$ whenever $n(x) = 0$. Clicking a cell $s$
reveals exactly the set of cells **reachable from $s$** in $G_0$: the
connected region of zeros containing $s$, plus its border of numbered cells
(those are reached but do not expand further, because their number is not 0).

Any complete graph traversal computes this reachable set:

- **BFS** stores the frontier in a **queue** (first in, first out). Cells are
  revealed in rings of increasing distance from the click.
- **DFS** stores the frontier in a **stack** (last in, first out). Cells are
  revealed by following one path as deep as possible before backtracking.

**Both reveal exactly the same set**, because reachability does not depend
on visiting order; only the *order* differs. The project tests this on
random 16×16 boards.

### 2.3 Complexity and the recursion trap

Each cell enters the queue/stack at most once (a `seen` set guards it) and
each visit inspects at most 8 neighbours, so the cost is

$$
O(8N) = O(RC)
$$

time and $O(RC)$ memory. A *recursive* DFS would also be $O(RC)$, but its
recursion depth can reach the size of the zero region; on a large empty
board that exceeds Python's default recursion limit (≈1000). The project
therefore uses an explicit stack/queue (iterative traversal).

---

## 3. Board generation

### 3.1 Uniform random layouts

Given a set $\mathcal{A} \subseteq \mathcal{C}$ of **allowed** cells, the
generator draws $M$ distinct cells uniformly at random (sampling without
replacement). Every mine set $\mathcal{M} \subseteq \mathcal{A}$ with
$|\mathcal{M}| = M$ has the same probability

$$
P(\mathcal{M}) = \binom{|\mathcal{A}|}{M}^{-1}.
$$

This uniformity is what makes the probability formulas of §6 exact.

### 3.2 First-click rules

| Rule | Excluded cells $\mathcal{E}$ | $\mathcal{A} = \mathcal{C} \setminus \mathcal{E}$ | Constraint |
|---|---|---|---|
| `UNSAFE` | none (mines placed before the click) | $\mathcal{C}$ | $M \le N$ |
| `SAFE` | the clicked cell $s$ | $\mathcal{C} \setminus \{s\}$ | $M \le N - 1$ |
| `OPENING` | $s$ and $\mathcal{N}(s)$ | $\mathcal{C} \setminus (\{s\} \cup \mathcal{N}(s))$ | $M \le N - \min(9, N)$ |

Under `OPENING`, $n(s) = 0$ by construction, so the first click always
starts a flood fill.

**Why `UNSAFE` loses on the first click with probability $\rho$:** the first
click lands on a mine with probability $M/N$. An experiment earlier in this
project showed that if the solver's random generator is seeded *identically*
to the board's generator, the solver's first random pick reproduces the
board's first mine and loses 100% of the time. The two random streams must
be **independent**, otherwise every statistic measured is biased.

---

## 4. Minesweeper as a constraint problem

### 4.1 Variables and equations

At any moment, the player knows:

- the revealed cells and their numbers,
- the total number of mines $M$.

Each hidden cell $x$ is an unknown $m_x \in \{0, 1\}$. Each revealed
number $n(x)$ gives one **linear equation**:

$$
\sum_{y \in \mathcal{N}(x)\ \cap\ \text{hidden}} m_y \;=\; n(x) - \bigl|\{\text{known mines in } \mathcal{N}(x)\}\bigr|,
$$

and the total mine count gives one global equation:

$$
\sum_{y\ \text{hidden}} m_y = M - (\text{known mines}).
$$

A **constraint** is written $(S, k)$: "the set $S$ of hidden cells contains
exactly $k$ mines". A **consistent layout** is any 0/1 assignment that
satisfies every constraint.

### 4.2 Frontier and interior

- The **frontier** $F$ is the set of hidden cells that appear in at least
  one constraint (they touch a revealed number).
- The **interior** $I$ is the set of hidden cells touching no revealed
  number, with $U = |I|$.

Interior cells are interchangeable: only the global equation mentions them.

### 4.3 How hard is it?

Deciding whether a given Minesweeper position has *any* consistent layout
is **NP-complete** (Kaye, 2000). Deciding whether a particular cell is
*certainly* safe is **coNP-complete** (Scott, Stege & van Rooij, 2011). So
no known algorithm solves every position in polynomial time, and exact
methods are exponential in the worst case. This is why a solver combines
**cheap, incomplete rules first** (§5) with **exponential search only when
needed** (§6), and why the search uses heuristics to stay fast in practice.

---

## 5. Logical deduction

A cell is **provably safe** if $m_x = 0$ in *every* consistent layout, and
**provably a mine** if $m_x = 1$ in every consistent layout. The rules
below find some of these cells cheaply. Each is **sound**: it never marks a
cell incorrectly.

### 5.1 Single-constraint rules (lv1)

Take one constraint $(S, k)$ with $|S|$ hidden cells.

**Rule 1 (all mines).** If $k = |S|$, then every $m_y = 1$ for $y \in S$.

*Proof.* $\sum_{y \in S} m_y = |S|$ with each $m_y \le 1$ forces every
term to equal 1. ∎

**Rule 2 (all safe).** If $k = 0$, then every $m_y = 0$ for $y \in S$.

*Proof.* A sum of non-negative terms equal to 0 forces each term to 0. ∎

Both rules cost $O(1)$ per number, so one pass over the board is $O(N)$.

### 5.2 Subset rule (lv2)

**Theorem.** Let $(A, a)$ and $(B, b)$ be constraints with $A \subseteq B$.
Then $(B \setminus A,\ b - a)$ is also a valid constraint.

*Proof.* $\sum_{B} m = \sum_{A} m + \sum_{B \setminus A} m$, so
$\sum_{B \setminus A} m = b - a$. ∎

The new constraint may trigger Rule 1 or 2:

- $b - a = 0$ → every cell of $B \setminus A$ is safe;
- $b - a = |B \setminus A|$ → every cell of $B \setminus A$ is a mine.

lv2 applies the theorem repeatedly until no new constraint appears (a
**fixed point**). With $K$ constraints, one round compares $O(K^2)$ pairs.

**Limitation.** The subset rule only combines *nested* sets. Overlapping
constraints that are not nested, or deductions needing three or more
constraints at once, or the global mine count, can stay invisible to it.
That gap is closed by search (§6).

> **Relation to linear algebra.** The constraints form a linear system
> $A\mathbf{m} = \mathbf{b}$ over the integers with $m_y \in \{0, 1\}$.
> Subtracting nested rows is a restricted form of Gaussian elimination.
> Full elimination over the reals is not enough on its own, because the
> 0/1 restriction is what makes many deductions possible.

---

## 6. Exhaustive search: DFS over the frontier (lv3)

### 6.1 Backtracking search

To find *all* consistent assignments of the frontier, explore a binary
search tree: at each node pick an unassigned frontier cell and branch on
$m_x = 0$ and $m_x = 1$. A leaf at depth $|F|$ is a complete layout.

Without pruning the tree has $2^{|F|}$ leaves. Three techniques make it
practical.

**(a) Bound pruning.** For a constraint $(S, k)$ under a partial
assignment, let $a$ = mines already assigned in $S$ and $u$ = unassigned
cells in $S$. A consistent completion exists only if

$$
0 \le k - a \le u .
$$

If this fails, the whole subtree is cut.

**(b) Propagation.** If $k - a = 0$, all $u$ unassigned cells must be 0; if
$k - a = u$, all must be 1. Assign them immediately and repeat until nothing
changes. This is Rules 1–2 applied *inside* the search; it often fixes many
cells without branching. (In SAT solving this is called *unit propagation*.)

**(c) Variable ordering.** Branch first on the cell appearing in the most
unfinished constraints (the *most-constrained-variable* heuristic). Wrong
choices then violate a constraint sooner, so bad subtrees are cut near the
root.

### 6.2 Splitting into independent components

Build a graph on frontier cells: join two cells when some constraint
contains both. Its connected components $F_1, \dots, F_t$ share no
constraint.

**Theorem.** The set of consistent frontier layouts is the Cartesian
product of the consistent layouts of each component (ignoring the global
mine count, which §7 handles).

*Proof.* Each constraint involves cells of only one component, so a full
assignment satisfies all constraints iff each component's part satisfies
its own constraints. ∎

So instead of searching $2^{|F|}$ we search $\sum_i 2^{|F_i|}$ in the
worst case: exponentially less when the frontier splits.

### 6.3 Deduction from the search

Let $\Omega$ be the set of all consistent layouts. Then:

- if $m_x = 0$ for every $\omega \in \Omega$, **$x$ is provably safe**;
- if $m_x = 1$ for every $\omega \in \Omega$, **$x$ is provably a mine**.

This is **complete** for the frontier: every deduction that follows from the
visible numbers is found (with §7, also those that need the mine count).
The price is exponential worst-case time: on one Expert position measured
in this project, a single component had 46 cells, 32 constraints and
**34,128** consistent layouts.

---

## 7. Exact mine probabilities

### 7.1 Posterior distribution

**Theorem.** Given everything the player has seen, every *full* layout
(frontier and interior) consistent with the observations is **equally
likely**.

*Proof (Bayes).* The prior over mine sets is uniform (§3.1). The
observations (which cells are revealed, which numbers they show) are a
deterministic function of the layout and the clicks, so
$P(\text{obs} \mid \mathcal{M})$ is 1 if $\mathcal{M}$ is consistent and 0
otherwise. Hence

$$
P(\mathcal{M} \mid \text{obs}) = \frac{P(\text{obs} \mid \mathcal{M})\, P(\mathcal{M})}{P(\text{obs})} \propto \mathbf{1}[\mathcal{M}\ \text{consistent}],
$$

which is uniform over consistent layouts. (Under `SAFE`/`OPENING` the
excluded cells are already revealed, so the restricted prior changes
nothing.) ∎

### 7.2 Frontier layouts are *not* equally likely

A frontier layout $\phi$ with $|\phi| = k$ mines leaves $M' - k$ mines for
the $U$ interior cells ($M'$ = mines not yet known). Those can be placed in
$\binom{U}{M' - k}$ ways, each a distinct full layout. So, by §7.1,

$$
P(\phi) = \frac{w(\phi)}{W}, \qquad w(\phi) = \binom{U}{M' - |\phi|}, \qquad W = \sum_{\phi \in \Omega} w(\phi).
$$

**Example.** Two frontier layouts fit the numbers: $\phi_1$ with 1 mine and
$\phi_2$ with 2 mines; $M' = 3$, $U = 10$:

$$
w(\phi_1) = \binom{10}{2} = 45, \qquad w(\phi_2) = \binom{10}{1} = 10, \qquad P(\phi_1) = \tfrac{45}{55} \approx 0.82 .
$$

Counting layouts naively (1 vs 1) would give 0.5: badly wrong.

### 7.3 Probability of each cell

For a frontier cell $x$:

$$
P(m_x = 1) = \frac{1}{W} \sum_{\phi \in \Omega,\ \phi_x = 1} \binom{U}{M' - |\phi|} .
$$

For an interior cell, using $\binom{U - 1}{j - 1} = \frac{j}{U}\binom{U}{j}$:

$$
P(m_{\text{interior}} = 1) = \frac{1}{W} \sum_{\phi} \binom{U-1}{M' - |\phi| - 1} = \frac{M' - \mathbb{E}\bigl[|\phi|\bigr]}{U},
$$

the expected number of mines left for the interior, spread evenly over its
$U$ cells. All interior cells share this one value.

If some cell has probability exactly 0 or 1 it is a certain move; this
catches **endgame deductions** that only the total mine count proves.

### 7.4 Combining components efficiently (convolution)

With components $F_1, \dots, F_t$, a layout is one choice per component.
Let $c_i(k)$ = number of consistent layouts of $F_i$ with exactly $k$
mines. The number of joint frontier layouts with $k$ mines in total is the
**convolution**

$$
D = c_1 * c_2 * \dots * c_t, \qquad (f * g)(k) = \sum_{j} f(j)\, g(k - j),
$$

and

$$
W = \sum_k D(k)\binom{U}{M' - k}.
$$

For a cell $x$ in component $F_j$, let $c_j^{x}(k)$ = layouts of $F_j$
with $k$ mines **and** $m_x = 1$, and $D_{-j}$ the convolution of every
other component. Then

$$
P(m_x = 1) = \frac{1}{W}\sum_{k}\ c_j^{x}(k) \sum_{k'} D_{-j}(k') \binom{U}{M' - k - k'} .
$$

lv3 computes $D_{-j}$ with prefix and suffix convolutions, so each
component is folded in once.

> **Consequence for speed.** The formulas need only the *counts*
> $c_i(k)$ and $c_i^{x}(k)$, not the list of layouts. A search that
> accumulates these counts at the leaves uses $O(|F_i| \cdot |F_i|)$ memory
> instead of storing every layout, which removes the multi-second worst
> cases seen with stored layouts.

---

## 8. Choosing a guess: decision theory

When no cell is certain, the player must guess. The aim is to **maximise
the probability of winning the whole game**.

### 8.1 Greedy: minimum mine probability

$$
x^* = \arg\min_x P(m_x = 1).
$$

This maximises survival of the *next* click only. It is a good first
approximation but **myopic**: it ignores what the click will reveal.

### 8.2 The exact objective (game tree)

Let $V(s)$ be the probability of winning from state $s$ with optimal play.
Revealing cell $x$ either hits a mine or shows a number $v \in \{0,\dots,8\}$:

$$
V(s) = \max_{x\ \text{hidden}}\ \sum_{v=0}^{8} P(m_x = 0,\ n(x) = v \mid s)\cdot V(s \oplus (x, v)),
$$

with $V = 1$ at a won state. Each $P(\cdot)$ comes from §7 (count the
consistent layouts with $m_x = 0$ and $n(x) = v$). Solving this recursion
exactly is only feasible when few layouts remain, i.e. in the **endgame**,
where it correctly handles situations a greedy player gets wrong, for
example choosing *which* of several 50/50s to take first.

### 8.3 Information and progress (one-step lookahead)

Between greedy and full search, a solver can score each candidate by what
its revealed number is expected to teach. The outcome $v$ of revealing $x$
has entropy

$$
H(x) = -\sum_{v} P(n(x) = v \mid m_x = 0)\,\log_2 P(n(x) = v \mid m_x = 0),
$$

and the **progress** of $x$ can be measured as the expected number of new
certain cells after revealing it. A practical rule: among cells whose mine
probability is within a small margin $\varepsilon$ of the minimum, choose
the one maximising

$$
P(m_x = 0) \times P(\text{revealing } x \text{ yields a new certain move}).
$$

### 8.4 Dead cells

A hidden cell $x$ is **dead** if, in every consistent layout where it is
safe, $n(x)$ has the same value. Revealing it gives $H(x) = 0$: no
information, only risk. Unless all candidates are dead, never guess one.

### 8.5 Interior guesses and corners

An interior cell has probability $(M' - \mathbb{E}|\phi|)/U$ (§7.3), often
*below* every frontier cell early in a game. Among interior cells, those
with fewer neighbours are more likely to show 0. For a corner (3
neighbours), roughly

$$
P(n = 0 \mid \text{safe}) \approx (1 - \rho)^3
$$

versus $(1 - \rho)^8$ for an interior cell. On Expert ($\rho \approx 0.21$)
that is about $0.50$ vs $0.16$, so a safe corner opens an area about three
times as often.

### 8.6 Forced guesses

Two consistent layouts that differ only on cells whose numbers can never
distinguish them (for example two cells sharing exactly the same revealed
neighbours) force a pure 50/50. No strategy avoids it, so **no solver wins
every board**; the decision theory above only reduces how often and how
early such guesses are taken.

---

## 9. Measuring solvers: statistics

### 9.1 Win rate as a Bernoulli estimate

Each game is a Bernoulli trial with unknown win probability $p$. After $n$
games with $w$ wins, $\hat p = w/n$.

### 9.2 Wilson score interval

The batch runner reports a 95% **Wilson interval** ($z = 1.96$):

$$
\frac{\hat p + \dfrac{z^2}{2n}}{1 + \dfrac{z^2}{n}} \ \pm\ \frac{z}{1 + \dfrac{z^2}{n}}\sqrt{\frac{\hat p(1 - \hat p)}{n} + \frac{z^2}{4n^2}} .
$$

It stays inside $[0, 1]$ and behaves well when $\hat p$ is near 0 or 1,
unlike the simple $\hat p \pm z\sqrt{\hat p(1-\hat p)/n}$. Example: 5 wins
in 10 games gives $[0.237,\ 0.763]$.

Its half-width is roughly $z\sqrt{p(1-p)/n}$; for $p \approx 0.5$:

| Games $n$ | ± (95%) |
|---|---|
| 200 | ≈ 6.9 points |
| 1,000 | ≈ 3.1 points |
| 5,000 | ≈ 1.4 points |

To detect a 2–3 point improvement, use thousands of games.

### 9.3 Comparing two solvers on the same boards

Play both solvers on **the same seeds** (paired design). Count

- $b$ = boards solver A won and B lost,
- $c$ = boards B won and A lost.

Boards both win or both lose say nothing about the difference. Under "no
difference", each discordant board is equally likely to favour A or B, so
**McNemar's test** compares $b$ with $c$:

$$
\chi^2 = \frac{(b - c)^2}{b + c}\quad (1\ \text{degree of freedom}),
$$

or, for small $b + c$, an exact binomial test of $b$ out of $b + c$ with
probability $\tfrac12$. Pairing removes board-to-board luck, so it detects
real improvements with far fewer games than comparing two independent win
rates.

---

## References

- R. Kaye, "Minesweeper is NP-complete", *The Mathematical Intelligencer*
  22(2), 2000.
- A. Scott, U. Stege, I. van Rooij, "Minesweeper may not be NP-complete but
  is hard nonetheless", *The Mathematical Intelligencer* 33(4), 2011.
- E. B. Wilson, "Probable inference, the law of succession, and statistical
  inference", *Journal of the American Statistical Association* 22, 1927.
- Q. McNemar, "Note on the sampling error of the difference between
  correlated proportions or percentages", *Psychometrika* 12, 1947.
