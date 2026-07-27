## Skill: Output Conventions

All persisted artifacts (figures, tables, structured results) MUST follow this convention so multi-site analyses never collide.

### Site tag

- Build with `build_site_tag(site_name, site_lon, site_lat)`.
- Format: `<lowercase_alphanum_site>_lat<lat3dec>p<dec>_lon<lon3dec>p<dec>`.
- Example: Palau (134.477, 7.337) → `palau_lat7p337_lon134p477`.

### Filenames

- Build with `build_output_filename(base_name, site_name, site_lon, site_lat, ext=...)`.
- Default extensions: `png` (matplotlib figures), `html` (plotly), `csv` (tables), `json` (metrics).

### Folders (shared convention with the air-temperature workflow)

```
outputs/
├── figures/<site_tag>/     # all published figures
└── tables/<site_tag>/      # CSV tables + JSON metrics
```

- Figures: `build_site_figures_dir(Path('../../outputs'), ...)`.
- Tables: `build_site_tables_dir(Path('../../outputs'), ...)` (via `persist_*_outputs`).
- Site config (input): `data/sites/<safe_name>.json`.
- GHCN cache (input): `data/rainfall/GHCN_<ghcn_station_id>.pkl`.

### Canonical figure filenames

| Notebook | Base name | Format |
|---|---|---|
| `a` | `F5_Rain_daily` | `.html` (plotly) |
| `a` | `F5_Rain_annual_max` | `.html` (plotly) |
| `a` | `F5_Rain_accum` | `.png` (via `plot_bar_probs`) |
| `a` | `F5_Rain_anom_top10` | `.png` |
| `a` | `F6a_Rain_dry_season` | `.png` |
| `a` | `F6a_Rain_wet_season` | `.png` |
| `a` | `F5_Rain_mean_ONI_daily` | `.png` |
| `a` | `F5_Rain_mean_ONI_accum` | `.png` |
| `b` | `F6a_Wet_dry_distribution` | `.png` |
| `b` | `F6a_Number_dry` | `.png` |
| `b` | `F6b_Mean_consecutive_dry` | `.png` |
| `b` | `F6b_Consecutive_dry` | `.png` |
| `c` | `F7a_Wet_dry_distribution` | `.png` |
| `c` | `F7a_Wet_days_1mm` | `.png` |
| `c` | `F7b_Wet_days_95p` | `.png` |

Save matplotlib: `plt.savefig(site_figures_dir / build_output_filename(...), dpi=300, bbox_inches='tight')`.
Save plotly: `fig.write_html(site_figures_dir / build_output_filename(..., ext='html'))`.

Optional diagnostic filename for accumulated rainfall: `F5_Rain_accum_plot_bar_probs_<station_id>_<station_name>.png`.

### Canonical table / JSON filenames

**Notebook `a`** (`persist_total_rainfall_outputs`):
- `R_mean_annual_<site_tag>.csv`
- `R_mean_summary_table_<site_tag>.csv`
- `R_top10_wettest_years_<site_tag>.csv`
- `R_dry_season_annual_<site_tag>.csv`
- `R_wet_season_annual_<site_tag>.csv`
- `R_ONI_annual_<site_tag>.csv`
- `R_mean_summary_metrics_<site_tag>.json`

**Notebook `b`** (`persist_dry_days_outputs`):
- `R_dry_days_per_year_<site_tag>.csv`
- `R_consecutive_dry_max_per_year_<site_tag>.csv`
- `R_consecutive_dry_mean_per_year_<site_tag>.csv`
- `R_dry_summary_table_<site_tag>.csv`
- `R_dry_summary_metrics_<site_tag>.json`

**Notebook `c`** (`persist_heavy_rainfall_outputs`):
- `R_wet_days_per_year_<site_tag>.csv`
- `R_heavy_days_per_year_<site_tag>.csv`
- `R_heavy_summary_table_<site_tag>.csv`
- `R_heavy_summary_metrics_<site_tag>.json`

### Hard rules

- Never overwrite a different site's outputs. Always re-derive `site_tag` from the loaded config.
- Cached pickle is keyed by **station ID**; figures/tables are keyed by **site tag**.
- Use `persist_*_outputs` for tables — do not call `style_matrix` alone without persisting.
