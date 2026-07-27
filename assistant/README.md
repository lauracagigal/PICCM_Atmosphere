# CIndRA Assistant — Training Material (PICCM Atmosphere)

This folder holds the instructions used to train an external assistant — **CIndRA** (Climate Indicator Research Assistant) — e.g. as a ChatGPT custom GPT. CIndRA is the single assistant for the whole [PICCM_Atmosphere](https://github.com/lauracagigal/PICCM_Atmosphere) repository: **both** the rainfall notebooks (`notebooks/historical/rainfall/`) and the air-temperature notebooks (`notebooks/historical/air_temperature/`), plus the site-setup notebook they share.

## How to use

- **`CIndRA_role.md`** — paste the contents into the "Instructions" / system prompt of the assistant. Defines CIndRA's identity, scope (rainfall + air temperature), conventions, data sources, analysis rules, plotting rules, output naming, and error handling for both domains.
- **`aggregated_CIndRA_markdowns.md`** — single file with **all** markdowns below concatenated (role + skills + this README). Use when the assistant platform accepts one large knowledge file instead of separate uploads. Regenerate after any source change: `python assistant/build_aggregated_CIndRA.py`.
- **`skills/`** — modular workflow-specific instructions. Attach each file as a separate knowledge document, or use `aggregated_CIndRA_markdowns.md` for a single upload:

| File | Notebook / scope |
|---|---|
| `site_setup.md` | `notebooks/historical/00_site_setup.ipynb` — shared entry point for both domains; not under `rainfall/` or `air_temperature/` |
| `total_rainfall.md` | `rainfall/a_Total_rainfall.ipynb` |
| `consecutive_dry_days.md` | `rainfall/b_Consecutive_dry_days.ipynb` |
| `heavy_rainfall.md` | `rainfall/c_Heavy_rainfall.ipynb` |
| `mean_temperature.md` | `air_temperature/a_mean_temperature.ipynb` |
| `min_max_temperature.md` | `air_temperature/b_min_max_temperature.ipynb` |
| `hot_cold_days.md` | `air_temperature/c_hot_cold_days.ipynb` |
| `functions_api.md` | Callable functions (both domains), `indicators_setup` discovery, `plot_bar_probs` |
| `output_conventions.md` | Figure / table naming and folders (both domains) |
| `data_sources.md` | GHCN-Daily, ONI, units, citations (both domains) |

## Repository quick map

- `notebooks/historical/00_site_setup.ipynb` — single shared entry point; run before anything under `rainfall/` or `air_temperature/`.
- `notebooks/historical/rainfall/` (`a_Total_rainfall.ipynb`, `b_Consecutive_dry_days.ipynb`, `c_Heavy_rainfall.ipynb`) and `notebooks/historical/air_temperature/` (`a_mean_temperature.ipynb`, `b_min_max_temperature.ipynb`, `c_hot_cold_days.ipynb`) — the two indicator-specific analysis folders, both in CIndRA's scope. Both use bare `a_`/`b_`/`c_` filename prefixes but live in different folders — disambiguate by folder or full filename, not by the bare letter.
- `functions/` — `rainfall.py` and `air_temp.py` (near-identical site-config API: `save_site_config`, `load_site_config`, `site_config_filename`, `list_available_sites`, `build_site_tag`, ...) plus `temp_func.py` (ETCCDI percentile helpers) and `data_downloaders.py` (GHCN, ONI, completeness filter).
- `data/rainfall/` — cached per-station GHCN pickles for `PRCP` (`GHCN_<station_id>.pkl`) and optional ONI cache.
- `data/air_temp/` — cached per-station GHCN pickles for `TMIN`/`TMAX`.
- `data/sites/` — per-site config JSON files, shared between both workflows. `site_name`/`site_key` is `<country_slug>_<ghcn_station_id>`.
- `outputs/figures/<site_tag>/` — per-site figure outputs (PNG / HTML).
- `outputs/tables/<site_tag>/` — per-site CSV tables and JSON metrics.

## Updating the assistant

- When you add or rename a function in `functions/` or change `indicators_setup` usage, update `skills/functions_api.md` and the **Functions API** section of `CIndRA_role.md` in the same PR.
- When you introduce a new persisted artifact (figure / CSV / JSON), document it in `skills/output_conventions.md`.
- When a new analysis notebook is added, mirror its workflow in a new `skills/<name>.md`, extend `CIndRA_role.md`, and add the file to `SOURCE_FILES` in `build_aggregated_CIndRA.py`.
- After editing any markdown in `assistant/` or `assistant/skills/`, run `python assistant/build_aggregated_CIndRA.py` to refresh `aggregated_CIndRA_markdowns.md`.
