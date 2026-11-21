# Design

## Context

See `proposal.md` for motivation and empirical impact.

In the current solver pipeline:
- `src/solver/decoder.py` defines the Giant Tour greedy capacity-split decoder (`decode_giant_tour`) and its allocation-free distance evaluator (`evaluate_giant_tour`).
- `src/solver/local_search.py` implements `lamarckian_two_opt(permutation, instance, ...)`, which decodes `permutation` into `routes`, applies intra-route `2-opt` via `two_opt_solution`, flattens `improved_routes` into `new_perm`, and returns `(new_perm, new_dist)` whenever `new_dist < orig_dist - 1e-12`—where `new_dist` is the distance of `improved_routes` prior to re-decoding `new_perm`.
- `src/solver/genetic.py` wraps `lamarckian_two_opt` inside `_apply_local_search(ind)` and assigns the returned `dist` directly to `ind.fitness.values`, which feeds DEAP's tournament selection, `selBest` elitism, `HallOfFame`, and `Logbook` history, while the final return value recomputes `best_routes, best_dist = decode_giant_tour(best_perm, instance)`.

Because `2-opt` reverses intra-route segments, a lower-demand customer can move to the front of route $r + 1$ and fit into the remaining capacity of route $r$ when `new_perm` is later re-decoded by greedy split. That boundary shift breaks the invariant `returned_dist == evaluate_giant_tour(returned_perm, instance)`.

## Goals / Non-Goals

**Goals:**
- Guarantee the invariant that `lamarckian_two_opt` always returns `(perm, dist)` where `dist` matches the greedy capacity-split decoded distance of `perm` and `dist <= orig_dist`.
- Commit Lamarckian write-back only on a strict re-decoded improvement (`redecoded_dist < orig_dist - 1e-12`).
- Guarantee exact consistency in `solve_genetic` between DEAP `ind.fitness.values`, `HallOfFame`, `Logbook` (`history`), and final `SolverResult.distance` / `SolverResult.routes`, restoring monotonically non-increasing `history` whenever `elite_size >= 1`.

**Non-Goals:**
- Changing the Giant Tour chromosome encoding or introducing a dual route-list genotype.
- Replacing the greedy capacity-split decoder with Prins' optimal `Split` algorithm.
- Regenerating `results/` artifacts or modifying `paper/main.tex`.

## Decisions

### 1. Re-evaluate the flattened permutation inside `lamarckian_two_opt` with `evaluate_giant_tour`

In `src/solver/local_search.py`, after `two_opt_solution` finds `new_dist < orig_dist - 1e-12` and constructs `new_perm`, compute:
```python
redecoded_dist = evaluate_giant_tour(new_perm, instance)
if redecoded_dist < orig_dist - 1e-12:
    return new_perm, redecoded_dist
```
Otherwise return `(permutation, orig_dist)`.

**Rationale:**
- `evaluate_giant_tour` executes the exact greedy capacity-split traversal in $O(n)$ with zero intermediate route allocations and matches `toolbox.evaluate` in `src/solver/genetic.py`.
- If a greedy-split boundary shift still leaves `redecoded_dist < orig_dist - 1e-12`, the improvement is kept **with its true re-decoded distance** rather than the phantom pre-concatenation `new_dist`.
- If the boundary shift cancels or reverses the `2-opt` gain (`redecoded_dist >= orig_dist - 1e-12`), the candidate permutation is rejected and the original `(permutation, orig_dist)` is preserved untouched.

**Alternatives considered:**
- *Store explicit route partitions on DEAP individuals (hybrid genotype)*: Would avoid re-decoding mismatches after `2-opt`, but requires changing crossover/mutation semantics, `HallOfFame`/`SolverResult` interfaces, and deviates from the Giant Tour representation specified in `memetic-cvrp-solver`.
- *Restrict `2-opt` to moves that preserve greedy-split boundaries*: Complicates `two_opt_route` with demand-aware lookahead into adjacent routes and rejects beneficial boundary shifts that actually reduce total distance.

### 2. Keep `_apply_local_search` and elitism flow in `src/solver/genetic.py` aligned via the invariant

Once `lamarckian_two_opt` enforces `returned_dist == evaluate_giant_tour(returned_perm, instance)` and `returned_dist <= orig_dist`:
- `_apply_local_search(ind)` sets `ind[:]` and `ind.fitness.values = (dist,)` to mutually consistent, non-regressing values.
- Running `_apply_local_search(best_ind)` at generation 0 and at the end of each generation after `population[:] = elites + offspring` can only preserve or strictly lower `min(population)` (no stale fitness overwrite on re-decoding in the next generation).
- `HallOfFame(1)` ranks individuals by their true greedy-split distance, so `decode_giant_tour(best_perm, instance)` at the end of `solve_genetic` matches `history[-1]` (when `elite_size >= 1`) and `min(history)` (for any `elite_size >= 0`) within floating-point tolerance (`1e-12`).

**Floating-point precision note:** `decode_giant_tour` sums per-route totals (`total_distance`) while `evaluate_giant_tour` accumulates edges in a single scalar loop, so they can differ by at most a few float64 ULPs ($\sim 10^{-14}$), two orders of magnitude below the strict-improvement threshold (`1e-12`). No behavioral drift occurs at `1e-12`.

## Risks / Trade-offs

- **[Slight per-call overhead in `lamarckian_two_opt`]** → Only triggered when `new_dist < orig_dist - 1e-12`, and `evaluate_giant_tour` is $O(n)$ without allocations—negligible compared to $O(m^2 \cdot M_{LS})$ `2-opt` search.
- **[Boundary-shifted `2-opt` moves whose re-decoded cost worsens are discarded]** → Inherent to Giant Tour + greedy Split decoding; rejecting them prevents deceptive fitness inflation and guarantees every written-back chromosome genuinely improves under the actual decoder.
- **[Changed per-seed `Memetic_GA` trajectories vs. existing `results/`]** → Existing `results/` files reflect the pre-fix buggy behavior on affected seeds; regenerating `results/` and updating `paper/main.tex` are kept out of scope for this bug-fix change and can be run separately after applying this fix.
