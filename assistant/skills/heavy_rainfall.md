## Skill: Heavy Rainfall (notebook `00c_Heavy_rainfall.ipynb`)

### Purpose
Quantify wet-day frequency and extreme (heavy) rainfall days at the site's GHCN station.

### Required inputs
- Site config JSON (`data/sites/<site_key>.json`, from the shared `../00_site_setup.ipynb`).
- Cleaned pickle (`data/rainfall/GHCN_<ghcn_station_id>.pkl`).

### Key definitions
- **Wet day**: `PRCP >= 1 mm` (days above the 1 mm threshold).
- **Heavy rainfall day**: `PRCP` above the **95th percentile** of the full record (`np.percentile(PRCP.dropna(), 95)`), rounded to 2 decimals. For Koror this is typically ~45.7 mm.
- **Year filter**: keep years with ≥ 300 daily observations.

### Workflow
1. Load config and cached data. Build `site_figures_dir`.
2. Filter years with ≥ 300 observations. Glue `n_years`.
3. Classify wet/dry (`wet_day` flag at 1 mm). Exploratory distribution plot.
4. **Wet days (> 1 mm)**:
   - Annual count of wet days → `plot_bar_probs(..., trendline=True, return_trend=True)` → glue `number_wet_days`, save `F7a_Wet_days_1mm.png`.
   - Multiply returned trend by 10 to report **days/decade**.
   - Keep copy `data_th_1mm` for the summary table.
5. **Heavy rainfall days (95th percentile)**:
   - `threshold = round(np.percentile(data['PRCP'].dropna(), 95), 2)`.
   - Annual count of days above threshold → `plot_bar_probs` → glue `number_over_95`, save `F7b_Wet_days_95p.png`.
   - Keep copy `data_th_95` for the summary table.
6. **Summary table**: `table_rain_23` via `style_matrix`. Persist via `persist_heavy_rainfall_outputs`.

### Function discovery
Use `plot_bar_probs` from `ind_setup.plotting` for all published bar charts. Import via `sys.path` to `indicators_setup` or clone from <https://github.com/lauracagigal/indicators_setup> if missing. See `functions_api.md`.

### Persisted figures
- `F7a_Wet_days_1mm.png` — annual wet-day count (> 1 mm).
- `F7b_Wet_days_95p.png` — annual heavy-rainfall days (> 95th percentile).

### Reporting style
- "Wet days: rainfall above 1 mm. Heavy rainfall days: rainfall above the 95th percentile (<threshold> mm)."
- "Wet-day trend at <station_id>: X days/decade (p = P). Heavy-rainfall trend: Y days/decade (p = P)."
- Always state the computed 95th-percentile threshold in mm and whether data are completeness-filtered.

### Hard rules
- The 95th percentile is computed on the **full available record** at the station (not restricted to the reference period), matching the notebook.
- Do not conflate wet-day (1 mm) and heavy-rainfall (95p) metrics in the same sentence without labelling each.
- Use `plot_bar_probs` for published bar charts after function discovery; do not inline matplotlib unless truly unavailable (label as quick-look).
- Do not claim repo styling was used unless `plot_bar_probs` was actually imported and called.
