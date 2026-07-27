## Skill: Site Setup (notebook `notebooks/historical/00_site_setup.ipynb`)

### Purpose
Define a new analysis site interactively, pick the right GHCN-Daily station, and pre-download + clean daily **temperature** (`TMIN`/`TMAX`) and **precipitation** (`PRCP`) **once**, so every other notebook — both the air-temperature (`a`/`b`/`c`) and rainfall (`00a`/`00b`/`00c`) notebooks — only loads cached data.

This notebook is **shared** between the two assistants: CIRA (air temperature) and CIndRA (rainfall). It lives one level above both indicator folders, at `notebooks/historical/00_site_setup.ipynb` — a sibling of `notebooks/historical/air_temperature/` and `notebooks/historical/rainfall/`, not inside either one. It replaces the two former per-domain notebooks (`air_temperature/00_site_setup.ipynb` and `rainfall/00_local_site_setup.ipynb`), which no longer exist.

### Inputs the assistant must collect
- `country` (free-form; the notebook fuzzy-matches against the GHCN country list).
- `ghcn_station_id` — chosen from the station table in Step 4 (e.g. `PSW00040309` for Koror).
- `site_name` — **not** freely chosen. It is auto-built in Step 5 as `<country_slug>_<ghcn_station_id>` (e.g. `palau_PSW00040309`), so it stays unique per station even when several stations share the same country. This is the value used everywhere downstream as the site key: config filename, cached-pickle site tag, figures/tables directories.
- `vars_interest` (default `["TMIN", "TMAX", "PRCP"]`). Any variable not available at the chosen station is skipped later with a warning — it does not stop the notebook.
- `reference_period_start` / `reference_period_end` (default `"1961"` / `"1990"`).
- `completeness_threshold` (default `0.75`).
- `force_redownload` (default `False`) — set `True` to refresh a cached pickle.

### Workflow
1. **Step 1 — Site fields**: initialise `site_name`, `site_lon`, `site_lat` (filled automatically after station pick).
2. **Step 2 — Country catalog**: `GHCN.download_country_codes()` + interactive map of GHCN countries.
3. **Step 3 — Country code**: set `country = "Palau"` (or other) and resolve via `GHCN.get_country_code(country)`. If no exact match, show `contains` suggestions and ask the user to refine spelling.
4. **Step 4 — Station list**: `GHCN.download_stations_info()` + `GHCN.download_station_inventory()` → filter by country code → merge `record_start`, `record_end`, `record_years` for **`TMIN`, `TMAX`, `PRCP`** (`elements=("TMIN", "TMAX", "PRCP")`) → show map + table (`ID`, `Name`, `Latitude`, `Longitude`, `Elevation`, record years, `elements`).
5. **Step 5 — Station pick**: set `ghcn_station_id` from the table. Auto-fill `site_lon`, `site_lat`, `ghcn_station_name`, and build `site_name = f"{country_slug}_{ghcn_station_id}"` (slug = lowercase, non-alphanumeric → `_`).
6. **Step 6 — Analysis parameters**: set `vars_interest = ["TMIN", "TMAX", "PRCP"]`, reference period, `completeness_threshold`.
7. **Step 7 — Save site JSON**: `save_site_config(site_config, Path('../../data/sites') / site_config_filename(site_name))`. This single file is read by **both** the air-temperature and rainfall analysis notebooks.
8. **Step 8 — Temperature download & cache** (skipped if `TMIN`/`TMAX` not in `vars_interest` or not available at the station):
   - `temp_pickle_path = Path('../../data/air_temp') / f"GHCN_{ghcn_station_id}.pkl"`.
   - If it exists and `force_redownload` is `False`, load it. Otherwise download `TMIN`/`TMAX` via `GHCN.extract_dict_data_var`, concat, `dropna()`, derive `TMEAN = (TMAX + TMIN) / 2` and `diff = TMAX − TMIN`, save.
   - Apply `filter_by_time_completeness(...)` and overwrite the pickle.
9. **Step 9 — Precipitation download & cache** (skipped if `PRCP` not in `vars_interest` or not available at the station): same pattern as Step 8, but `pickle_path = Path('../../data/rainfall') / f"GHCN_{ghcn_station_id}.pkl"`, single variable `PRCP`, no derived columns.
10. **Step 10 — Quick-look plots**: one plot per domain that actually has data — temperature (daily/monthly/annual overlay, one subplot per column) and precipitation (daily/monthly/annual overlay). Sanity checks only, not published figures.

### Listing already-configured sites
Before asking the user to pick a `country`/station, or before setting `site_key` in a downstream notebook, call `list_available_sites(sites_dir)` (from `air_temp.py` or `rainfall.py` — identical implementation in both) and show the result. It returns one row per existing `data/sites/*.json` with `site_key` (the value to pass to `site_config_filename()`), `site_name`, `country`, `ghcn_station_id`, `ghcn_station_name`, `vars_interest`. This lets the user reuse an already-downloaded site instead of re-running Step 5–9.

### Output contract
- JSON at `data/sites/<site_key>.json` (filename = `site_config_filename(site_name)`, a lowercase/underscore slug of `site_name`) with: `site_name`, `site_lon`, `site_lat`, `country`, `ghcn_station_id`, `ghcn_station_name`, `vars_interest`, `reference_period_start`, `reference_period_end`, `completeness_threshold`.
- Cleaned pickle at `data/air_temp/GHCN_<ghcn_station_id>.pkl` (if `TMIN`/`TMAX` requested and available) — DataFrame indexed by `DatetimeIndex`, columns `TMIN`, `TMAX`, `TMEAN`, `diff`, all in **°C**.
- Cleaned pickle at `data/rainfall/GHCN_<ghcn_station_id>.pkl` (if `PRCP` requested and available) — DataFrame indexed by `DatetimeIndex`, column `PRCP` in **mm**.

### Common follow-up actions
- Confirm which station was selected, its coordinates, and which variables (`TMIN`/`TMAX`/`PRCP`) were actually downloaded — a station may only report one domain.
- If the station record is short or has large gaps, warn the user before running any downstream notebook.
- After saving the config, recommend opening `notebooks/historical/air_temperature/a_mean_temperature.ipynb` and/or `notebooks/historical/rainfall/00a_Total_rainfall.ipynb` next, depending on which variables are available.

### Hard rules

- Do not re-run `00_site_setup.ipynb` unless the user changes site/station, wants to add a variable that wasn't downloaded before, or a cached pickle is missing.
- Never write the site config outside `data/sites/`.
- Never write GHCN pickles outside `data/air_temp/` (temperature) or `data/rainfall/` (precipitation).
- Always name pickles `GHCN_<ghcn_station_id>.pkl` (per station, not per site) — a site tag can map to only one station, but the reverse note matters: **do not** reuse a `site_name` across two different stations, since `site_name` is now the key everything else (config filename, `build_site_tag`, output folders) is derived from.
- `site_name` is derived, not freely typed: `<country_slug>_<ghcn_station_id>`. Do not hand-edit it to something unrelated to the station — downstream notebooks assume `site_config_filename(site_name)` round-trips back to the same file.
- The QC plots in Step 10 are quick-look matplotlib overlays only — not published figures. Published figures in downstream notebooks must use `ind_setup` helpers after function discovery.
