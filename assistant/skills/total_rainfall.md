## Skill: Total Rainfall (notebook `notebooks/historical/rainfall/00a_Total_rainfall.ipynb`)

### Purpose
Quantify annual accumulated precipitation, daily extremes, seasonal totals, and ENSO modulation at the site's GHCN station. Report anomalies relative to the reference period from the site config.

### Required inputs
- Site config JSON at `data/sites/<site_key>.json` (from the shared `../00_site_setup.ipynb`).
- Cleaned pickle at `data/rainfall/GHCN_<ghcn_station_id>.pkl`.

### Key definitions
- **Wet day**: `PRCP > 1 mm` (used in some exploratory sections).
- **Accumulated annual rainfall** — normalise for unequal observation counts:

  `annual accumulated rainfall = (sum of observed daily rainfall in the year / number of valid daily observations in the year) × 365`

  In code: `(groupby(year).sum() / groupby(year).count()) * 365`. Units: **mm/year**.
- **Dry season** (Palau convention in notebook): months 12–4 and 11 (`season == "dry"`).
- **Wet season**: months 5–10 (`season == "wet"`).
- **Reference-period anomaly**: subtract `datag.loc[ref_start:ref_end].PRCP.mean()` (use slice syntax, not a single `"1961:1990"` string).

### Workflow
1. Set `site_key`, load config via `load_site_config(Path('../../data/sites') / site_config_filename(site_key))`. Extract `site_name`, coordinates, `ghcn_station_id`, `ref_start`, `ref_end`.
2. Build `site_figures_dir = build_site_figures_dir(Path('../../outputs'), site_name, site_lon, site_lat)`.
3. Load data: `data = pd.read_pickle(data_dir / f"GHCN_{ghcn_station_id}.pkl")`. Keep `data_daily = data.copy()`.
4. **Daily series**: `plot_timeseries_interactive` on raw `PRCP` with `trendline=True`.
5. **Annual daily maxima**: `data.groupby(data.index.year).max()`, resample to year-start timestamps, plot.
6. **Accumulated annual rainfall** (`datag`):
   - Build normalised annual totals (formula above).
   - Styled bar plot via `plot_bar_probs(x=years, y=mm_per_year, bar_label='Accumulated annual rainfall', trendline=True, y_label='Accumulated annual rainfall (mm/year)', return_trend=True)` → glue `accum_rain`, save `F5_Rain_accum.png`.
   - Multiply returned trend by 10 to report **mm/decade**; compute p-value separately if needed for reporting.
   - Top-10 wettest years vs reference mean.
   - Anomaly plot with twin axis for absolute rainfall + top-10 scatter → save `F5_Rain_anom_top10.png`.
7. **Seasonal accumulated rainfall**: split by dry/wet season, compute annual normalised totals per season, plot anomalies vs reference → save `F6a_Rain_dry_season.png`, `F6a_Rain_wet_season.png`.
8. **ONI / ENSO** (when requested):
   - `download_oni_index('https://psl.noaa.gov/data/correlation/oni.data')` (cache as `data/rainfall/oni_index.pkl` when `update_oni = True`).
   - Join monthly mean `PRCP` from `data_daily`.
   - `add_oni_cat` + `plot_bar_probs_ONI` for mean and accumulated precipitation anomalies → save `F5_Rain_mean_ONI_daily.png`, `F5_Rain_mean_ONI_accum.png`.
9. **Summary table**: `table_rain_21` via `style_matrix`. Persist via `persist_total_rainfall_outputs`.

### Function discovery
Before writing custom matplotlib for bar charts, import `plot_bar_probs` from `ind_setup.plotting`. If missing, search locally or clone `https://github.com/lauracagigal/indicators_setup` into `external/indicators_setup` and add to `sys.path`. See `functions_api.md`.

### Persisted figures (under `outputs/figures/<site_tag>/`)
- `F5_Rain_accum.png` — accumulated annual rainfall styled with `plot_bar_probs`.
- `F5_Rain_anom_top10.png` — annual accumulated rainfall anomaly with top-10 years.
- `F5_Rain_mean_ONI_daily.png`, `F5_Rain_mean_ONI_accum.png` — ENSO-modulated precipitation anomaly.
- `F6a_Rain_dry_season.png` — dry-season accumulated anomaly.
- `F6a_Rain_wet_season.png` — wet-season accumulated anomaly.

Optional diagnostic filename: `F5_Rain_accum_plot_bar_probs_<station_id>_<station_name>.png`.

### Reporting style
Example:

> Accumulated annual rainfall at `PSW00040309 — KOROR` over 1952–2025 shows a trend of `+15.2 mm/decade` using the cleaned GHCN-Daily `PRCP` series. The trend is not statistically significant (`p = 0.636`). The 1961–1990 reference-period mean is `3757 mm/year`.

Always include: station ID and name, data source (GHCN-Daily), analysis window, units (**mm**, **mm/year**), reference period, and whether data are completeness-filtered.

### Hard rules
- Do **not** re-download GHCN data here; read the cached pickle.
- Use `ref_start:ref_end` slice for reference-period means — never `.loc["1961:1990"]` as a single label.
- Use `plot_bar_probs` from `ind_setup.plotting` for published bar charts; do not inline matplotlib unless function discovery fails (label as quick-look).
- Do not claim repo styling was used unless `plot_bar_probs` was actually imported and called.
- Season labels (dry/wet months) are site-specific; confirm with the user before applying Palau defaults to another site.
