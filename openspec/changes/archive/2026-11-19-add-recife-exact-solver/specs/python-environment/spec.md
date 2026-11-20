## MODIFIED Requirements

### Requirement: Single-source dependency declaration in pyproject.toml
The project SHALL declare all runtime, development, and optional workflow dependencies exclusively in `pyproject.toml`, with no legacy `requirements.txt` file. Runtime dependencies MUST include `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, `rich`, and `optuna`, development dependencies MUST declare `pytest` in the `dev` dependency group, and offline exact-solver dependencies MUST be isolated in a dedicated `exact` dependency group so default runtime provisioning remains lightweight and portable.

#### Scenario: Core runtime dependencies include all directly imported packages
- **WHEN** the environment is provisioned without development or optional groups (`uv sync --no-dev`)
- **THEN** `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, `rich`, and `optuna` are all installed and importable by `src/` and `scripts/` without requiring the exact-solver group

#### Scenario: Optional exact-solver group installs reproducibly from lockfile
- **WHEN** a contributor provisions or executes with `--group exact` (for example, `uv sync --frozen --group exact` or `uv run --group exact ...`)
- **THEN** `uv` resolves and installs the locked exact-solver dependency from `uv.lock` without altering the core runtime dependency list

#### Scenario: Legacy pip manifest is absent
- **WHEN** inspecting the repository root after migration
- **THEN** `requirements.txt` does not exist and all dependency constraints reside in `pyproject.toml`

### Requirement: Standard command execution via uv run
The project SHALL support running the test suite, dataset preparation script, offline exact-solver script, and experiment runner directly through `uv run` without manual virtual environment activation, and project documentation SHALL reflect `uv sync` and `uv run` commands.

#### Scenario: Running the test suite via uv run
- **WHEN** a contributor runs `uv run pytest` from the repository root
- **THEN** the full test suite executes inside the `uv`-managed environment and passes

#### Scenario: Running project entrypoints via uv run
- **WHEN** a contributor invokes `uv run -m src.experiments.runner --help` or `uv run scripts/prepare_recife_data.py --help`
- **THEN** the command resolves imports from the repository root and displays the CLI help without requiring manual venv activation

#### Scenario: Running the offline exact-solver entrypoint via uv run
- **WHEN** a contributor invokes `uv run --group exact scripts/solve_recife_exact.py --help`
- **THEN** the command resolves imports from the repository root inside the locked environment with the `exact` group and displays the CLI help
