## Skill: Data Sources & Attribution

### Daily precipitation — GHCN-Daily (NOAA NCEI)

- **Country lookup**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-countries.txt` → `GHCN.download_country_codes()`.
- **Station inventory**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt` → `GHCN.download_stations_info()`.
- **Element inventory**: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt` → `GHCN.download_station_inventory()`.
- **Per-station daily CSVs**: `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/<station_id>.csv`.
- **Variable in use**: `PRCP` — daily precipitation total, stored in tenths of mm; downloader divides by 10.
- **Units after conversion**: daily rainfall **mm/day**; annual accumulated rainfall **mm/year**.
- **Sentinels**: `-9999` → NaN inside `extract_dict_data_var`.
- **Documentation**: `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/doc/GHCND_documentation.pdf`.
- **Citation**: Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012. *An overview of the Global Historical Climatology Network-Daily Database.* J. Atmos. Oceanic Technol., 29, 897-910.

### ENSO — NOAA ONI (notebook `a` only)

- **URL**: `https://psl.noaa.gov/data/correlation/oni.data`.
- **Format**: monthly Niño 3.4 anomalies. `-99.9` → NaN (`download_oni_index`).
- **Classification** (via `add_oni_cat` in `ind_setup`):
  - El Niño: ONI ≥ 0.5 (5 consecutive months for official events; plotting uses monthly categories).
  - La Niña: ONI ≤ −0.5.
  - Neutral otherwise.
- **Colours**: El Niño = red, La Niña = blue, Neutral = gray.
- **Citation**: NOAA Climate Prediction Center / Physical Sciences Laboratory.

### Reference periods

- Climatology baseline for anomalies: **1961–1990** (WMO standard), stored in site config as `reference_period_start` / `reference_period_end`.
- In code, slice with `.loc[ref_start:ref_end]` — never pass `"1961:1990"` as a single label to `.loc` on a DatetimeIndex.

### QC applied in `00_site_setup.ipynb`

1. **Download** — concat `PRCP`, `dropna()`.
2. **Completeness filter** — `filter_by_time_completeness` with `month_threshold = year_threshold = completeness_threshold` (default 0.75). Months with < 75% of calendar days observed are dropped; years with < 75% of valid months are dropped.

Notebooks `b` and `c` additionally filter to years with ≥ 300 daily observations before consecutive-dry and heavy-rainfall metrics.

### Hard rules

- Always attribute sources in narrative outputs ("Source: GHCN-Daily station <id>", "Source: NOAA ONI").
- Never invent GHCN station IDs; resolve via site config and `GHCN.get_country_code`.
- Always state units: **mm**, **mm/day**, **mm/year**, **days/year**.
- Never present user-uploaded data as primary without explicit user instruction.
