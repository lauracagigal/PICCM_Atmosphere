## Skill: Consecutive Dry Days (notebook `00b_Consecutive_dry_days.ipynb`)

### Purpose
Quantify dry-day frequency and consecutive dry spells at the site's GHCN station. Dry conditions are a key drought / water-stress indicator for Pacific Island sites.

### Required inputs
- Site config JSON (`data/sites/<site_key>.json`, from the shared `../00_site_setup.ipynb`).
- Cleaned pickle (`data/rainfall/GHCN_<ghcn_station_id>.pkl`).

### Key definitions
- **Dry day**: `PRCP < 1 mm` (equivalently `PRCP <= 1 mm` depending on strict `>` vs `>=` in the wet-day flag; primary threshold is **1 mm**).
- **Wet day**: `PRCP > 1 mm`.
- **Consecutive dry days (annual max)**: longest run of dry days within each year, via `consecutive_dry_days` applied per year.
- **Running consecutive dry days**: per-day count of the current dry spell via `count_consecutive_days` on `PRCP < threshold`.
- **Year filter**: keep years with ≥ 300 daily observations (`groupby(year).filter(lambda x: len(x) >= 300)`).

### Workflow
1. Load config and cached `PRCP` data. Build `site_figures_dir`.
2. Classify wet/dry: `data['wet_day'] = np.where(PRCP > 1, 1, 0)` (NaN where missing).
3. Exploratory distribution bar chart (wet vs dry day counts).
4. **Annual dry-day counts**:
   - `threshold = 1` mm.
   - Annual count of dry days (`wet_day_t == 0`) → `plot_bar_probs(..., trendline=True, return_trend=True)` → glue `number_dry_days`, save `F6a_Number_dry.png`.
   - Multiply returned trend by 10 to report **days/decade**.
5. **Consecutive dry days**:
   - Filter to years with ≥ 300 days.
   - `data['dry_day'] = np.where(PRCP < threshold, 1, 0)`.
   - `consecutive_dry_days` per year (annual maximum spell).
   - `count_consecutive_days` on `PRCP < threshold` for per-day running counts.
   - Mean consecutive dry days per year → glue `mean_dry_days_fig`.
   - Maximum consecutive dry days per year → `plot_bar_probs` → glue `maximum_cons_dry_days`, save `F6b_Consecutive_dry.png`.
6. **Summary table**: `table_rain_22` via `style_matrix`. Persist via `persist_dry_days_outputs`.

### Function discovery
Use `plot_bar_probs` from `ind_setup.plotting` for all published bar charts. Import via `sys.path` to `indicators_setup` or clone from <https://github.com/lauracagigal/indicators_setup> if missing. See `functions_api.md`.

### Persisted figures
- `F6a_Number_dry.png` — annual number of dry days (< 1 mm).
- `F6b_Consecutive_dry.png` — annual maximum consecutive dry days.

### Reporting style
- "Dry days are defined as days with rainfall below 1 mm (0.04 inches)."
- "Maximum consecutive dry days at <station_id> (<start>–<end>): trend X days/decade (p = P). Source: GHCN-Daily."
- Report both annual dry-day count and maximum consecutive dry-day metrics.
- Always state whether data are completeness-filtered.

### Hard rules
- Use `consecutive_dry_days` and `count_consecutive_days` from `functions/rainfall.py` — do not reimplement inline.
- Do not change the 1 mm threshold without explicit user request (WMO / ETCCDI wet-day convention).
- Published figures must use `plot_bar_probs` from `ind_setup.plotting` after function discovery.
- If falling back to custom matplotlib, label the figure as quick-look or non-repo-styled.
