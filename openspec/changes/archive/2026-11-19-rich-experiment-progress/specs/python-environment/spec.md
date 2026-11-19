# Spec Delta

## MODIFIED Requirements

### Requirement: Single-source dependency declaration in pyproject.toml
The project SHALL declare all runtime and development dependencies exclusively in `pyproject.toml`, with no legacy `requirements.txt` file. Runtime dependencies MUST include `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, and `rich`, and development dependencies MUST declare `pytest` in the `dev` dependency group.

#### Scenario: Core runtime dependencies include all directly imported packages
- **WHEN** the environment is provisioned without development dependencies (`uv sync --no-dev`)
- **THEN** `numpy`, `scipy`, `matplotlib`, `folium`, `requests`, and `rich` are all installed and importable by `src/` and `scripts/`

#### Scenario: Legacy pip manifest is absent
- **WHEN** inspecting the repository root after migration
- **THEN** `requirements.txt` does not exist and all dependency constraints reside in `pyproject.toml`
