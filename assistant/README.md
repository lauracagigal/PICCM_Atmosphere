# CIndRA Assistant — Training Material (PICCM Rainfall)

This folder holds the instructions used to train an external assistant — **CIndRA** (Climate Indicator Research Assistant) — e.g. as a ChatGPT custom GPT. The current skill set specializes CIndRA in the rainfall side of the [PICCM_Atmosphere](https://github.com/lauracagigal/PICCM_Atmosphere) repository, which also hosts the air-temperature workflow (CIRA's specialization, see `CIRA_role.md`). The two share the site-setup notebook and the `data/sites/` config store — `site_setup.md` below documents that shared skill.

## How to use

- **`CIndRA_role.md`** — paste the contents into the "Instructions" / system prompt of the assistant. Defines CIndRA's identity, scope, conventions, data sources, analysis rules, plotting rules, output naming, and error handling.
- **`aggregated_CIndRA_markdowns.md`** — single file with **all** markdowns below concatenated (role + skills + this README). Use when the assistant platform accepts one large knowledge file instead of separate uploads. Regenerate after any source change: `python assistant/build_aggregated_CIndRA.py`.
- **`skills/`** — modular workflow-specific instructions. Attach each file as a separate knowledge document, or use `aggregated_CIndRA_markdowns.md` for a single upload:

| File | Notebook / scope |
|---|---|
| `site_setup.md` | `notebooks/historical/00_site_setup.ipynb` — **shared** with the air-temperature assistant (CIRA); not under `rainfall/` |
| `total_rainfall.md` | `00a_Total_rainfall.ipynb` |
| `consecutive_dry_days.md` | `00b_Consecutive_dry_days.ipynb` |
| `heavy_rainfall.md` | `00c_Heavy_rainfall.ipynb` |
| `functions_api.md` | Callable functions, `indicators_setup` discovery, `plot_bar_probs` |
| `output_conventions.md` | Figure / table naming and folders |
| `data_sources.md` | GHCN-Daily, ONI, units, citations |

## Repository quick map

- `notebooks/historical/00_site_setup.ipynb` — single shared entry point; run before anything under `rainfall/` or `air_temperature/`.
- `notebooks/historical/rainfall/` (`00a`, `00b`, `00c`) and `notebooks/historical/air_temperature/` (`a`, `b`, `c`) — the two indicator-specific analysis folders. Air temperature is CIRA's specialization (see `CIRA_role.md`); this assistant folder trains CIndRA on the rainfall side only.
- `functions/` — `rainfall.py` (site config, dry-spell metrics, output paths) and `data_downloaders.py` (GHCN, ONI, completeness filter). `air_temp.py` has an equivalent site-config API used by CIRA.
- `data/rainfall/` — cached per-station GHCN pickles (`GHCN_<station_id>.pkl`) and optional ONI cache.
- `data/air_temp/` — cached per-station GHCN pickles for `TMIN`/`TMAX` (written by the shared `00_site_setup.ipynb`, consumed by CIRA's notebooks).
- `data/sites/` — per-site config JSON files, shared between both workflows. `site_name`/`site_key` is `<country_slug>_<ghcn_station_id>`.
- `outputs/figures/<site_tag>/` — per-site figure outputs (PNG / HTML).
- `outputs/tables/<site_tag>/` — per-site CSV tables and JSON metrics.

## Updating the assistant

- When you add or rename a function in `functions/` or change `indicators_setup` usage, update `skills/functions_api.md` and the **Functions API** section of `CIndRA_role.md` in the same PR.
- When you introduce a new persisted artifact (figure / CSV / JSON), document it in `skills/output_conventions.md`.
- When a new analysis notebook is added, mirror its workflow in a new `skills/<name>.md` and extend `CIndRA_role.md`.
- After editing any markdown in `assistant/` or `assistant/skills/`, run `python assistant/build_aggregated_CIndRA.py` to refresh `aggregated_CIndRA_markdowns.md`.
