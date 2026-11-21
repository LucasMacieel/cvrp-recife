# Proposal

## Why

In `src/solver/local_search.py`, `lamarckian_two_opt` applies intra-route `2-opt` to decoded routes, flattens `improved_routes` back into a Giant Tour permutation `new_perm`, and returns the pre-concatenation route distance `new_dist` without re-evaluating `new_perm` under the greedy capacity-split decoder. Because reversing a route can move a lower-demand customer to the start of the following route, re-decoding `new_perm` can pull that customer into the preceding route and shift subsequent route boundaries, making `evaluate_giant_tour(new_perm, instance)` diverge from—and sometimes exceed—`new_dist` and even the original distance. In `src/solver/genetic.py`, storing this stale `new_dist` in `ind.fitness.values` causes `Memetic_GA` convergence histories (`Logbook` / `phase2_histories.json`) to become non-monotonic despite elitism (`elite_size >= 1`) and to disagree with the final re-decoded `SolverResult.distance` (affecting 2/30 seeds on `Recife-UBS-40-road`, 4/30 on `A-n32-k5`, and 1/30 on `A-n60-k9`).

## What Changes

- Update `lamarckian_two_opt` in `src/solver/local_search.py` to re-evaluate the flattened candidate permutation `new_perm` with the greedy capacity-split evaluator (`evaluate_giant_tour(new_perm, instance)`) before accepting a Lamarckian write-back, committing `new_perm` only when the re-decoded distance achieves a strict improvement (`redecoded_dist < orig_dist - 1e-12`) and returning the exact re-decoded distance `(new_perm, redecoded_dist)` (or `(permutation, orig_dist)` unchanged otherwise).
- Verify and enforce in `src/solver/genetic.py` that Memetic GA individual fitness values, `HallOfFame` selection, per-generation `Logbook` history, and final `decode_giant_tour(best_perm, instance)` distance remain strictly consistent, preserving monotonically non-increasing convergence history whenever `elite_size >= 1`.
- Add regression tests in `tests/test_solver.py` covering multi-route greedy-split boundary shifts during `lamarckian_two_opt` (both symmetric and asymmetric matrices), invariant checks `returned_dist == evaluate_giant_tour(returned_perm, instance) <= orig_dist`, and Memetic GA monotonic convergence plus exact `res.distance == res.history[-1]` alignment when `elite_size >= 1`.
- **Out of scope**: Re-running Phase 1 HPO / Phase 2 benchmarks to regenerate `results/`, updating `paper/main.tex` tables/text or figure styling, and replacing the greedy capacity-split decoder with an optimal Split algorithm.

## Capabilities

### New Capabilities

(None)

### Modified Capabilities

- `memetic-cvrp-solver`: Tighten the Memetic `2-opt` requirement so Lamarckian write-back evaluates the re-decoded Giant Tour distance after concatenating `2-opt`-improved routes, commits the updated permutation only on strict re-decoded improvement, and keeps fitness, convergence history, and final decoded solution distance mutually consistent (preserving monotonic best-distance history under elitism).

## Impact

- **Affected code**:
  - `src/solver/local_search.py` (`lamarckian_two_opt` re-evaluation and write-back acceptance check)
  - `src/solver/genetic.py` (audit/safeguard consistency between `_apply_local_search`, `Logbook`, `HallOfFame`, and final `decode_giant_tour` distance)
  - `tests/test_solver.py` (new deterministic and multi-route regression tests for `lamarckian_two_opt` and `Memetic_GA`)
- **Public APIs & dependencies**: No signature changes (`lamarckian_two_opt`, `GAConfig`, `solve_genetic`, `SolverResult` unchanged) and no new dependencies.
- **Behavioral note**: `Greedy` and `Pure_GA` outputs are completely unaffected. For `Memetic_GA`, exact per-seed trajectories will change on seeds where `lamarckian_two_opt` previously committed a boundary-shifted permutation with stale fitness; re-running experiments under `results/` and refreshing `paper/` is intentionally deferred outside this bug-fix change.
