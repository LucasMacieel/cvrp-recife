# Tasks

## 1. Lamarckian 2-opt Re-evaluation Fix

- [x] 1.1 Import `evaluate_giant_tour` in `src/solver/local_search.py` and update `lamarckian_two_opt` so that after constructing `new_perm` from `improved_routes`, it computes `redecoded_dist = evaluate_giant_tour(new_perm, instance)` and returns `(new_perm, redecoded_dist)` only when `redecoded_dist < orig_dist - 1e-12` (otherwise returning `(permutation, orig_dist)` untouched); update the docstring to document greedy-split re-evaluation and verify with `uv run pytest tests/test_solver.py -k two_opt`.
- [x] 1.2 Add unit and regression tests in `tests/test_solver.py` for `lamarckian_two_opt` covering: (a) a constructed multi-route instance where `2-opt` shifts greedy-split boundaries upon concatenation and increases re-decoded cost (asserting the original permutation and `orig_dist` are preserved), (b) a multi-route case where boundary shift still yields a strict re-decoded improvement (asserting the returned distance equals `evaluate_giant_tour(new_perm, instance)` rather than the pre-concatenation `two_opt_solution` distance), and (c) randomized multi-route probes on both `A-n32-k5` (symmetric) and `Recife-UBS-40-road` (asymmetric) asserting `np.isclose(d_after, evaluate_giant_tour(new_perm, inst), atol=1e-12)` and `d_after <= d_before + 1e-12`; verify `uv run pytest tests/test_solver.py -k two_opt` passes.

## 2. Memetic GA Consistency & Elitist Monotonicity Verification

- [x] 2.1 Audit `_apply_local_search` and the generational loop in `src/solver/genetic.py` to confirm DEAP individual fitness, `HallOfFame`, `Logbook` history, and final `decode_giant_tour(best_perm, instance)` stay strictly aligned (making no unnecessary edits if the `lamarckian_two_opt` invariant suffices), and expand `tests/test_solver.py` to test `solve_genetic(..., memetic=True)` across symmetric (`A-n32-k5`) and asymmetric (`Recife-UBS-40-road`, including previously affected seeds `1` and `13`) instances—asserting monotonically non-increasing `res.history` whenever `elite_size >= 1`, `np.isclose(res.distance, res.history[-1], atol=1e-12)`, `np.isclose(res.distance, evaluate_giant_tour(res.permutation, inst), atol=1e-12)`, and `res.distance <= min(res.history) + 1e-12` when `elite_size == 0`; verify `uv run pytest tests/test_solver.py` passes.

## 3. Full Test Suite & Regression Integration Check

- [x] 3.1 Run the full test suite (`uv run pytest`) and confirm all unit and integration tests pass with zero failures or warnings, and confirm via `git status` that only solver code and tests were modified (no unintended changes to `results/` or `paper/`).
