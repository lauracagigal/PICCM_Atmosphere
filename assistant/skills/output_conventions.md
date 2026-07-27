## Skill: Output Conventions

All persisted artifacts (figures, tables, structured results) MUST follow this convention so multi-site analyses never collide. It applies to **both** the rainfall and air-temperature notebooks.

### Site tag

- Build with `build_site_tag(site_name, site_lon, site_lat)`.
- Format: `<lowercase_alphanum_site>_lat<lat3dec>p<dec>_lon<lon3dec>p<dec>`.
- Example: `palau_PSW00040309` (134.477, 7.337) → `palau_psw00040309_lat7p337_lon134p477`.

### Filenames

- Build with `build_output_filename(base_name, site_name, site_lon, site_lat, ext=...)`.
- Default extensions: `png` (matplotlib figures), `html` (plotly), `csv` (tables), `json` (metrics).

### Folders (shared convention across both domains)

```
outputs/
├── figures/<site_tag>/     # all published figures
└── tables/<site_tag>/      # CSV tables + JSON metrics
```

- Figures: `build_site_figures_dir(Path('../../outputs'), ...)`.
- Tables: `build_site_tables_dir(Path('../../outputs'), ...)` (via `persist_*_outputs`).
- Site config (input): `data/sites/<site_key>.json`.
- GHCN cache (input): `data/rainfall/GHCN_<ghcn_station_id>.pkl` (rainfall) and/or `data/air_temp/GHCN_<ghcn_station_id>.pkl` (temperature).

### Canonical figure filenames — rainfall (`notebooks/historical/rainfall/`)

| Notebook | Base name | Format |
|---|---|---|
| `00a` | `F5_Rain_daily` | `.html` (plotly) |
| `00a` | `F5_Rain_annual_max` | `.html` (plotly) |
| `00a` | `F5_Rain_accum` | `.png` (via `plot_bar_probs`) |
| `00a` | `F5_Rain_anom_top10` | `.png` |
| `00a` | `F6a_Rain_dry_season` | `.png` |
| `00a` | `F6a_Rain_wet_season` | `.png` |
| `00a` | `F5_Rain_mean_ONI_daily` | `.png` |
| `00a` | `F5_Rain_mean_ONI_accum` | `.png` |
| `00b` | `F6a_Wet_dry_distribution` | `.png` |
| `00b` | `F6a_Number_dry` | `.png` |
| `00b` | `F6b_Mean_consecutive_dry` | `.png` |
| `00b` | `F6b_Consecutive_dry` | `.png` |
| `00c` | `F7a_Wet_dry_distribution` | `.png` |
| `00c` | `F7a_Wet_days_1mm` | `.png` |
| `00c` | `F7b_Wet_days_95p` | `.png` |

Optional diagnostic filename for accumulated rainfall: `F5_Rain_accum_plot_bar_probs_<station_id>_<station_name>.png`.

### Canonical figure filenames — air temperature (`notebooks/historical/air_temperature/`)

| Notebook | Base name | Format |
|---|---|---|
| `a` | `F2_ST_Mean` | `.png` (via `plot_bar_probs`) |
| `a` | `F2_ST_Annomalies_top10` | `.png` |
| `b` | `F3_ST_min` | `.html` + `.png` (via `plot_timeseries_interactive`) |
| `b` | `F3_ST_max` | `.html` + `.png` |
| `b` | `F3_ST_min_max` | `.html` + `.png` |
| `c` | `F4_ST_hot_cold` | `.html` + `.png` |
| `c` | `F4_ST_hot_cold_percentiles` | `.html` + `.png` |

Save matplotlib: `plt.savefig(site_figures_dir / build_output_filename(...), dpi=300, bbox_inches='tight')`.
Save plotly: `fig.write_html(site_figures_dir / build_output_filename(..., ext='html'))` and, where applicable, `fig.write_image(site_figures_dir / build_output_filename(...))`.

### Canonical table / JSON filenames — rainfall (`R_*` prefix)

**Notebook `00a`** (`persist_total_rainfall_outputs`):
- `R_mean_annual_<site_tag>.csv`
- `R_mean_summary_table_<site_tag>.csv`
- `R_top10_wettest_years_<site_tag>.csv`
- `R_dry_season_annual_<site_tag>.csv`
- `R_wet_season_annual_<site_tag>.csv`
- `R_ONI_annual_<site_tag>.csv`
- `R_mean_summary_metrics_<site_tag>.json`

**Notebook `00b`** (`persist_dry_days_outputs`):
- `R_dry_days_per_year_<site_tag>.csv`
- `R_consecutive_dry_max_per_year_<site_tag>.csv`
- `R_consecutive_dry_mean_per_year_<site_tag>.csv`
- `R_dry_summary_table_<site_tag>.csv`
- `R_dry_summary_metrics_<site_tag>.json`

**Notebook `00c`** (`persist_heavy_rainfall_outputs`):
- `R_wet_days_per_year_<site_tag>.csv`
- `R_heavy_days_per_year_<site_tag>.csv`
- `R_heavy_summary_table_<site_tag>.csv`
- `R_heavy_summary_metrics_<site_tag>.json`

### Canonical table / JSON filenames — air temperature (`T_*` prefix)

**Notebook `a`** (`persist_mean_temperature_outputs`):
- `T_mean_annual_<site_tag>.csv`
- `T_mean_summary_table_<site_tag>.csv`
- `T_mean_top10_warmest_years_<site_tag>.csv`
- `T_mean_ONI_annual_<site_tag>.csv`
- `ENSO_temperature_summary_<site_tag>.csv`
- `T_mean_summary_metrics_<site_tag>.json`

**Notebook `b`** (`persist_minmax_temperature_outputs`):
- `T_minmax_annual_<site_tag>.csv`
- `T_minmax_summary_table_<site_tag>.csv`
- `T_minmax_summary_metrics_<site_tag>.json`

**Notebook `c`** (`persist_hot_cold_outputs`):
- `T_hot_days_per_year_<site_tag>.csv`
- `T_cold_nights_per_year_<site_tag>.csv`
- `T_hot_cold_summary_table_etccdi_<site_tag>.csv`
- `T_hot_cold_summary_table_percentiles_<site_tag>.csv`
- `T_hot_cold_summary_metrics_<site_tag>.json`

### Hard rules

- Never overwrite a different site's outputs. Always re-derive `site_tag` from the loaded config.
- Cached pickle is keyed by **station ID**; figures/tables are keyed by **site tag**.
- Use `persist_*_outputs` for tables — do not call `style_matrix` alone without persisting.
- Rainfall outputs use the `R_`/`F5`/`F6`/`F7` prefixes; air-temperature outputs use `T_`/`F2`/`F3`/`F4`. Don't mix them.
