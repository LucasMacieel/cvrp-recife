# Tasks

## 1. Dependencies & Environment

- [x] 1.1 Add `rich>=13.0` to `[project.dependencies]` in `pyproject.toml`, run `uv lock` and `uv sync`, and verify `uv run python -c "import rich; print(rich.__version__)"` succeeds and `uv sync --frozen` passes.

## 2. Progress Dashboard Helper Module

- [x] 2.1 Create `src/experiments/progress.py` with reusable `rich` progress bar builders (`create_experiment_progress` with spinner, description, bar, `MofNCompleteColumn`, percentage, elapsed, ETA, and live `detail` telemetry), telemetry string formatting (instance, method/operators, `seed i/N`, latest distance, best distance, and optional `gap%`), and Phase 1 / Phase 2 `rich.table.Table` summary renderers. Verify via unit tests in `tests/test_experiments.py` that formatting handles both instances with `optimal_value` (showing gap%) and without `optimal_value` (omitting gap%), and that summary tables render expected headers and rows to a captured `Console`.

## 3. Experiment Runner Integration

- [x] 3.1 Integrate `rich` run-level progress reporting into `run_phase1_ablation` and `run_phase2_comparison` in `src/experiments/runner.py`, adding backward-compatible keyword-only parameters `show_progress: bool = True` and `console: Console | None = None`, updating live detail before and after each solver run, and rendering Phase 1 and Phase 2 summary tables. Verify via tests in `tests/test_experiments.py` using a captured `Console` that progress updates and summaries include instance names, methods/operators, seed counts, and distances, and that `show_progress=False` suppresses live progress while producing identical CSV/JSON outputs.
- [x] 3.2 Update `main()` in `src/experiments/runner.py` to add the `--no-progress` CLI flag, display a `rich` progress indicator for post-processing steps (convergence curves, comparative boxplots, Recife HTML map), and print a final completion summary. Verify `uv run -m src.experiments.runner --help` lists `--no-progress` and a unit test validates CLI flag parsing and post-processing progress output.

## 4. Integration Verification

- [x] 4.1 Run the full test suite (`uv run pytest`) and a quick end-to-end smoke run of the CLI (`uv run -m src.experiments.runner --phase1-seeds 1 --phase2-seeds 1 --pop-size 10 --generations 3 --output-dir /tmp/cvrp-progress-smoke` with and without `--no-progress`) to verify all tests pass and both progress-enabled and `--no-progress` runs complete cleanly.
