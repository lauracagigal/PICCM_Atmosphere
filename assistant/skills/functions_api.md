## Skill: Functions API Reference (`functions/site_common.py` + `functions/rainfall.py` + `functions/air_temp.py` + `functions/temp_func.py` + `functions/data_downloaders.py` + `functions/rainfall_regional.py` + `indicators_setup`)

Single source of truth for what the assistant is allowed to call, across both the rainfall and air-temperature workflows. If something is missing, add a function to `functions/` — do not inline it in notebooks.

---

## Function-Discovery Rule

CIndRA should actively **find and use functions from the relevant repositories** before writing custom analysis or plotting code.

For PICCM plotting and styling (rainfall and air temperature alike), look for and use functions from the external **`indicators_setup`** repository:

- GitHub: <https://github.com/lauracagigal/indicators_setup>
- Package path: `ind_setup`
- Canonical plotting module: `ind_setup.plotting`
- Canonical styled bar-plot function: `plot_bar_probs`
- Canonical interactive time-series function: `plot_timeseries_interactive` (`ind_setup.plotting_int`)

`plot_bar_probs` is the preferred helper for published PICCM bar charts: accumulated annual rainfall, dry-day counts, consecutive dry-day metrics, wet-day counts, heavy-rainfall counts, and annual mean-temperature trends. `plot_timeseries_interactive` is preferred for annual TMIN/TMAX, diurnal range, and hot-day/cold-night time series.

---

## Function Discovery Workflow

When a required function is not immediately importable, search the local workspace and known repositories before falling back to ad-hoc code.

### 1. Try direct imports first

```python
from ind_setup.plotting import plot_bar_probs
from ind_setup.plotting import plot_bar_probs_ONI
from ind_setup.plotting import add_oni_cat
from ind_setup.plotting_int import plot_timeseries_interactive, fig_int_to_glue
from ind_setup.tables import style_matrix
from ind_setup.tables import table_rain_21, table_rain_22, table_rain_23
from ind_setup.tables import table_temp_11, table_temp_12, table_temp_13, table_temp_13b
```

If imports succeed, inspect the function signature before calling unfamiliar functions.

### 2. Search the local workspace

Search bounded local paths:

- `ind_setup/plotting.py`
- `ind_setup/colors.py`
- `ind_setup/tables.py`
- `indicators_setup/ind_setup/plotting.py`
- `functions/site_common.py`
- `functions/rainfall.py`
- `functions/air_temp.py`
- `functions/temp_func.py`
- `functions/data_downloaders.py`
- `functions/rainfall_regional.py`

Look for: `plot_bar_probs`, `plot_bar_probs_ONI`, `plot_timeseries_interactive`, `add_oni_cat`, `get_df_col`, `style_matrix`, `table_rain_21`, `table_rain_22`, `table_rain_23`, `table_temp_11`, `table_temp_12`, `table_temp_13`, `table_temp_13b`.

Notebooks typically add the package via `sys.path.append("../../../../../indicators_setup")` (rainfall/air-temperature analysis notebooks, one level deeper than `00_site_setup.ipynb`).

### 3. Clone `indicators_setup` if missing

If `indicators_setup` is not installed and not present locally, clone into a session-local folder such as `external/indicators_setup`, then add the repository root to `sys.path` so `ind_setup` can be imported.

Do **not** assume the repository is pip-installable. It may lack `setup.py` or `pyproject.toml`; cloning and path injection may be required.

### 4. Use repository functions once found

- `plot_bar_probs(..., trendline=True, return_trend=True)` — styled bar plots with linear trend lines.
- `plot_timeseries_interactive(dict_plot, trendline=True, return_trend=True)` — styled interactive plotly time series, single- or multi-series.
- Use the trend returned by these functions when reporting the repository-computed trend.
- If p-value or additional regression statistics are needed and not returned by the plotting function, compute those separately only for reporting, while preserving the repository-generated figure style.

---

