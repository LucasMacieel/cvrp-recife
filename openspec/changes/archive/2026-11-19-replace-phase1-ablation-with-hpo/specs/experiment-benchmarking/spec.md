# Spec Delta

## ADDED Requirements

### Requirement: Multi-seed benchmark experiment execution
The system SHALL execute automated multi-seed Phase 2 experimental campaigns comparing the deterministic Greedy Baseline, Pure GA, and Memetic GA across configurable random seeds. The default Phase 2 suite SHALL consist of the three CVRPLIB tuning/benchmark instances (`A-n32-k5`, `A-n45-k6`, `A-n60-k9` — excluding `A-n80-k10`) plus the sole held-out real-world Recife/PE road-network instance (`Recife-UBS-40-road`), excluding the geodesic Haversine instance (`Recife-UBS-40-haversine`).

#### Scenario: Multi-seed campaign execution
- **WHEN** a Phase 2 experimental campaign is executed for a list of instances and `K` seeds
- **THEN** the system runs Greedy (`seed=0`), Pure GA, and Memetic GA across all `K` seeds and records for each run: instance, method, operator configuration, seed, final distance, number of vehicles used, runtime, and per-generation history

#### Scenario: Default CVRPLIB and road-only Recife/PE Phase 2 suite selection
- **WHEN** the default experimental runner loads instances for Phase 2 comparison
- **THEN** it loads `A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and `Recife-UBS-40-road`, excluding `A-n80-k10` and `Recife-UBS-40-haversine` from Phase 2 runs, summary tables, statistical tests, and analytical plots

### Requirement: Phase 1 (Bayesian HPO) to Phase 2 benchmarking workflow
The experiment runner SHALL use Bayesian hyperparameter optimization (Optuna TPE) as Phase 1 in the Phase 1 → Phase 2 campaign, replacing Phase 1 operator ablation. Users SHALL either load pre-computed Phase 1 HPO results via `--tuned-config <path>` or run Phase 1 HPO inline before Phase 2 on `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, keeping `Recife-UBS-40-road` strictly held out from Phase 1.

#### Scenario: Running Phase 2 with pre-computed Phase 1 tuned configs
- **WHEN** the experiment runner is invoked with `--tuned-config <path>` pointing to a valid `hpo_best_configs.json` file containing both `Pure_GA` and `Memetic_GA` entries
- **THEN** Phase 2 uses the loaded `Pure_GA` and `Memetic_GA` hyperparameter configurations (including each method's operators, population size, rates, tournament size, elitism, and Memetic local search parameters) with Phase 2's `--generations` and `--phase2-seeds` budgets, without re-running Phase 1 HPO or writing legacy ablation artifacts

#### Scenario: Running default inline Phase 1 HPO before Phase 2
- **WHEN** the experiment runner is invoked without `--tuned-config` (with or without `--tune`)
- **THEN** the runner executes Phase 1 (independent Optuna TPE HPO for `Pure_GA` and `Memetic_GA` on `A-n32-k5`, `A-n45-k6`, and `A-n60-k9`, defaulting to `--hpo-trials 30`, `--hpo-seeds 3`, `--hpo-generations 100`, `--hpo-seed 42`), saves Phase 1 HPO artifacts (`hpo_best_configs.json`, `hpo_trials_pure_ga.csv`, `hpo_trials_memetic_ga.csv`) to the output directory, and passes the resulting tuned configurations into Phase 2 comparison

#### Scenario: Rejecting mutually exclusive or invalid tuned configuration inputs
- **WHEN** the experiment runner is invoked with both `--tune` and `--tuned-config`, or with a `--tuned-config` file that is missing, malformed, or lacks valid `Pure_GA` and `Memetic_GA` configurations
- **THEN** the runner exits with a clear error message before starting Phase 1 HPO or Phase 2

### Requirement: Phase 1 (HPO) and Phase 2 progress reporting and summaries
The experiment runner SHALL display live progress indicators across Phase 1 (inline HPO), Phase 2 comparison, and post-processing with run/trial counts, elapsed time, ETA, active instance or method, and latest/best metrics. It SHALL render summary tables after Phase 1 HPO and Phase 2, and SHALL support suppressing live progress via `--no-progress` without altering exported artifacts.

#### Scenario: Live progress telemetry during Phase 2 runs
- **WHEN** an experimental campaign executes Phase 2 comparison with progress enabled
- **THEN** the runner updates a live progress display after each run showing the current phase, completed/total run count and percentage, elapsed time and ETA, current instance, method and operator pair, seed progress (`i/N`), and latest/best distance (plus percentage gap when the instance defines a known optimum)

#### Scenario: Post-processing progress feedback
- **WHEN** Phase 2 completes and the runner generates convergence curves, comparative boxplots, and the interactive Recife HTML map
- **THEN** the runner displays progress status for each post-processing step and prints a final completion summary indicating the output directory

#### Scenario: End-of-phase summaries
- **WHEN** Phase 1 HPO finishes and when Phase 2 finishes benchmarking
- **THEN** the runner renders readable summary tables showing tuned hyperparameters (for Phase 1 HPO) and per-instance/method summary metrics (for Phase 2)

#### Scenario: Disabling live progress output
- **WHEN** the runner is invoked with `--no-progress` on the CLI or with progress disabled programmatically
- **THEN** live progress bars and summary tables are suppressed while all exported CSV, JSON, chart, and map files are produced identically

## REMOVED Requirements

### Requirement: Multi-seed and ablation experiment execution
**Reason**: Fixed-parameter Phase 1 2×2 operator ablation (`Pure_GA` only) is redundant with Optuna TPE HPO and is removed completely from the experiment runner; `A-n80-k10` is excluded from the Phase 2 benchmark suite.
**Migration**: Use `Multi-seed benchmark experiment execution` with Phase 1 HPO-tuned configurations across `A-n32-k5`, `A-n45-k6`, `A-n60-k9`, and `Recife-UBS-40-road`.

### Requirement: Run-level experiment progress reporting and summaries
**Reason**: Legacy Phase 1 operator ablation progress bars and ablation summary tables are removed along with Phase 1 ablation execution.
**Migration**: Use `Phase 1 (HPO) and Phase 2 progress reporting and summaries` covering Phase 1 HPO, Phase 2 comparison, and post-processing.

### Requirement: Optional tuned hyperparameter integration in Phase 2 benchmarking
**Reason**: Phase 1 Bayesian HPO is no longer an optional override over a Phase 1 ablation fallback; Phase 1 (Bayesian HPO) → Phase 2 is now the sole primary workflow.
**Migration**: Use `Phase 1 (Bayesian HPO) to Phase 2 benchmarking workflow` (either omit `--tuned-config` to run Phase 1 HPO inline before Phase 2 or pass `--tuned-config <path>` to reuse saved Phase 1 HPO results).
