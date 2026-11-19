# Proposal

## Why

The automated experiment runner (`src/experiments/runner.py`) executes hundreds of solver runs across Phase 1 operator ablation and Phase 2 multi-seed benchmarking, yet currently emits only two plain `print` messages (after Phase 1 finishes and after all post-processing finishes). Long campaigns appear frozen with no visibility into which instance, method, or seed is running, how much time remains, or what solution quality is being achieved.

## What Changes

- Add a `rich`-based live progress dashboard to the experiment runner (`src/experiments/runner.py`) with run-level progress reporting across Phase 1 ablation, Phase 2 comparison, and post-processing (plots and Recife map generation).
- Display live per-phase progress bars showing completion count and percentage, elapsed time and estimated time remaining (ETA), current instance, method/operator configuration, current seed (`i/N`), and latest/best distance (plus percentage gap to known optimum when available).
- Render compact `rich` summary tables/panels for Phase 1 selected operators and Phase 2 completion status.
- Add a `--no-progress` CLI flag (and optional `show_progress: bool = True` keyword parameter on `run_phase1_ablation` and `run_phase2_comparison`) so tests, CI, or redirected/non-interactive runs can suppress live terminal updates cleanly without changing exported CSV/JSON/plot/map artifacts.
- Add `rich` to runtime dependencies in `pyproject.toml` and update `uv.lock`.

## Capabilities

### New Capabilities

_(None)_

### Modified Capabilities

- `experiment-benchmarking`: Add live run-level progress reporting requirements for Phase 1 ablation, Phase 2 comparison, and post-processing steps, including displayed telemetry fields (phase, instance, method/operators, seed progress, elapsed/ETA, latest/best distance and gap%) and opt-out control (`--no-progress` / `show_progress=False`).
- `python-environment`: Include `rich` among the required runtime dependencies declared in `pyproject.toml` and locked in `uv.lock`.

## Impact

- **Dependencies**: Adds `rich>=13.0` to `[project.dependencies]` in `pyproject.toml` and updates `uv.lock`.
- **Code**: Modifies `src/experiments/runner.py` (and optionally adds a small focused progress helper module under `src/experiments/` if helpful); no changes to solver algorithms (`src/solver/`) or exported CSV/JSON/plot/map schemas.
- **CLI / API**: Adds `--no-progress` flag to `src/experiments/runner.py` CLI and backward-compatible keyword-only `show_progress: bool = True` parameters to `run_phase1_ablation` and `run_phase2_comparison`.
- **Tests**: Adds unit/smoke tests in `tests/test_experiments.py` verifying progress rendering output and `--no-progress` / `show_progress=False` behavior without breaking existing tests.
