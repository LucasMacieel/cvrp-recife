# Proposal

## Why

The project currently manages dependencies through a dual-source setup (`requirements.txt` for `pip` alongside `pyproject.toml`) without a lockfile, which risks dependency drift across machines and leaves `requests` missing from core `[project].dependencies` even though `src/experiments/map_recife.py` imports it directly. Migrating to `uv` consolidates dependency management into `pyproject.toml` + `uv.lock`, delivers fast and reproducible environment setup, and aligns development workflows with modern Python packaging standards.

## What Changes

- **Migrate dependency and environment management to `uv`**:
  - Update `pyproject.toml` to declare `requests>=2.31` as a core runtime dependency (removing the redundant `[project.optional-dependencies].data` extra).
  - Move `pytest>=7.4` from `[project.optional-dependencies].dev` to PEP 735 `[dependency-groups]` (`dev`) so `uv sync` installs test tooling by default.
  - Explicitly mark the project as a non-packaged virtual project (`[tool.uv] package = false`) to preserve the existing `src/` module layout and `python -m src.experiments.runner` invocation.
- **Pin Python toolchain version and lock dependencies**:
  - Add `.python-version` (pinned to `3.12`, matching the current verified `.venv` runtime) while keeping `requires-python = ">=3.10"`.
  - Generate and commit `uv.lock` for deterministic, cross-machine dependency resolution.
- **Remove legacy `pip` manifest** (**BREAKING** for workflows invoking `pip install -r requirements.txt`):
  - Delete `requirements.txt` so `pyproject.toml` and `uv.lock` serve as the single source of truth.
- **Update documentation and script usage hints**:
  - Update `README.md` installation and execution commands from `python -m venv` / `pip install -r requirements.txt` to `uv sync` and `uv run`.
  - Update the usage docstring in `scripts/prepare_recife_data.py` to reference `uv run`.

## Capabilities

### New Capabilities

- `python-environment`: Defines the `uv`-managed Python environment, single-source dependency declaration in `pyproject.toml`, deterministic lockfile (`uv.lock`), Python version pinning, and standard `uv sync` / `uv run` execution workflow.

### Modified Capabilities

<!-- None: solver, data loading, and experiment benchmarking behaviors are unchanged. -->

## Impact

- **Configuration & Lockfile**: `pyproject.toml` (modified), `.python-version` (added), `uv.lock` (added), `requirements.txt` (removed).
- **Documentation & Scripts**: `README.md` (modified), `scripts/prepare_recife_data.py` (docstring updated).
- **Runtime & Tests**: No changes to solver logic, data loaders, experiment runner, or test assertions; all existing tests (`tests/`) will run via `uv run pytest`.
- **Developer Workflow**: Contributors must have `uv` installed and use `uv sync` / `uv run` instead of `venv` + `pip install -r requirements.txt`.
