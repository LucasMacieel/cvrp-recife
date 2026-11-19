# Spec Delta

## ADDED Requirements

### Requirement: Run-level experiment progress reporting and summaries
The experiment runner SHALL display live run-level progress indicators across Phase 1 ablation, Phase 2 comparison, and post-processing (plots and Recife map), showing completed/total runs, percentage, elapsed time, ETA, active instance, method or operators, seed (`i/N`), and latest/best distance (with optimal gap% when known). It SHALL render concise phase summaries after Phase 1 and Phase 2, and SHALL support disabling live progress via `--no-progress` without altering exported artifacts.

#### Scenario: Live progress telemetry during Phase 1 and Phase 2 runs
- **WHEN** an experimental campaign executes Phase 1 ablation or Phase 2 comparison with progress enabled
- **THEN** the runner updates a live progress display after each run showing the current phase, completed/total run count and percentage, elapsed time and ETA, current instance, method or operator pair, seed progress (`i/N`), and latest/best distance (plus percentage gap when the instance defines a known optimum)

#### Scenario: Post-processing progress feedback
- **WHEN** Phase 2 completes and the runner generates convergence curves, comparative boxplots, and the interactive Recife HTML map
- **THEN** the runner displays progress status for each post-processing step and prints a final completion summary indicating the output directory

#### Scenario: End-of-phase summaries
- **WHEN** Phase 1 ablation finishes operator selection and when Phase 2 finishes benchmarking
- **THEN** the runner renders a readable summary table showing the selected operators (for Phase 1) and per-instance/method summary metrics (for Phase 2)

#### Scenario: Disabling live progress output
- **WHEN** the runner is invoked with `--no-progress` on the CLI or with progress disabled programmatically
- **THEN** live progress bars are suppressed while all exported CSV, JSON, chart, and map files are produced identically