## `plot_bar_probs` signature and usage

Expected signature:

`plot_bar_probs(x, y, bar_label=None, labels=None, trendline=False, y_label=' ', figsize=[7, 5], return_trend=False)`

Returns `(fig, ax)` or `(fig, ax, trend)` when `return_trend=True`.

| Use case | `x` | `y` | `y_label` | Trend units |
|---|---|---|---|---|
| Accumulated annual rainfall | years (numeric) | mm/year | `Accumulated annual rainfall (mm/year)` | mm/year → ×10 for mm/decade |
| Dry-day counts | years | days/year | `Number of dry days` | days/year → ×10 for days/decade |
| Wet-day / heavy-day counts | years | days/year | as appropriate | days/year → ×10 for days/decade |
| Annual mean temperature | years | °C | `Mean Temperature` | °C/year → ×10 for °C/decade |

Ad-hoc matplotlib bar plots are acceptable only for quick-look/QC or when `plot_bar_probs` is truly unavailable after discovery. Label such outputs as quick-look or non-repo-styled.

---

## `functions/site_common.py` — shared site config, output paths

`rainfall.py` and `air_temp.py` both re-export everything in this module (`from rainfall import site_config_filename` and `from air_temp import site_config_filename` are the same function) -- it exists so the two domain modules don't maintain two silently-diverging copies of the same code. Import from whichever domain module matches the notebook; there is no reason to import `site_common` directly.

**Site configuration**
- `site_config_filename(site_key)` → JSON filename (slugified: lowercase, non-alphanumeric → `_`). `site_key` is normally `<country_slug>_<ghcn_station_id>`, e.g. `"palau_PSW00040309"` → `"palau_psw00040309.json"`.
- `save_site_config(config_dict, output_path)` → write site JSON; creates parent directory.
- `load_site_config(config_path)` → load JSON dict. Raises `FileNotFoundError` if missing.
- `list_available_sites(sites_dir)` → DataFrame, one row per `data/sites/*.json`, columns `site_key`, `site_name`, `country`, `ghcn_station_id`, `ghcn_station_name`, `vars_interest`. Call before asking the user for a `site_key` so they can reuse an already-configured site.

**Output paths**
- `build_site_tag(site_name, site_lon, site_lat)` → filesystem-safe tag.
- `build_output_filename(base_name, site_name, site_lon, site_lat, ext='png')` → `"<base_name>_<site_tag>.<ext>"`.
- `build_site_figures_dir(base_outputs_dir, ...)` → `outputs/figures/<site_tag>/`.
- `build_site_tables_dir(base_outputs_dir, ...)` → `outputs/tables/<site_tag>/`.

**Persist-helper internals** (used by the `persist_*_outputs` functions below, not usually called directly): `table_to_dataframe`, `save_table_to_csv`, `save_dict_json`, `_trend_pvalue`, `_series_stats`, `_site_meta`, `_frame_with_year_column`, `_display_site_table`.

---

## `functions/rainfall.py` and `functions/air_temp.py` — domain-specific persist helpers

**Rainfall-specific (`rainfall.py`), dry-spell metrics** (notebook `b_Consecutive_dry_days.ipynb`)
- `consecutive_dry_days(series)` → maximum consecutive dry days in a boolean series.
- `count_consecutive_days(series)` → running count of consecutive dry days.

**Persist helpers**
- `rainfall.py`: `persist_total_rainfall_outputs(...)` (`a_Total_rainfall.ipynb`: CSVs + `R_mean_summary_metrics_*.json`), `persist_dry_days_outputs(...)` (`b_Consecutive_dry_days.ipynb`: CSVs + `R_dry_summary_metrics_*.json`), `persist_heavy_rainfall_outputs(...)` (`c_Heavy_rainfall.ipynb`: CSVs + `R_heavy_summary_metrics_*.json`).
- `air_temp.py`: `persist_mean_temperature_outputs(...)` (`a`: CSVs + `T_mean_summary_metrics_*.json`), `persist_minmax_temperature_outputs(...)` (`b`: CSVs + `T_minmax_summary_metrics_*.json`), `persist_hot_cold_outputs(...)` (`c`: CSVs + `T_hot_cold_summary_metrics_*.json`).

