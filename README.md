# PICCM Atmosphere

Historical **rainfall** and **air-temperature** indicators for the Pacific Islands Climate Change Monitor (PICCM).

This repository merges the former `PICCM_Rainfall` and `PICCM_AirTemp` workflows into one place. Shared helpers and conventions follow the more recent rainfall layout; site setup is a single shared notebook, and indicator-specific modules and notebooks stay separate per domain.

## Notebooks

| Path | Purpose |
|---|---|
| `notebooks/historical/00_site_setup.ipynb` | **Shared** site setup — pick a country/station once, download and cache `TMIN`/`TMAX` and `PRCP` for it |
| `notebooks/historical/rainfall/` | Total rainfall, dry spells, heavy rainfall, regional maps |
| `notebooks/historical/air_temperature/` | Mean / min–max temperature, hot days and cold nights |

Run `notebooks/historical/00_site_setup.ipynb` once per new site — it is a sibling of both indicator folders, not inside either one. It saves a single `data/sites/<site_key>.json` (`site_key` = `<country_slug>_<ghcn_station_id>`, e.g. `palau_PSW00040309`) used by every analysis notebook in both domains, plus whichever of `data/air_temp/GHCN_<id>.pkl` / `data/rainfall/GHCN_<id>.pkl` the station actually reports. Analysis notebooks set `site_key` and load the cached pickle and site JSON — they never re-download data. Call `list_available_sites(...)` (from `air_temp.py` or `rainfall.py`) to list already-configured sites before picking one.

## Functions (`functions/`)

| Module | Role |
|---|---|
| `rainfall.py` | Rainfall site config I/O (`load_site_config`, `site_config_filename`, `list_available_sites`), output paths, dry-spell metrics |
| `rainfall_regional.py` | Regional rainfall maps and multi-station helpers |
| `air_temp.py` | Air-temperature site config I/O (same site-config API as `rainfall.py`), output paths, temperature helpers |
| `temp_func.py` | ETCCDI TX90p / TN10p and related percentile helpers |
| `data_downloaders.py` | GHCN-Daily downloaders, ONI index, completeness filter |

`rainfall.py` and `air_temp.py` implement an identical site-config API (`save_site_config`, `load_site_config`, `site_config_filename`, `list_available_sites`, `build_site_tag`, ...) so either module can read/write the shared `data/sites/<site_key>.json` files produced by `00_site_setup.ipynb`.

## Data and outputs

```
data/
├── sites/<site_key>.json          # shared site configuration (both domains)
├── rainfall/GHCN_<id>.pkl         # cleaned daily PRCP, if the station reports it
└── air_temp/GHCN_<id>.pkl         # cleaned daily TMIN/TMAX, if the station reports it

outputs/
├── figures/<site_tag>/            # PNG and HTML figures
└── tables/<site_tag>/             # CSV tables and JSON metrics
```

A station may only report one of the two domains — `00_site_setup.ipynb` skips (with a warning) whichever pickle isn't available rather than failing.

## Assistant documentation

See `assistant/` for CIndRA / CIRA training material (role definition, per-notebook skills, functions API). `assistant/skills/site_setup.md` documents the shared `00_site_setup.ipynb` skill used by both assistants; rainfall skills and shared conventions are otherwise the baseline, and air-temperature skills cover the temperature notebooks.
