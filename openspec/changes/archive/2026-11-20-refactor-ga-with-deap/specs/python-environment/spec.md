# Spec Delta

## MODIFIED Requirements

### Requirement: Single-source dependency declaration in pyproject.toml
The project SHALL declare all runtime, development, and optional workflow dependencies exclusively in `pyproject.toml`, with no legacy `requirements.txt` file. Runtime dependencies MUST include `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, `rich`, `optuna`, and `deap`, development dependencies MUST declare `pytest` in the `dev` dependency group, and offline exact-solver dependencies MUST be isolated in a dedicated `exact` dependency group so default runtime provisioning remains lightweight and portable.

#### Scenario: Core runtime dependencies include all directly imported packages
- **WHEN** the environment is provisioned without development or optional groups (`uv sync --no-dev`)
- **THEN** `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, `rich`, `optuna`, and `deap` are all installed and importable by `src/` and `scripts/` without requiring the exact-solver group

#### Scenario: Optional exact-solver group installs reproducibly from lockfile
- **WHEN** a contributor provisions or executes with `--group exact` (for example, `uv sync --frozen --group exact` or `uv run --group exact ...`)
- **THEN** `uv` resolves and installs the locked exact-solver dependency from `uv.lock` without altering the core runtime dependency list

#### Scenario: Legacy pip manifest is absent
- **WHEN** inspecting the repository root after migration
- **THEN** `requirements.txt` does not exist and all dependency constraints reside in `pyproject.toml`