Station ranking/selection in `00_site_setup.ipynb` is currently a plain alphabetical station table (`sort_values(["Name", "ID"])`) — there is no distance-based ranking helper in `functions/` (an earlier `haversine_km` was unused dead code and has been removed).

---

## `functions/temp_func.py` — ETCCDI temperature-extreme calculations

- `exceedance_rate_for_base_period(st_data, var)` → per-year exceedance rate over the 1961–1990 base period for `"TMAX"` (TX90p) or `"TMIN"` (TN10p).
- `exceedance_rate_for_outbase_period(st_data, var)` → calendar-day (366-row) percentile thresholds `(DAY, THRESHOLD)` derived from the base period, applied to the full record.

---

## `functions/data_downloaders.py` — GHCN, ONI, completeness

**`GHCN` class**
- `download_country_codes()` → DataFrame `(Code, Country)`.
- `get_country_code(country)` → exact-match row(s) for a country name.
- `download_stations_info()` → `ID`, `Latitude`, `Longitude`, `Elevation`, `Name`.
- `download_station_inventory()` → per-station element record spans.
- `summarize_record_years(inventory_df, station_ids, elements=("TMIN", "TMAX", "PRCP"))` → `record_start`, `record_end`, `record_years`, `elements`.
- `extract_dict_data_var(GHCND_dir, var, df_country_stations)` → `(records, station_ids)`. Downloads per-station CSV; divides `TMIN`/`TMAX`/`PRCP` by 10. Returns plot-ready dicts plus ID list.

**Standalone functions**
- `download_oni_index(url)` → monthly ONI DataFrame; `-99.9` → NaN.
- `filter_by_time_completeness(df, time_col, month_threshold, year_threshold)` → `(df_filtered, removed_months, removed_years)`.

---

## `functions/rainfall_regional.py` — regional (multi-station) Pacific maps

Used by `notebooks/historical/Regional/rainfall/compute_regional_indicators.ipynb` and `notebooks/historical/Regional/air_temperature/compute_regional_indicators.ipynb`, both of which build on the multi-station dictionary `01_regional_setup.ipynb` produces (`data/regional/<region_key>_stations.pkl`). Not part of the single-site `00_site_setup.ipynb` → `a/b/c` workflow the rest of this file describes.

