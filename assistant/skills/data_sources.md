## Skill: Data Sources & Attribution

### Daily precipitation and temperature — GHCN-Daily (NOAA NCEI)

- **Country lookup**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-countries.txt` → `GHCN.download_country_codes()`.
- **Station inventory**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt` → `GHCN.download_stations_info()`.
- **Element inventory**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt` → `GHCN.download_station_inventory()`.
- **Per-station daily CSVs**: `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/<station_id>.csv`.
- **Variables in use**: `PRCP` (rainfall), `TMIN`/`TMAX` (temperature) — all stored in tenths of the analysis unit; downloader divides by 10.
- **Units after conversion**: daily rainfall **mm/day**; annual accumulated rainfall **mm/year**; temperature **°C**; `TMEAN = (TMAX + TMIN) / 2` and `diff = TMAX − TMIN` derived in `00_site_setup.ipynb`.
- **Sentinels**: `-9999` → NaN inside `extract_dict_data_var`.
- **Documentation**: `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/doc/GHCND_documentation.pdf`.
- **Citation**: Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012. *An overview of the Global Historical Climatology Network-Daily Database.* J. Atmos. Oceanic Technol., 29, 897-910.

### ENSO — NOAA ONI (rainfall `a_Total_rainfall.ipynb` and temperature `a_mean_temperature.ipynb`)

- **URL**: `https://psl.noaa.gov/data/correlation/oni.data`.
- **Format**: monthly Niño 3.4 anomalies. `-99.9` → NaN (`download_oni_index`).
- **Classification** (via `add_oni_cat` in `ind_setup`):
  - El Niño: ONI ≥ 0.5 (5 consecutive months for official events; plotting uses monthly categories).
  - La Niña: ONI ≤ −0.5.
  - Neutral otherwise.
- **Colours**: El Niño = red, La Niña = blue, Neutral = gray.
- **Citation**: NOAA Climate Prediction Center / Physical Sciences Laboratory.

### Reference periods

- Climatology baseline for anomalies: **1961–1990** (WMO standard), stored in site config as `reference_period_start` / `reference_period_end`. Applies to rainfall totals and to mean/min/max temperature anomalies alike.
- In code, slice with `.loc[ref_start:ref_end]` — never pass `"1961:1990"` as a single label to `.loc` on a DatetimeIndex.
- Hot days (TX90p) / cold nights (TN10p) use the same 1961–1990 window as the ETCCDI base period, hardcoded in `temp_func.py` (`BASE_PERIOD_START`/`BASE_PERIOD_END`).

### QC applied in the shared `00_site_setup.ipynb`

1. **Download** — concat requested variables, `dropna()`. Temperature additionally derives `TMEAN`/`diff` when both `TMIN` and `TMAX` are present.
2. **Completeness filter** — `filter_by_time_completeness` with `month_threshold = year_threshold = completeness_threshold` (default 0.75), applied independently to the temperature pickle and the rainfall pickle. Months with < 75% of calendar days observed are dropped; years with < 75% of valid months are dropped.

Rainfall notebooks `b_Consecutive_dry_days.ipynb` and `c_Heavy_rainfall.ipynb` do not apply any additional per-notebook completeness filter — the shared `00_site_setup.ipynb` filter is the only one.

### Hard rules

- Always attribute sources in narrative outputs ("Source: GHCN-Daily station <id>", "Source: NOAA ONI").
- Never invent GHCN station IDs; resolve via site config and `GHCN.get_country_code`.
- Always state units: **mm**, **mm/day**, **mm/year**, **°C**, **°C/decade**, **days/year**.
- Never present user-uploaded data as primary without explicit user instruction.
