# Air temperature

Surface air temperature is a primary measure of climate change. It is influenced by solar radiation, greenhouse gases and land-use change, and it affects human health, agriculture and energy demand for cooling (USGCRP, 2017; IPCC, 2021).

Observations come from meteorological stations, ships, buoys and satellites. Temperature is typically described through **mean**, **minimum** and **maximum** values. Common extremes indicators include the number of **hot days** and **cold nights**, as well as heat-index or wet-bulb metrics of human comfort.

Because of the moderating influence of the ocean, many Pacific Island sites have a small annual temperature range (on the order of 1 °C; Miles et al., 2020). Even modest warming increases heat stress and cooling needs, especially when humidity is high.

## Notebooks in this section

| Notebook | Indicator |
|---|---|
| [`../00_site_setup.ipynb`](../00_site_setup.ipynb) | Define the site, download and cache GHCN `TMIN` / `TMAX` (and `PRCP` for the rainfall notebooks) |
| `a_mean_temperature.ipynb` | Annual mean temperature, anomalies and ENSO (ONI) |
| `b_min_max_temperature.ipynb` | Annual TMIN / TMAX and diurnal range |
| `c_hot_cold_days.ipynb` | Hot days (TX90p) and cold nights (TN10p) |

Run [`../00_site_setup.ipynb`](../00_site_setup.ipynb) first — it is shared with the `rainfall/` notebooks, one level up in `notebooks/historical/`. Analysis notebooks load the cached pickle and site JSON — they do not re-download data.

**Hot days / cold nights:** hot days exceed the 90th percentile of daily maximum temperature for that calendar day in 1961–1990; cold nights fall below the 10th percentile of daily minimum temperature for that calendar day in the same period.
