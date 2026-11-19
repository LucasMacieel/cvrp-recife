# Design

## Context

See `proposal.md` for motivation. Currently, `src/experiments/runner.py` runs:
- Phase 1 (`run_phase1_ablation`): `len(instances) * 4 * len(seeds)` calls to `solve_genetic`.
- Phase 2 (`run_phase2_comparison`): per instance, 1 `solve_greedy` call + `2 * len(seeds)` calls to `solve_genetic` (total `len(instances) * (1 + 2 * len(seeds))` runs).
- Post-processing (`main`): convergence plots, comparative boxplots, and interactive Recife HTML map generation.

None of these loops report intermediate progress. Tests in `tests/test_experiments.py` call `run_phase1_ablation` and `run_phase2_comparison` directly with `tmp_path` and assert on returned rows/histories and written files.

## Goals / Non-Goals

**Goals:**
- Provide an informative, low-overhead `rich` live progress dashboard for Phase 1, Phase 2, and post-processing.
- Show exact run-level telemetry: phase label, completed/total runs, percentage, elapsed time, ETA, current instance, method/operator pair, seed index (`i/N`), latest distance, best distance so far (for the active instance/config), and percentage gap to known optimum when `instance.optimal_value` is available.
- Print compact `rich` summary tables after Phase 1 (operator ablation ranking & selected pair) and Phase 2 (per-instance/method mean, best distance, gap%, and runtime).
- Support disabling live progress cleanly via `--no-progress` CLI flag and optional `show_progress: bool = True` / `console: Console | None = None` parameters without breaking existing callers or altering output files.

**Non-Goals:**
- Generation-level progress bars inside `src/solver/genetic.py` (no solver API changes or per-generation callback overhead).
- Parallel / multi-process execution of seeds or instances.
- Changing any exported CSV, JSON, PNG, or HTML output schema or file paths.

## Decisions

### 1. Use `rich` (`rich.progress.Progress`, `rich.table.Table`, `rich.console.Console`)
- **Decision**: Add `rich>=13.0` to `pyproject.toml` (`[project.dependencies]`) and lock it in `uv.lock`.
- **Rationale**: `rich` natively supports multi-column progress displays, custom status fields (`task.fields`), elapsed/ETA columns, clean non-TTY fallback, injectable `Console(file=StringIO(), ...)` for deterministic unit testing, and formatted summary tables without hand-rolled ANSI escape codes.
- **Alternatives considered**:
  - `tqdm`: Simpler single-line bar, but less structured for multi-field telemetry and summary tables.
  - Stdlib ANSI output: Zero dependencies, but fragile across terminal widths, redirected pipes, and lacks rich table formatting.

### 2. Encapsulate progress rendering in a focused helper module (`src/experiments/progress.py`)
- **Decision**: Place `Progress` column builders, telemetry formatting helpers (distance + optional gap%), and Phase 1 / Phase 2 summary table renderers in `src/experiments/progress.py`, keeping `src/experiments/runner.py` focused on orchestration.
- **Rationale**: Separates UI/formatting concerns from experiment logic, makes formatting functions independently unit-testable, and keeps `runner.py` concise and readable.
- **Alternatives considered**:
  - Inline all `rich` widgets directly in `runner.py`: Increases clutter in `runner.py` and makes isolated testing of formatting harder.

### 3. Per-phase `Progress` bars with structured live status fields
- **Decision**: Use a `Progress` instance per phase (or shared context with distinct tasks) displaying:
  - `SpinnerColumn()`
  - `TextColumn("[bold blue]{task.description}")` (e.g., `Phase 1: Ablation`, `Phase 2: Comparison`, `Post-processing`)
  - `BarColumn()`
  - `MofNCompleteColumn()` + `TaskProgressColumn()` (`completed/total`, `XX%`)
  - `TimeElapsedColumn()` + `TimeRemainingColumn()` (elapsed & ETA)
  - A secondary status line or `TextColumn("{task.fields[detail]}")` showing: `inst=<name> | <method/ops> | seed <i>/<N> | last=<dist> | best=<dist> (<gap>%)`.
- **Rationale**: Keeps the progress bar width stable while giving rich per-run context. Updating `detail` before starting a run (showing active instance/method/seed) and after finishing a run (updating `last`, `best`, `gap`, and advancing by 1) ensures the user immediately sees what is currently executing even if a single Memetic GA run takes several seconds.
- **Alternatives considered**:
  - Updating only after each run finishes: Leaves the user unsure which instance/seed is currently running during a slow Memetic GA seed.

### 4. Opt-out and testability via `show_progress` and `console`
- **Decision**: Add keyword-only `show_progress: bool = True` and `console: Console | None = None` to `run_phase1_ablation` and `run_phase2_comparison`, and `--no-progress` to `runner.py`'s `argparse` CLI. Pass `disable=not show_progress` to `rich.progress.Progress`.
- **Rationale**: Fully backward-compatible with existing call sites; allows tests to pass a recording `Console(file=StringIO(), force_terminal=False, width=160)` to assert on rendered telemetry and summary tables, and allows CI/scripts to silence live progress via `--no-progress`.

## Risks / Trade-offs

- **Wide status strings wrapping on narrow terminals** → Use concise abbreviations (`inst`, `seed i/N`, `last`, `best`, `gap`) and let `rich` handle terminal width gracefully; put the detail string in a dedicated column or second task line so the bar never collapses.
- **ETA inaccuracy between Pure GA and Memetic GA in Phase 2** → Memetic GA runs significantly slower than Greedy and Pure GA, so `TimeRemainingColumn`'s rolling speed estimate may jump when transitioning from Pure GA to Memetic GA. Showing per-phase progress with active method/instance context makes this transparent; keeping run-level granularity avoids overcomplicating ETA weighting.
- **Extra runtime dependency (`rich`)** → `rich` is pure Python, lightweight, widely maintained, and locked via `uv.lock` for deterministic installs.
