# Tasks

## 1. Configure `uv` Project Metadata & Toolchain

- [x] 1.1 Update `pyproject.toml` to add `requests>=2.31` to `[project].dependencies`, replace `[project.optional-dependencies]` with `[dependency-groups]` containing `dev = ["pytest>=7.4"]`, and add `[tool.uv]` with `package = false`; verify the TOML parses cleanly with `python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"`.
- [x] 1.2 Create `.python-version` pinned to `3.12` and verify `uv python find` resolves a Python 3.12 interpreter in the repository root.

## 2. Generate Lockfile, Sync Environment & Remove Legacy `pip` Manifest

- [x] 2.1 Run `uv lock` and `uv sync` to generate `uv.lock` and provision `.venv`; verify `uv.lock` exists and `uv sync --frozen` succeeds without modifying `uv.lock`.
- [x] 2.2 Remove `requirements.txt` and verify `requirements.txt` is absent while all core runtime packages (`numpy`, `scipy`, `matplotlib`, `folium`, `requests`) import cleanly under `uv run --no-dev python -c "import numpy, scipy, matplotlib, folium, requests"`.

## 3. Update Documentation & Usage References

- [x] 3.1 Update `README.md` installation and running sections to use `uv sync`, `uv run pytest`, `uv run python scripts/prepare_recife_data.py`, and `uv run python -m src.experiments.runner` (removing `venv` and `pip install -r requirements.txt` instructions), and verify each documented help/test command runs as written.
- [x] 3.2 Update the usage docstring in `scripts/prepare_recife_data.py` to reference `uv run python scripts/prepare_recife_data.py` and verify `uv run python scripts/prepare_recife_data.py --help` exits 0.

## 4. End-to-End Verification

- [x] 4.1 Run `uv sync --frozen` followed by `uv run pytest` and `uv run python -m src.experiments.runner --help` from the repository root; verify all tests pass and no legacy `requirements.txt` or `pip` setup references remain in `README.md` or `scripts/`.
