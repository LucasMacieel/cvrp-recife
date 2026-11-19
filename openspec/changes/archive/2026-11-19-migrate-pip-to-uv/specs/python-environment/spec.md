# Spec Delta

## Purpose

Defines the reproducible `uv`-managed Python environment, single-source dependency declaration, lockfile resolution, and command execution workflow for developing, testing, and running the CVRP project.

## ADDED Requirements

### Requirement: Single-source dependency declaration in pyproject.toml
The project SHALL declare all runtime and development dependencies exclusively in `pyproject.toml`, with no legacy `requirements.txt` file. Runtime dependencies MUST include `numpy`, `scipy`, `matplotlib`, `folium`, and `requests`, and development dependencies MUST declare `pytest` in the `dev` dependency group.

#### Scenario: Core runtime dependencies include all directly imported packages
- **WHEN** the environment is provisioned without development dependencies (`uv sync --no-dev`)
- **THEN** `numpy`, `scipy`, `matplotlib`, `folium`, and `requests` are all installed and importable by `src/` and `scripts/`

#### Scenario: Legacy pip manifest is absent
- **WHEN** inspecting the repository root after migration
- **THEN** `requirements.txt` does not exist and all dependency constraints reside in `pyproject.toml`

### Requirement: Deterministic dependency locking and environment sync
The project SHALL maintain a committed `uv.lock` file synchronized with `pyproject.toml` so that `uv sync --frozen` provisions a reproducible virtual environment with all runtime and `dev` group dependencies installed by default.

#### Scenario: Reproducible environment provisioning from lockfile
- **WHEN** a contributor runs `uv sync --frozen` in the repository root
- **THEN** `uv` creates or updates `.venv` using the exact versions pinned in `uv.lock` without modifying `uv.lock`, and `pytest` is available in the environment

#### Scenario: Virtual non-packaged project configuration
- **WHEN** `uv sync` runs against `pyproject.toml`
- **THEN** `uv` treats the repository as a non-packaged project (`[tool.uv] package = false`) and does not require a wheel build backend to install dependencies

### Requirement: Python version compatibility and toolchain pinning
The project SHALL declare `requires-python = ">=3.10"` in `pyproject.toml` and pin a verified default Python minor version in `.python-version` so `uv` selects a compatible interpreter automatically.

#### Scenario: Automatic interpreter selection via .python-version
- **WHEN** `uv sync` or `uv run` is executed in the repository root without an explicit `--python` override
- **THEN** `uv` resolves the Python interpreter matching `.python-version` (satisfying `>=3.10`) for `.venv`

### Requirement: Standard command execution via uv run
The project SHALL support running the test suite, dataset preparation script, and experiment runner directly through `uv run` without manual virtual environment activation, and project documentation SHALL reflect `uv sync` and `uv run` commands.

#### Scenario: Running the test suite via uv run
- **WHEN** a contributor runs `uv run pytest` from the repository root
- **THEN** the full test suite executes inside the `uv`-managed environment and passes

#### Scenario: Running project entrypoints via uv run
- **WHEN** a contributor invokes `uv run python -m src.experiments.runner --help` or `uv run python scripts/prepare_recife_data.py --help`
- **THEN** the command resolves imports from the repository root and displays the CLI help without requiring manual venv activation
