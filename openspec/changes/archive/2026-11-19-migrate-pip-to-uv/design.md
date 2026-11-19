# Design

## Context

See [proposal.md](proposal.md) for motivation. Currently, the repository has:
- `pyproject.toml` declaring `requires-python = ">=3.10"`, runtime dependencies (`numpy>=1.24`, `scipy>=1.10`, `matplotlib>=3.7`, `folium>=0.14`), and `[project.optional-dependencies]` (`dev` with `pytest>=7.4`, `data` with `requests>=2.31`), with no `[build-system]` table and `[tool.pytest.ini_options]` setting `pythonpath = ["."]`.
- `requirements.txt` duplicating all six packages in a flat list for `pip install -r requirements.txt`.
- Codebase imports: `src/experiments/map_recife.py` directly imports `requests` at module top level, alongside `scripts/prepare_recife_data.py` and `tests/`.
- Local runtime: `uv 0.13.6` is installed; `.venv` runs Python 3.12.16 while the host system `python3` is 3.15.2.
- Documentation: `README.md` documents `python -m venv .venv`, `source .venv/bin/activate`, and `pip install -r requirements.txt`; `scripts/prepare_recife_data.py` docstring shows `python scripts/prepare_recife_data.py`.

## Goals / Non-Goals

**Goals:**
- Consolidate dependency declarations into `pyproject.toml` with a committed `uv.lock` for deterministic installs.
- Make `uv sync` and `uv run` work out-of-the-box for tests, dataset scripts, and experiment runs without manual `.venv` activation.
- Keep `src/` module resolution (`python -m src.experiments.runner` and `pytest` with `pythonpath = ["."]`) unchanged.

**Non-Goals:**
- Packaging or publishing the repository as a distributable wheel/sdist on PyPI.
- Adding new linters, formatters, type checkers, or CI/CD pipelines.
- Modifying any solver, data-loading, or experiment logic.

## Decisions

### 1. Keep as a non-packaged virtual project (`[tool.uv] package = false`)
- **Decision**: Explicitly set `[tool.uv] package = false` in `pyproject.toml` and do not add a `[build-system]`.
- **Rationale**: The repo is a research/course project imported from the repo root (`src.*` and `scripts.*`). Setting `package = false` makes `uv`'s virtual-project behavior explicit and avoids requiring a build backend (such as `hatchling`) or restructuring `src/` into an installable package layout.
- **Alternative considered**: Adding `[build-system]` with `hatchling` and installing `src` as a package. Rejected because `src` is not a namespaced package name suitable for site-packages installation and `pyproject.toml` already configures `pythonpath = ["."]` for `pytest`.

### 2. Move `pytest` to PEP 735 `[dependency-groups]` (`dev`)
- **Decision**: Replace `[project.optional-dependencies].dev` with `[dependency-groups] dev = ["pytest>=7.4"]`.
- **Rationale**: `uv sync` installs the `dev` dependency group by default, whereas `[project.optional-dependencies]` requires passing `--extra dev`. Using PEP 735 `[dependency-groups]` is the standard `uv` convention and ensures `uv sync && uv run pytest` works with zero extra flags.
- **Alternative considered**: Keeping `[project.optional-dependencies].dev`. Rejected because `uv sync` would omit `pytest` by default.

### 3. Promote `requests>=2.31` to `[project].dependencies`
- **Decision**: Move `requests>=2.31` into `[project].dependencies` and remove `[project.optional-dependencies].data`.
- **Rationale**: `src/experiments/map_recife.py` directly imports `requests` at module import time. Keeping it only in an optional `data` extra relied on `folium` pulling `requests` transitively. Making it a direct runtime dependency ensures `uv sync --no-dev` always satisfies all `src/` and `scripts/` imports explicitly.
- **Alternative considered**: Keeping `[project.optional-dependencies].data` and requiring `uv sync --extra data`. Rejected because `requests` is required by the core experiment runner's map generation step, not only optional data prep.

### 4. Pin `.python-version` to `3.12` while keeping `requires-python = ">=3.10"`
- **Decision**: Add `.python-version` containing `3.12` and keep `requires-python = ">=3.10"` in `pyproject.toml`.
- **Rationale**: The existing verified `.venv` runs Python 3.12, whereas host environments may have very new or pre-release Python versions (e.g., 3.15) that lack prebuilt wheels for `numpy`/`scipy`. Pinning `.python-version` to `3.12` gives `uv` a stable, wheel-backed default while still permitting Python 3.10+ for users who override `--python`.
- **Alternative considered**: Omitting `.python-version`. Rejected because `uv` could pick an unsupported host Python (like 3.15) during `uv sync` and fail building scientific wheels from source.

### 5. Remove `requirements.txt`
- **Decision**: Delete `requirements.txt` after generating `uv.lock`.
- **Rationale**: Maintaining both `requirements.txt` and `pyproject.toml`/`uv.lock` reintroduces drift. Removing `requirements.txt` establishes a single source of truth.
- **Alternative considered**: Keeping `requirements.txt` exported via `uv export`. Rejected because no deployment target or CI workflow in this repository requires `requirements.txt`.

## Risks / Trade-offs

- **[Breaking pip-based instructions]** Contributors used to `pip install -r requirements.txt` will find `requirements.txt` removed → **Mitigation**: Update `README.md` with clear `uv` installation/sync/run commands (and note `uv` prerequisite).
- **[Lockfile resolution across Python versions]** `uv.lock` resolves across `requires-python = ">=3.10"`, which may constrain some package upper/lower bounds across Python 3.10–3.14 → **Mitigation**: Run `uv lock` and `uv sync --frozen`, then verify with `uv run pytest` and entrypoint checks during implementation.
- **[Existing `.venv` replacement]** Re-syncing `.venv` with `uv sync` will replace packages previously installed by `pip` → **Mitigation**: `uv sync` cleanly manages `.venv`; `.venv/` is already gitignored.

## Migration Plan

1. Update `pyproject.toml` (`requests>=2.31` in `dependencies`, `[dependency-groups].dev`, `[tool.uv] package = false`, remove `[project.optional-dependencies]`).
2. Create `.python-version` with `3.12`.
3. Run `uv lock` and `uv sync` to generate `uv.lock` and provision `.venv`.
4. Delete `requirements.txt`.
5. Update `README.md` and `scripts/prepare_recife_data.py` usage comments.
6. Verify with `uv sync --frozen`, `uv run pytest`, `uv run python -m src.experiments.runner --help`, and `uv run python scripts/prepare_recife_data.py --help`.
7. **Rollback**: Restore `requirements.txt`, revert `pyproject.toml` and docs, and remove `uv.lock` and `.python-version` via `git checkout`.