**Regional indicators** (per-station annual DataFrames, mirroring the National single-site notebooks' formulas)
- `compute_regional_rainfall_indicators(stations_data, ...)` → `(dict_lon_lat, annual_data, heavy_thresholds)`. Columns: `total_annual_mm`, `dry_days`, `wet_days`, `max_consecutive_dry_days`, `mean_consecutive_dry_days`, `heavy_days` (`RAINFALL_INDICATOR_LABELS`/`RAINFALL_INDICATOR_UNITS`).
- `compute_regional_temperature_indicators(stations_data, ...)` → `(dict_lon_lat, annual_data, thresholds)`. Columns: `tmean_annual`, `tmin_annual`, `tmax_annual`, `diff_annual`, `hot_days_pct`, `cold_nights_pct` (`TEMPERATURE_INDICATOR_LABELS`/`TEMPERATURE_INDICATOR_UNITS`). `hot_days_pct`/`cold_nights_pct` use a **fixed station-wide percentile** (90th `TMAX` / 10th `TMIN` over the reference period), not the full calendar-day ETCCDI TX90p/TN10p climatology in `temp_func.py` — that method is too slow to run per-station across a few hundred stations.
- `compute_regional_temperature_anomaly_series(annual_data, ...)` → `(annual_anomaly, smoothed)`, a simple unweighted station-average anomaly time series with a 5-year rolling mean.

**Station-only maps** (no ERA5)
- `RegionalMapConfig(variable, metric="trend"|"mean", period_start, period_end, min_years=2, cmap, vmin, vmax, color_label, ...)` — `min_years` guards against an unstable few-point regression (e.g. 2 valid years) dominating a map's colour scale; the regional notebooks set it to 20.
- `build_sites_map_dataframe(dict_lon_lat, config, annual_data=...)` → one row per station: `value`, `p_value`, `n_years`, `significant`.
- `plot_annual_regional_map(dict_lon_lat, annual_data, data_dir, config, variable_labels=...)` → `(fig, ax, sites_df)`. `data_dir` here is the shared PICCM `data/` folder (one level above this repo) that holds `Pacific_EEZs/*.shp` — not this repo's own `data/`.
- `create_pacific_base_map(data_dir, ...)` → `(fig, ax, eez_gdf)`, the shared EEZ + land base map both regional notebooks build on.

**ERA5-background maps** — only for indicators reconstructable from *monthly* ERA5 fields (annual accumulated rainfall, annual mean temperature); anything needing daily data (dry-day counts, hot/cold days, diurnal range) has no ERA5 counterpart.
- `plot_monthly_rainfall_with_era5_background(dict_lon_lat, monthly_data, data_dir, era5_ds, metric=..., annual_data=..., variable="total_annual_mm", era5_field=..., min_years=...)` / `plot_monthly_temperature_with_era5_background(..., variable="tmean_annual", ...)` — pass exactly one of `monthly_data` (CIPSAP-style) or `annual_data` (GHCN-style, this repo's usage); `era5_field` lets a caller pass an already-computed field to skip recomputation.
- `load_or_compute_era5_annual_rainfall(era5_ds, cache_path, metric, ...)` / `load_or_compute_era5_annual_temperature(...)` — NetCDF-cached mean/trend field computation (pulling + aggregating global monthly ERA5 over the network is slow); pass `era5_ds=None` on a cache hit.
- `plot_era5_eez_temperature_anomaly(era5_ds, data_dir, period_start, period_end, baseline_start, baseline_end, smooth_years=5)` → EEZ area-weighted mean temperature anomaly time series (the ERA5 counterpart of `compute_regional_temperature_anomaly_series`'s station average).
- ERA5 endpoint: `https://api.earthdatahub.destine.eu/era5/era5-single-levels-atmosphere-monthly-v0.zarr` (opened with `xarray.open_dataset(..., engine="zarr")`); `tp` needs `* 1000 * 30` (m/day → mm/month) and an explicit `.attrs["units"] = "mm"` before use, `t2m` needs `- 273.15` (K → °C).

---

## External plotting / tables (`indicators_setup`)

- `ind_setup.plotting`: `plot_bar_probs`, `plot_bar_probs_ONI`, `add_oni_cat`, `plot_oni_index_th`, `fontsize`.
- `ind_setup.plotting_int`: `plot_timeseries_interactive`, `fig_int_to_glue`.
- `ind_setup.tables`: `style_matrix`, `table_rain_21`, `table_rain_22`, `table_rain_23`, `table_temp_11`, `table_temp_12`, `table_temp_13`, `table_temp_13b`.
- `ind_setup.colors`: `get_df_col` (stacked bar colours).

---

## Hard rules

- Never redefine helpers that exist in `functions/site_common.py`, `functions/rainfall.py`, `functions/air_temp.py`, `functions/temp_func.py`, `functions/data_downloaders.py`, or `functions/rainfall_regional.py`.
- Use repository functions before custom code; clone `indicators_setup` if missing.
- Do not fabricate repository functions or claim repo styling was used unless the function was actually imported and called.
- After editing modules, reload in the notebook: `import importlib; import rainfall as rf; importlib.reload(rf)` (or `air_temp`, `temp_func`, `rainfall_regional`).
- Keep this file in sync when `functions/` or `indicators_setup` usage changes.
