"""Regional (multi-station) Pacific map helpers.

Everything needed to go from the GHCN station dictionary built by
``01_regional_setup.ipynb`` to a Pacific EEZ map: per-station rainfall/
temperature indicators, the shared ``RegionalMapConfig``-driven trend/mean
map machinery, and ERA5 background fields (with NetCDF caching, since
pulling+aggregating a global monthly ERA5 field over the network is slow).

Despite the filename, this module is used by both
``Regional/rainfall/compute_regional_indicators.ipynb`` and
``Regional/air_temperature/compute_regional_indicators.ipynb`` -- it grew out
of an EEZ-mapping module originally written for CIPSAP station CSVs (hence
``EEZ_LABEL_MAP``, ``create_pacific_base_map``, the ERA5 helpers), then picked
up the GHCN-specific indicator functions on top. The CIPSAP CSV loaders this
repo never used (``data/cipsap/`` doesn't exist here) have been removed --
see git history if a CIPSAP monthly/annual CSV loader is needed again.

Three parallel families of functions:

- **Indicators**: ``compute_regional_rainfall_indicators`` /
  ``compute_regional_temperature_indicators`` (station dict -> per-station
  annual DataFrames), mirroring the National single-site notebooks'
  per-year formulas.
- **Station-only maps**: ``RegionalMapConfig`` + ``build_sites_map_dataframe``
  + ``plot_annual_regional_map`` (generic: pass any annual-indicator column
  as ``variable``).
- **ERA5-background maps**: ``plot_monthly_rainfall_with_era5_background`` /
  ``plot_monthly_temperature_with_era5_background`` (grid field masked to the
  EEZs, station points overlaid), plus ``load_or_compute_era5_annual_rainfall``
  / ``load_or_compute_era5_annual_temperature`` for NetCDF caching and
  ``plot_era5_eez_temperature_anomaly`` for an EEZ area-weighted anomaly time
  series. Only indicators reconstructable from *monthly* ERA5 fields have an
  ERA5 counterpart (annual accumulated rainfall, annual mean temperature) --
  anything needing daily data (dry-day counts, hot/cold days, diurnal range)
  is GHCN-station-only.
"""

from __future__ import annotations

from dataclasses import dataclass
import glob
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cartopy.mpl.geoaxes import GeoAxes
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from scipy import stats

EEZ_LABEL_MAP = {
    "Northern Mariana Islands and Guam": "Guam & N. Mariana",
    "Howland Island and Baker Island": "Howland & Baker Isl.",
    "Marshall Islands": "Marshall Is.",
    "Solomon Islands": "Solomon Is.",
    "French Polynesia": "French Polynesia",
    "Papua New Guinea": "Papua New Guinea",
    "Wallis and Futuna": "Wallis & Futuna",
    "American Samoa": "American Samoa",
    "Cook Islands": "Cook Is.",
}

PACIFIC_EXTENT = (125, 245, -35, 45)
MONTHLY_VARIABLES = ("RAIN", "TMAX", "TMIN", "TMEAN")
SIGNIFICANCE_NOTE = (
    "Circles with 'x' represent trends statistically significant at the 95% level."
)


@dataclass
class RegionalMapConfig:
    """Configuration for a regional CIPSAP map."""

    variable: str
    metric: str = "trend"  # "mean" or "trend"
    period_start: int = 1951
    period_end: int = 2020
    significance_level: float = 0.05
    missing_value: float = -99.9
    trend_as_percent: bool = False
    min_months_per_year: int = 10
    min_years: int = 2  # a "trend" fit through fewer years than this is reported as NaN
    cmap: str | None = None
    vmin: float | None = None
    vmax: float | None = None
    color_label: str | None = None


def load_pacific_eez(data_dir: str | Path) -> gpd.GeoDataFrame:
    data_dir = Path(data_dir)
    shp = glob.glob(str(data_dir / "Pacific_EEZs" / "*.shp"))[0]
    return gpd.read_file(shp)


RAINFALL_INDICATOR_LABELS = {
    "total_annual_mm": "total annual rainfall",
    "dry_days": "number of dry days (<1 mm)",
    "wet_days": "number of wet days (>1 mm)",
    "max_consecutive_dry_days": "maximum consecutive dry days",
    "mean_consecutive_dry_days": "mean consecutive dry days",
    "heavy_days": "days above the station's 95th percentile",
}

RAINFALL_INDICATOR_UNITS = {
    "total_annual_mm": "mm / decade",
    "dry_days": "days / decade",
    "wet_days": "days / decade",
    "max_consecutive_dry_days": "days / decade",
    "mean_consecutive_dry_days": "days / decade",
    "heavy_days": "days / decade",
}


def _station_rainfall_indicators(
    daily_df: pd.DataFrame,
    dry_wet_threshold_mm: float = 1.0,
    heavy_percentile: float = 95,
    min_year_completeness: float = 0.75,
) -> tuple[pd.DataFrame, float]:
    """Per-station annual rainfall indicators, mirroring the National rainfall notebooks.

    Reproduces, column for column, what ``a_Total_rainfall.ipynb``,
    ``b_Consecutive_dry_days.ipynb`` and ``c_Heavy_rainfall.ipynb`` compute for a
    single site, so the same numbers underlie both the per-site notebooks and the
    regional maps built from ``compute_regional_rainfall_indicators``.

    ``min_year_completeness`` guards ``total_annual_mm`` in particular:
    ``01_regional_setup.ipynb`` applies its completeness filter to the merged
    TMIN/TMAX/PRCP frame, so a year can pass on temperature coverage alone
    while PRCP itself has only a handful of real observations that year. Since
    ``total_annual_mm`` extrapolates via ``sum / count * 365``, a year with
    e.g. 5 real PRCP days would inflate to an absurd annual total. Years where
    fewer than ``min_year_completeness`` of calendar days have a non-null
    PRCP value are dropped from every indicator here, independent of whatever
    the upstream (multi-variable) completeness filter already did.

    Returns ``(annual_df, heavy_threshold_mm)``: ``annual_df`` has a ``Year``
    column plus ``total_annual_mm``, ``dry_days``, ``wet_days``,
    ``max_consecutive_dry_days``, ``mean_consecutive_dry_days``, ``heavy_days``
    (one row per calendar year with sufficient PRCP coverage); ``heavy_threshold_mm``
    is the station's own 95th-percentile daily rainfall, computed once over its
    full record (matching ``c_Heavy_rainfall.ipynb``).
    """
    from rainfall import count_consecutive_days

    prcp = daily_df[["PRCP"]].copy()

    prcp_days_present = prcp["PRCP"].notna().groupby(prcp.index.year).sum()
    days_in_year = pd.Series(
        {year: pd.Timestamp(year=int(year), month=12, day=31).dayofyear for year in prcp_days_present.index}
    )
    complete_years = prcp_days_present.index[
        (prcp_days_present / days_in_year) >= min_year_completeness
    ]

    # a_Total_rainfall.ipynb: count-normalised annual accumulation.
    total_annual_mm = (
        prcp.groupby(prcp.index.year).sum()["PRCP"]
        / prcp.groupby(prcp.index.year).count()["PRCP"]
    ) * 365

    # b_Consecutive_dry_days.ipynb: dry-day count, computed before dropna (as in the notebook).
    wet_day_t = np.where(prcp["PRCP"] > dry_wet_threshold_mm, 1, np.where(prcp["PRCP"].isna(), np.nan, 0))
    dry_rows = prcp.loc[wet_day_t == 0]
    dry_days = dry_rows.groupby(dry_rows.index.year).count()["PRCP"]

    # b_Consecutive_dry_days.ipynb: consecutive dry-day runs, computed after dropna (as in the notebook).
    prcp_valid = prcp.dropna()

    # Unlike the single-site notebook, a regional station can have multi-year
    # reporting gaps (e.g. a decades-old paper record digitized in separate
    # batches). Running count_consecutive_days directly on prcp_valid.dropna()
    # would silently treat the last dry day before a gap and the first dry day
    # after it as adjacent, "stitching" unrelated dry spells into one absurd
    # run (observed: a single-year value of 2637 consecutive dry days). Reindex
    # to the full daily calendar range first so a missing day breaks the run
    # (NaN -> not-dry), then only average over actually-observed days so the
    # mean keeps its original meaning.
    full_range = pd.date_range(prcp.index.min(), prcp.index.max(), freq="D")
    prcp_daily = prcp.reindex(full_range)
    below_threshold_daily = prcp_daily["PRCP"] < dry_wet_threshold_mm
    consecutive_days_daily = pd.Series(count_consecutive_days(below_threshold_daily), index=full_range)

    observed_mask = prcp_daily["PRCP"].notna()
    consecutive_days_observed = consecutive_days_daily[observed_mask]

    max_consecutive_dry_days = consecutive_days_daily.groupby(full_range.year).max()
    mean_consecutive_dry_days = consecutive_days_observed.groupby(consecutive_days_observed.index.year).mean()

    # c_Heavy_rainfall.ipynb: wet-day count and heavy-rainfall day count (post-dropna).
    wet_rows = prcp_valid.loc[prcp_valid["PRCP"] > dry_wet_threshold_mm]
    wet_days = wet_rows.groupby(wet_rows.index.year).count()["PRCP"]

    heavy_threshold_mm = float(np.round(np.percentile(prcp_valid["PRCP"], heavy_percentile), 2))
    heavy_rows = prcp_valid.loc[prcp_valid["PRCP"] > heavy_threshold_mm]
    heavy_days = heavy_rows.groupby(heavy_rows.index.year).count()["PRCP"]

    annual_df = pd.DataFrame({
        "total_annual_mm": total_annual_mm,
        "dry_days": dry_days,
        "wet_days": wet_days,
        "max_consecutive_dry_days": max_consecutive_dry_days,
        "mean_consecutive_dry_days": mean_consecutive_dry_days,
        "heavy_days": heavy_days,
    })
    annual_df = annual_df.loc[annual_df.index.isin(complete_years)]
    annual_df.index.name = "Year"
    return annual_df.reset_index(), heavy_threshold_mm


def compute_regional_rainfall_indicators(
    stations_data: dict,
    dry_wet_threshold_mm: float = 1.0,
    heavy_percentile: float = 95,
    min_year_completeness: float = 0.75,
) -> tuple[dict, dict, dict]:
    """Compute the National rainfall indicators for every station in a regional dict.

    ``stations_data`` is the dictionary produced by ``01_regional_setup.ipynb``
    (``{station_id: {..., "lat", "lon", "data": daily DataFrame with a PRCP column}}``,
    typically loaded back from ``data/regional/<region_key>_stations.pkl``).
    Stations without a usable ``PRCP`` column are skipped.

    ``min_year_completeness`` (see :func:`_station_rainfall_indicators`) drops
    any year where fewer than this fraction of calendar days have a real PRCP
    observation, independent of ``01_regional_setup.ipynb``'s own (TMIN/TMAX/PRCP
    merged) completeness filter -- this prevents ``total_annual_mm`` from
    extrapolating a handful of PRCP days up to an absurd annual figure.

    Returns ``(dict_lon_lat, annual_data, heavy_thresholds)``:

    - ``dict_lon_lat`` / ``annual_data`` plug directly into
      ``build_sites_map_dataframe`` / ``plot_annual_regional_map`` — pass
      ``variable`` as one of the keys in :data:`RAINFALL_INDICATOR_LABELS`.
    - ``heavy_thresholds`` maps ``station_id`` to its 95th-percentile daily
      rainfall threshold (mm).
    """
    dict_lon_lat = {}
    annual_data = {}
    heavy_thresholds = {}

    for station_id, station in stations_data.items():
        daily_df = station.get("data")
        if daily_df is None or "PRCP" not in daily_df.columns or daily_df["PRCP"].dropna().empty:
            continue

        annual_df, heavy_threshold_mm = _station_rainfall_indicators(
            daily_df, dry_wet_threshold_mm=dry_wet_threshold_mm, heavy_percentile=heavy_percentile,
            min_year_completeness=min_year_completeness,
        )
        annual_data[station_id] = annual_df
        heavy_thresholds[station_id] = heavy_threshold_mm
        dict_lon_lat[station_id] = {"lat": station["lat"], "lon": station["lon"]}

    return dict_lon_lat, annual_data, heavy_thresholds


TEMPERATURE_INDICATOR_LABELS = {
    "tmean_annual": "mean annual temperature",
    "tmin_annual": "mean annual minimum temperature",
    "tmax_annual": "mean annual maximum temperature",
    "diff_annual": "mean annual diurnal temperature range",
    "hot_days_pct": "hot days (> station's 90th percentile)",
    "cold_nights_pct": "cold nights (< station's 10th percentile)",
}

TEMPERATURE_INDICATOR_UNITS = {
    "tmean_annual": "°C / decade",
    "tmin_annual": "°C / decade",
    "tmax_annual": "°C / decade",
    "diff_annual": "°C / decade",
    "hot_days_pct": "% / decade",
    "cold_nights_pct": "% / decade",
}


def _year_completeness_mask(daily_series: pd.Series, min_year_completeness: float) -> pd.Index:
    """Years where ``daily_series`` has at least ``min_year_completeness`` of calendar days present."""
    days_present = daily_series.notna().groupby(daily_series.index.year).sum()
    days_in_year = pd.Series(
        {year: pd.Timestamp(year=int(year), month=12, day=31).dayofyear for year in days_present.index}
    )
    return days_present.index[(days_present / days_in_year) >= min_year_completeness]


def _station_temperature_indicators(
    daily_df: pd.DataFrame,
    reference_period_start: int = 1961,
    reference_period_end: int = 1990,
    min_year_completeness: float = 0.75,
) -> tuple[pd.DataFrame, dict]:
    """Per-station annual temperature indicators, mirroring the National air-temperature notebooks.

    Reproduces ``a_mean_temperature.ipynb`` (``tmean_annual``),
    ``b_min_max_temperature.ipynb`` (``tmin_annual``, ``tmax_annual``,
    ``diff_annual``) and the **fixed-percentile companion metric** from
    ``c_hot_cold_days.ipynb`` (``hot_days_pct``, ``cold_nights_pct``): a single
    station-wide 90th/10th percentile threshold of ``TMAX``/``TMIN`` over the
    reference period, not the full calendar-day ETCCDI TX90p/TN10p climatology.
    The ETCCDI method (``functions/temp_func.py``) estimates a percentile per
    calendar day from a centred 5-day window scanned with nested Python loops
    over the whole base period -- fine for one station, far too slow to run
    for a few hundred. The fixed-percentile variant is the same simplification
    ``c_hot_cold_days.ipynb`` itself offers as "a simpler companion metric".

    ``min_year_completeness`` mirrors ``_station_rainfall_indicators``: each
    indicator's source column (``TMEAN``/``TMIN``/``TMAX``) is masked to NaN
    for any year where fewer than this fraction of calendar days have a real
    observation for *that* column -- a station can report TMAX far more
    consistently than TMIN (or vice versa), so completeness is evaluated per
    variable rather than once for the whole station.

    Returns ``(annual_df, thresholds)``: ``annual_df`` has a ``Year`` column
    plus ``tmean_annual``, ``tmin_annual``, ``tmax_annual``, ``diff_annual``
    (°C) and ``hot_days_pct``, ``cold_nights_pct`` (percent of days in the
    year, 0-100); ``thresholds`` is ``{"tmax_q90": ..., "tmin_q10": ...}``,
    the station's own reference-period thresholds (°C).
    """
    cols = [c for c in ("TMIN", "TMAX", "TMEAN", "diff") if c in daily_df.columns]
    temp = daily_df[cols].copy()
    if "TMEAN" not in temp.columns and {"TMIN", "TMAX"}.issubset(temp.columns):
        temp["TMEAN"] = (temp["TMAX"] + temp["TMIN"]) / 2
    if "diff" not in temp.columns and {"TMIN", "TMAX"}.issubset(temp.columns):
        temp["diff"] = temp["TMAX"] - temp["TMIN"]

    annuals = {}

    if "TMEAN" in temp.columns:
        series = temp["TMEAN"].groupby(temp.index.year).mean()
        annuals["tmean_annual"] = series.loc[series.index.isin(_year_completeness_mask(temp["TMEAN"], min_year_completeness))]
    if "TMIN" in temp.columns:
        series = temp["TMIN"].groupby(temp.index.year).mean()
        annuals["tmin_annual"] = series.loc[series.index.isin(_year_completeness_mask(temp["TMIN"], min_year_completeness))]
    if "TMAX" in temp.columns:
        series = temp["TMAX"].groupby(temp.index.year).mean()
        annuals["tmax_annual"] = series.loc[series.index.isin(_year_completeness_mask(temp["TMAX"], min_year_completeness))]
    if "diff" in temp.columns:
        series = temp["diff"].groupby(temp.index.year).mean()
        complete_diff_years = _year_completeness_mask(temp["TMIN"], min_year_completeness).intersection(
            _year_completeness_mask(temp["TMAX"], min_year_completeness)
        )
        annuals["diff_annual"] = series.loc[series.index.isin(complete_diff_years)]

    thresholds = {"tmax_q90": None, "tmin_q10": None}
    ref = temp.loc[str(reference_period_start):str(reference_period_end)]

    if "TMAX" in temp.columns and ref["TMAX"].notna().sum() >= 30:
        tmax_q90 = float(ref["TMAX"].quantile(0.9))
        thresholds["tmax_q90"] = tmax_q90
        hot = (temp["TMAX"] > tmax_q90).astype(float)
        hot[temp["TMAX"].isna()] = np.nan
        hot_pct = hot.groupby(temp.index.year).mean() * 100
        annuals["hot_days_pct"] = hot_pct.loc[hot_pct.index.isin(_year_completeness_mask(temp["TMAX"], min_year_completeness))]

    if "TMIN" in temp.columns and ref["TMIN"].notna().sum() >= 30:
        tmin_q10 = float(ref["TMIN"].quantile(0.1))
        thresholds["tmin_q10"] = tmin_q10
        cold = (temp["TMIN"] < tmin_q10).astype(float)
        cold[temp["TMIN"].isna()] = np.nan
        cold_pct = cold.groupby(temp.index.year).mean() * 100
        annuals["cold_nights_pct"] = cold_pct.loc[cold_pct.index.isin(_year_completeness_mask(temp["TMIN"], min_year_completeness))]

    annual_df = pd.DataFrame(annuals)
    annual_df.index.name = "Year"
    return annual_df.reset_index(), thresholds


def compute_regional_temperature_indicators(
    stations_data: dict,
    reference_period_start: int = 1961,
    reference_period_end: int = 1990,
    min_year_completeness: float = 0.75,
) -> tuple[dict, dict, dict]:
    """Compute the National air-temperature indicators for every station in a regional dict.

    ``stations_data`` is the dictionary produced by ``01_regional_setup.ipynb``
    (``{station_id: {..., "lat", "lon", "data": daily DataFrame with TMIN/TMAX
    columns}}``, typically loaded back from ``data/regional/<region_key>_stations.pkl``).
    Stations without usable TMIN/TMAX data are skipped.

    Returns ``(dict_lon_lat, annual_data, thresholds)``:

    - ``dict_lon_lat`` / ``annual_data`` plug directly into
      ``build_sites_map_dataframe`` / ``plot_annual_regional_map`` — pass
      ``variable`` as one of the keys in :data:`TEMPERATURE_INDICATOR_LABELS`.
    - ``thresholds`` maps ``station_id`` to ``{"tmax_q90", "tmin_q10"}`` (°C).
    """
    dict_lon_lat = {}
    annual_data = {}
    thresholds = {}

    for station_id, station in stations_data.items():
        daily_df = station.get("data")
        has_temp = daily_df is not None and ({"TMIN", "TMAX"} & set(daily_df.columns))
        if not has_temp:
            continue
        if daily_df[[c for c in ("TMIN", "TMAX") if c in daily_df.columns]].dropna(how="all").empty:
            continue

        annual_df, station_thresholds = _station_temperature_indicators(
            daily_df,
            reference_period_start=reference_period_start,
            reference_period_end=reference_period_end,
            min_year_completeness=min_year_completeness,
        )
        annual_data[station_id] = annual_df
        thresholds[station_id] = station_thresholds
        dict_lon_lat[station_id] = {"lat": station["lat"], "lon": station["lon"]}

    return dict_lon_lat, annual_data, thresholds


def compute_regional_temperature_anomaly_series(
    annual_data: dict[str, pd.DataFrame],
    reference_period_start: int = 1961,
    reference_period_end: int = 1990,
    variable: str = "tmean_annual",
    smooth_years: int = 5,
) -> tuple[pd.Series, pd.Series]:
    """Regional-mean annual temperature anomaly across stations (Figure-7 style).

    For each station, subtracts that station's own reference-period mean from
    its annual series (so stations at very different absolute temperatures
    contribute comparable anomalies), then takes a simple unweighted average
    across stations for each year -- not an area-weighted spatial mean like
    ``plot_era5_eez_temperature_anomaly`` computes for the ERA5 grid, just a
    station average, since GHCN stations aren't a regular grid.

    Returns ``(annual_anomaly, smoothed)`` -- ``smoothed`` is the centred
    ``smooth_years`` rolling mean, matching the dashed line in Figure 7.
    """
    anomalies = []
    for df in annual_data.values():
        if variable not in df.columns:
            continue
        series = df.set_index("Year")[variable].dropna()
        ref_mean = series.loc[
            (series.index >= reference_period_start) & (series.index <= reference_period_end)
        ].mean()
        if pd.isna(ref_mean):
            continue
        anomalies.append(series - ref_mean)

    if not anomalies:
        empty = pd.Series(dtype=float)
        return empty, empty

    combined = pd.concat(anomalies, axis=1)
    annual_anomaly = combined.mean(axis=1).sort_index()
    smoothed = annual_anomaly.rolling(window=smooth_years, center=True, min_periods=1).mean()
    return annual_anomaly, smoothed


def load_or_compute_era5_annual_temperature(
    era5_ds,
    cache_path: str | Path,
    metric: str,
    period_start: int = 1951,
    period_end: int = 2020,
    temp_var: str = "t2m",
    force_recompute: bool = False,
):
    """Compute the ERA5 annual-temperature mean/trend field, cached as NetCDF.

    Same caching pattern as :func:`load_or_compute_era5_annual_rainfall` --
    see that function's docstring for the rationale and cache-hit behaviour.
    """
    import xarray as xr

    try:
        import h5netcdf  # noqa: F401
        netcdf_engine = "h5netcdf"
    except ImportError:
        netcdf_engine = None

    cache_path = Path(cache_path)
    if cache_path.exists() and not force_recompute:
        return xr.open_dataarray(cache_path, engine=netcdf_engine)

    if metric == "trend":
        field = compute_era5_annual_temperature_trend(
            era5_ds, period_start=period_start, period_end=period_end, temp_var=temp_var,
        )
    elif metric == "mean":
        field = compute_era5_annual_mean_temperature(
            era5_ds, period_start=period_start, period_end=period_end, temp_var=temp_var,
        )
    else:
        raise ValueError("metric must be 'mean' or 'trend'")

    field = field.load()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    field.to_netcdf(cache_path, engine=netcdf_engine)
    return field


def _prepare_year_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "Year" in out.columns:
        return out
    if out.index.name == "Year":
        return out.reset_index()
    if "year" in out.columns:
        return out.rename(columns={"year": "Year"})
    if out.index.name == "year":
        return out.reset_index().rename(columns={"year": "Year"})
    return out


def compute_linear_trend_per_decade(years: pd.Series, values: pd.Series) -> dict:
    mask = values.notna()
    if mask.sum() < 2:
        return {"value": np.nan, "p_value": np.nan, "n_years": int(mask.sum())}

    slope, _, _, p_value, _ = stats.linregress(years[mask], values[mask])
    return {
        "value": float(slope * 10),
        "p_value": float(p_value),
        "n_years": int(mask.sum()),
    }


def _compute_metric_from_series(
    series: pd.Series,
    metric: str,
    trend_as_percent: bool = False,
    min_years: int = 2,
) -> dict:
    values = series.dropna()
    if metric == "mean":
        return {
            "value": float(values.mean()) if len(values) else np.nan,
            "p_value": np.nan,
            "n_years": int(len(values)),
        }

    if len(values) < min_years:
        # A linear fit through very few points is a near-perfect (and
        # meaningless) line -- e.g. exactly 2 years always gives p=0.0 and can
        # produce an enormous slope that then dominates a map's colour scale.
        return {"value": np.nan, "p_value": np.nan, "n_years": int(len(values))}

    years = pd.Series(values.index.astype(float).values)
    vals = pd.Series(values.values)
    result = compute_linear_trend_per_decade(years, vals)
    if trend_as_percent and metric == "trend" and values.mean() != 0 and not np.isnan(result["value"]):
        result["value"] = float((result["value"] / 10) / values.mean() * 100 * 10)
    return result


def _annual_series_from_annual_df(
    annual_df: pd.DataFrame,
    variable: str,
    config: RegionalMapConfig,
) -> pd.Series:
    df = _prepare_year_df(annual_df)
    if variable not in df.columns or "Year" not in df.columns:
        return pd.Series(dtype=float)

    sub = df[(df["Year"] >= config.period_start) & (df["Year"] <= config.period_end)].copy()
    values = sub[variable].replace(config.missing_value, np.nan)
    return pd.Series(values.values, index=sub["Year"].values)


def _annual_series_from_monthly_df(
    monthly_df: pd.DataFrame,
    variable: str,
    config: RegionalMapConfig,
) -> pd.Series:
    if variable not in monthly_df.columns:
        return pd.Series(dtype=float)

    df = _prepare_year_df(monthly_df)
    if "Year" not in df.columns:
        return pd.Series(dtype=float)

    sub = df[(df["Year"] >= config.period_start) & (df["Year"] <= config.period_end)].copy()
    values = sub[variable].replace(config.missing_value, np.nan)
    counts = values.groupby(sub["Year"]).count()

    if variable == "RAIN":
        annual = values.groupby(sub["Year"]).sum(min_count=1)
    else:
        annual = values.groupby(sub["Year"]).mean()

    annual[counts < config.min_months_per_year] = np.nan
    return annual


def build_sites_map_dataframe(
    dict_lon_lat: dict,
    config: RegionalMapConfig,
    annual_data: dict[str, pd.DataFrame] | None = None,
    monthly_data: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Build station table with mean or trend for one variable."""
    records = []
    for site, coords in dict_lon_lat.items():
        if annual_data is not None:
            station_df = annual_data.get(site)
            series = _annual_series_from_annual_df(station_df, config.variable, config) if station_df is not None else pd.Series(dtype=float)
        elif monthly_data is not None:
            station_df = monthly_data.get(site)
            series = _annual_series_from_monthly_df(station_df, config.variable, config) if station_df is not None else pd.Series(dtype=float)
        else:
            series = pd.Series(dtype=float)

        metric = _compute_metric_from_series(series, config.metric, config.trend_as_percent, min_years=config.min_years)
        records.append({"site": site, "lat": coords["lat"], "lon": coords["lon"], **metric})

    sites_df = pd.DataFrame(records)
    if config.metric == "trend":
        sites_df["significant"] = sites_df["p_value"] < config.significance_level
    else:
        sites_df["significant"] = False
    return sites_df


def _map_style(
    sites_df: pd.DataFrame,
    config: RegionalMapConfig,
    variable_labels: dict | None = None,
    source: str = "annual",
) -> dict:
    variable_labels = variable_labels or {}
    label = variable_labels.get(config.variable, config.variable)

    if config.metric == "trend":
        vals = sites_df["value"].dropna()
        lim = max(abs(vals.min()), abs(vals.max())) if len(vals) else 1
        vmin = -lim if config.vmin is None else config.vmin
        vmax = lim if config.vmax is None else config.vmax
        if config.trend_as_percent:
            color_label = config.color_label or "% / decade"
        elif config.variable == "RAIN" and source == "monthly":
            color_label = config.color_label or "mm / decade"
        elif config.variable in {"cdd", "cwd"}:
            color_label = config.color_label or "days / decade"
        elif config.variable in {"r95p", "r99p", "rx1day"}:
            color_label = config.color_label or "mm / decade"
        else:
            color_label = config.color_label or "units / decade"
        title = f"Trend in {label.lower()} over {config.period_start}–{config.period_end}"
        cmap = config.cmap or ("RdBu_r" if config.trend_as_percent else "BrBG")
    else:
        vmin = sites_df["value"].min() if config.vmin is None else config.vmin
        vmax = sites_df["value"].max() if config.vmax is None else config.vmax
        color_label = config.color_label or label
        title = f"Mean {label.lower()} ({config.period_start}–{config.period_end})"
        cmap = config.cmap or "YlOrRd"

    return {
        "cmap": cmap,
        "vmin": vmin,
        "vmax": vmax,
        "color_label": color_label,
        "title": title,
    }


def create_pacific_base_map(
    data_dir: str | Path,
    figsize: tuple[float, float] = (14, 9),
    extent: tuple[float, float, float, float] = PACIFIC_EXTENT,
    label_fontsize: int = 9,
    show_eez_labels: bool = True,
    eez_facecolor: str = "#8fc4e8",
    eez_alpha: float = 0.35,
):
    """Create the Pacific EEZ base map. Returns (fig, ax, eez_gdf)."""
    eez_gdf = load_pacific_eez(data_dir)

    fig = plt.figure(figsize=figsize)
    ax = plt.axes(projection=ccrs.PlateCarree(central_longitude=180))
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.set_facecolor("#c6dce8")

    eez_gdf.plot(
        ax=ax,
        transform=ccrs.PlateCarree(),
        facecolor=eez_facecolor,
        edgecolor="#1b4f72",
        linewidth=0.6,
        alpha=eez_alpha,
        zorder=2,
    )

    ax.add_feature(cfeature.LAND, facecolor="lightgrey", edgecolor="lightgrey", linewidth=0.3, zorder=3)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor="#2d5a24", zorder=4)

    gl = ax.gridlines(draw_labels=True, linewidth=0.4, color="gray", alpha=0.5, linestyle="--")
    gl.top_labels = False
    gl.right_labels = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER

    if show_eez_labels:
        for _, row in eez_gdf.iterrows():
            pt = row.geometry.representative_point()
            eez_label = EEZ_LABEL_MAP.get(row["Country"], row["Country"])
            ax.text(
                pt.x,
                pt.y,
                eez_label,
                transform=ccrs.PlateCarree(),
                fontsize=label_fontsize,
                ha="center",
                va="center",
                color="black",
                zorder=5,
            )

    ax.text(180, 35, "NORTH PACIFIC OCEAN", transform=ccrs.PlateCarree(), fontsize=11, color="#1b4f72", ha="center", zorder=1)
    ax.text(180, -32, "SOUTH PACIFIC OCEAN", transform=ccrs.PlateCarree(), fontsize=11, color="#1b4f72", ha="center", zorder=1)

    return fig, ax, eez_gdf


def plot_regional_map(
    dict_lon_lat: dict,
    data_dir: str | Path,
    config: RegionalMapConfig,
    annual_data: dict[str, pd.DataFrame] | None = None,
    monthly_data: dict[str, pd.DataFrame] | None = None,
    variable_labels: dict | None = None,
    figsize: tuple[float, float] = (14, 9),
    label_fontsize: int = 9,
):
    """Plot mean or trend for one variable on the shared Pacific base map."""
    if (annual_data is None) == (monthly_data is None):
        raise ValueError("Provide exactly one of annual_data or monthly_data.")

    source = "annual" if annual_data is not None else "monthly"
    sites_df = build_sites_map_dataframe(
        dict_lon_lat,
        config,
        annual_data=annual_data,
        monthly_data=monthly_data,
    )
    style = _map_style(sites_df, config, variable_labels, source=source)

    fig, ax, _ = create_pacific_base_map(data_dir, figsize=figsize, label_fontsize=label_fontsize)
    plot_df = sites_df.dropna(subset=["value"])

    sc = ax.scatter(
        plot_df["lon"],
        plot_df["lat"],
        c=plot_df["value"],
        cmap=style["cmap"],
        vmin=style["vmin"],
        vmax=style["vmax"],
        s=90,
        edgecolors="black",
        linewidths=0.8,
        transform=ccrs.PlateCarree(),
        zorder=6,
    )

    if config.metric == "trend":
        sig_df = plot_df[plot_df["significant"]]
        if not sig_df.empty:
            ax.scatter(
                sig_df["lon"],
                sig_df["lat"],
                marker="x",
                c="black",
                s=55,
                linewidths=1.8,
                transform=ccrs.PlateCarree(),
                zorder=7,
                label="Significant at 95% level",
            )
        fig.text(0.5, 0.03, SIGNIFICANCE_NOTE, ha="center", fontsize=9, style="italic")

    cbar = fig.colorbar(sc, ax=ax, orientation="horizontal", pad=0.08, shrink=0.7, aspect=35)
    cbar.set_label(style["color_label"])
    ax.set_title(style["title"], fontsize=14, pad=12)

    if config.metric == "trend" and plot_df["significant"].any():
        ax.legend(loc="lower left", framealpha=0.9, fontsize=9)

    return fig, ax, sites_df


def plot_annual_regional_map(
    dict_lon_lat: dict,
    annual_data: dict[str, pd.DataFrame],
    data_dir: str | Path,
    config: RegionalMapConfig,
    variable_labels: dict | None = None,
    **kwargs,
):
    """Plot one annual index (dict_keys variables) on the Pacific base map."""
    return plot_regional_map(
        dict_lon_lat,
        data_dir,
        config,
        annual_data=annual_data,
        variable_labels=variable_labels,
        **kwargs,
    )


def _linregress_trend_per_decade(years: np.ndarray, values: np.ndarray) -> float:
    mask = np.isfinite(values)
    if mask.sum() < 2:
        return np.nan
    slope, _, _, _, _ = stats.linregress(years[mask], values[mask])
    return float(slope * 10)


def compute_era5_annual_rainfall_trend(
    era5_ds,
    period_start: int = 1951,
    period_end: int = 2020,
    precip_var: str = "tp",
    time_dim: str = "valid_time",
):
    """
    Compute annual-total rainfall trend (mm/decade) from ERA5 monthly precipitation.

    ERA5 ``tp`` is monthly accumulated precipitation in metres; annual totals are
    converted to millimetres before fitting the linear trend.
    """
    import xarray as xr

    precip = era5_ds[precip_var]
    if time_dim not in precip.dims:
        raise ValueError(f"Variable '{precip_var}' must contain dimension '{time_dim}'")

    sub = precip.sel({time_dim: slice(str(period_start), str(period_end))})
    annual = _annual_rainfall_mm_from_precip(sub, time_dim=time_dim)

    year_coord = "year" if "year" in annual.coords else f"{time_dim}.year"
    years = annual[year_coord].values.astype(float)

    # Trend regression needs the full annual time series in one chunk.
    if hasattr(annual.data, "chunks"):
        annual = annual.chunk({year_coord: -1})

    def _trend_for_gridcell(values: np.ndarray) -> float:
        return _linregress_trend_per_decade(years, values)

    trend = xr.apply_ufunc(
        _trend_for_gridcell,
        annual,
        input_core_dims=[[year_coord]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        dask_gufunc_kwargs={"allow_rechunk": True},
    )
    trend.name = "rainfall_trend_mm_decade"
    trend.attrs["units"] = "mm/decade"
    return trend


def _annual_rainfall_mm_from_precip(precip_sub, time_dim: str = "valid_time"):
    """Sum monthly precipitation to annual totals in mm."""
    annual = precip_sub.groupby(f"{time_dim}.year").sum(time_dim)
    units = str(annual.attrs.get("units", precip_sub.attrs.get("units", ""))).lower()
    if units not in {"mm", "millimetre", "millimeters"}:
        annual = annual * 1000.0
        annual.attrs["units"] = "mm"
    return annual


def compute_era5_annual_mean_rainfall(
    era5_ds,
    period_start: int = 1951,
    period_end: int = 2020,
    precip_var: str = "tp",
    time_dim: str = "valid_time",
):
    """Multi-year mean of annual total rainfall (mm) from ERA5 monthly ``tp``."""
    precip = era5_ds[precip_var]
    if time_dim not in precip.dims:
        raise ValueError(f"Variable '{precip_var}' must contain dimension '{time_dim}'")

    sub = precip.sel({time_dim: slice(str(period_start), str(period_end))})
    annual = _annual_rainfall_mm_from_precip(sub, time_dim=time_dim)
    year_coord = "year" if "year" in annual.coords else f"{time_dim}.year"
    mean_rain = annual.mean(year_coord)
    mean_rain.name = "annual_mean_rainfall_mm"
    mean_rain.attrs["units"] = "mm"
    return mean_rain


def _as_celsius_if_kelvin(values):
    """Convert ERA5 temperature to °C when still in Kelvin."""
    units = str(values.attrs.get("units", "")).lower()
    if units in {"c", "°c", "degc", "celsius"}:
        return values
    try:
        if float(values.mean()) > 150:
            return values - 273.15
    except Exception:
        pass
    return values


def _lon_to_180(lons: np.ndarray) -> np.ndarray:
    """Convert longitudes to -180..180."""
    return ((np.asarray(lons, dtype=float) + 180) % 360) - 180


def _lon_to_pacific_map(lons: np.ndarray, west: float = PACIFIC_EXTENT[0]) -> np.ndarray:
    """
    Express longitudes in the Pacific map frame (125–245°E).

    Matches CIPSAP station longitudes when plotted with central_longitude=180.
    """
    lons_180 = _lon_to_180(lons)
    return np.where(lons_180 < west, lons_180 + 360, lons_180)


def _prepare_era5_field_for_pacific_map(
    field,
    extent: tuple[float, float, float, float] = PACIFIC_EXTENT,
):
    """Subset and reorder an ERA5 lat/lon field to Pacific longitudes (125–245°E)."""
    west, east, south, north = extent
    da = field.sel(latitude=slice(north, south))

    lon_180 = _lon_to_180(da["longitude"].values)
    in_pacific = (lon_180 >= west) | (lon_180 <= east - 360)
    da = da.isel(longitude=in_pacific)

    lon_180 = lon_180[in_pacific]
    lon_plot = _lon_to_pacific_map(lon_180, west=west)
    sort_idx = np.argsort(lon_plot)

    da = da.isel(longitude=sort_idx)
    return da, lon_plot[sort_idx], lon_180[sort_idx], da["latitude"].values, da.values


# Backwards-compatible alias
_prepare_era5_trend_for_pacific_map = _prepare_era5_field_for_pacific_map


def compute_era5_annual_mean_temperature(
    era5_ds,
    period_start: int = 1951,
    period_end: int = 2020,
    temp_var: str = "t2m",
    time_dim: str = "valid_time",
):
    """
    Mean annual temperature (°C) from ERA5 monthly 2 m temperature.

    For each year the monthly ``t2m`` values are averaged, then the multi-year
    mean of those annual means is returned (Kelvin → Celsius).
    """
    temp = era5_ds[temp_var]
    if time_dim not in temp.dims:
        raise ValueError(f"Variable '{temp_var}' must contain dimension '{time_dim}'")

    sub = temp.sel({time_dim: slice(str(period_start), str(period_end))})
    annual = _as_celsius_if_kelvin(sub.groupby(f"{time_dim}.year").mean(time_dim))
    year_coord = "year" if "year" in annual.coords else f"{time_dim}.year"
    mean_c = annual.mean(year_coord)
    mean_c.name = "annual_mean_temperature_c"
    mean_c.attrs["units"] = "°C"
    return mean_c


def compute_era5_annual_temperature_trend(
    era5_ds,
    period_start: int = 1951,
    period_end: int = 2020,
    temp_var: str = "t2m",
    time_dim: str = "valid_time",
):
    """
    Annual mean temperature trend (°C/decade) from ERA5 monthly 2 m temperature.

    For each year the monthly ``t2m`` values are averaged, converted to °C,
    then a linear trend per decade is fitted at each grid cell.
    """
    import xarray as xr

    temp = era5_ds[temp_var]
    if time_dim not in temp.dims:
        raise ValueError(f"Variable '{temp_var}' must contain dimension '{time_dim}'")

    sub = temp.sel({time_dim: slice(str(period_start), str(period_end))})
    annual = _as_celsius_if_kelvin(sub.groupby(f"{time_dim}.year").mean(time_dim))

    year_coord = "year" if "year" in annual.coords else f"{time_dim}.year"
    years = annual[year_coord].values.astype(float)

    if hasattr(annual.data, "chunks"):
        annual = annual.chunk({year_coord: -1})

    def _trend_for_gridcell(values: np.ndarray) -> float:
        return _linregress_trend_per_decade(years, values)

    trend = xr.apply_ufunc(
        _trend_for_gridcell,
        annual,
        input_core_dims=[[year_coord]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        dask_gufunc_kwargs={"allow_rechunk": True},
    )
    trend.name = "temperature_trend_c_decade"
    trend.attrs["units"] = "°C/decade"
    return trend


def _plot_era5_field_with_cipsap_stations(
    dict_lon_lat: dict,
    monthly_data: dict[str, pd.DataFrame] | None,
    data_dir: str | Path,
    era5_field,
    config: RegionalMapConfig,
    *,
    annual_data: dict[str, pd.DataFrame] | None = None,
    variable_labels: dict | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str | None = None,
    color_label: str | None = None,
    title: str | None = None,
    show_significance: bool = False,
    figsize: tuple[float, float] = (14, 9),
    label_fontsize: int = 9,
):
    """Shared Pacific map: ERA5 field masked to EEZs + coloured station points.

    Station data is either CIPSAP-style ``monthly_data`` (aggregated to annual
    internally, e.g. summing monthly ``RAIN``) or already-annual ``annual_data``
    (e.g. the GHCN-derived indicators from ``compute_regional_rainfall_indicators``)
    -- provide exactly one.
    """
    if (annual_data is None) == (monthly_data is None):
        raise ValueError("Provide exactly one of annual_data or monthly_data.")

    variable_labels = variable_labels or {}
    source = "annual" if annual_data is not None else "monthly"
    sites_df = build_sites_map_dataframe(dict_lon_lat, config, annual_data=annual_data, monthly_data=monthly_data)
    style = _map_style(sites_df, config, variable_labels, source=source)

    _, lons_plot, lons_180, lats, values = _prepare_era5_field_for_pacific_map(era5_field)

    if vmin is None or vmax is None:
        era5_vals = values[np.isfinite(values)]
        station_vals = sites_df["value"].dropna().values
        combined = np.concatenate([era5_vals, station_vals]) if len(station_vals) else era5_vals
        if len(combined):
            vmin = float(np.nanpercentile(combined, 2)) if vmin is None else vmin
            vmax = float(np.nanpercentile(combined, 98)) if vmax is None else vmax
        else:
            vmin = style["vmin"] if vmin is None else vmin
            vmax = style["vmax"] if vmax is None else vmax

    cmap = cmap or style["cmap"]
    color_label = color_label or style["color_label"]

    fig, ax, eez_gdf = create_pacific_base_map(
        data_dir,
        figsize=figsize,
        label_fontsize=label_fontsize,
        show_eez_labels=True,
        eez_facecolor="none",
        eez_alpha=1.0,
    )

    _, _, masked_values = _mask_grid_to_eez(
        lons_plot,
        lats,
        values,
        eez_gdf,
        lons_for_mask=lons_180,
    )
    lon2d, lat2d = np.meshgrid(lons_plot, lats)

    mesh = ax.pcolormesh(
        lon2d,
        lat2d,
        masked_values,
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        shading="auto",
        zorder=2,
    )

    plot_df = sites_df.dropna(subset=["value"])
    ax.scatter(
        plot_df["lon"],
        plot_df["lat"],
        c=plot_df["value"],
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        s=90,
        edgecolors="black",
        linewidths=0.8,
        transform=ccrs.PlateCarree(),
        zorder=6,
    )

    if show_significance and config.metric == "trend" and not plot_df.empty:
        sig_df = plot_df[plot_df["significant"]]
        if not sig_df.empty:
            ax.scatter(
                sig_df["lon"],
                sig_df["lat"],
                marker="x",
                c="black",
                s=55,
                linewidths=1.8,
                transform=ccrs.PlateCarree(),
                zorder=7,
                label="Significant at 95% level",
            )
        fig.text(0.5, 0.03, SIGNIFICANCE_NOTE, ha="center", fontsize=9, style="italic")
        if plot_df["significant"].any():
            ax.legend(loc="lower left", framealpha=0.9, fontsize=9)

    station_source = "CIPSAP stations" if monthly_data is not None else "GHCN stations"
    cbar = fig.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.08, shrink=0.7, aspect=35)
    cbar.set_label(color_label)
    ax.set_title(
        title or style["title"] + f"\n(ERA5 background within EEZs, {station_source})",
        fontsize=14,
        pad=12,
    )

    return fig, ax, sites_df, era5_field


def _eez_inside_mask(
    lons: np.ndarray,
    lats: np.ndarray,
    eez_gdf: gpd.GeoDataFrame,
    *,
    lons_for_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Boolean 2D mask (lat × lon) for grid-cell centres inside Pacific EEZs."""
    from shapely.ops import unary_union
    from shapely.prepared import prep

    mask_lons = _lon_to_180(lons_for_mask if lons_for_mask is not None else lons)
    lon2d, lat2d = np.meshgrid(mask_lons, lats)
    eez_union = unary_union(eez_gdf.geometry)
    prepared = prep(eez_union)

    points = gpd.points_from_xy(lon2d.ravel(), lat2d.ravel())
    inside = np.fromiter((prepared.contains(pt) for pt in points), dtype=bool, count=points.size)
    return inside.reshape(len(lats), len(lons))


def _mask_grid_to_eez(
    lons: np.ndarray,
    lats: np.ndarray,
    values: np.ndarray,
    eez_gdf: gpd.GeoDataFrame,
    *,
    lons_for_mask: np.ndarray | None = None,
):
    """Keep only grid cells whose centres fall inside the Pacific EEZ polygons."""
    lon2d, lat2d = np.meshgrid(lons, lats)
    inside = _eez_inside_mask(lons, lats, eez_gdf, lons_for_mask=lons_for_mask)
    masked = values.copy()
    masked[~inside] = np.nan
    return lon2d, lat2d, masked


def compute_era5_eez_mean_temperature_series(
    era5_ds,
    data_dir: str | Path,
    temp_var: str = "t2m",
    time_dim: str = "valid_time",
    period_start: int | None = None,
    period_end: int | None = None,
):
    """
    Area-weighted mean 2 m temperature (°C) over all Pacific EEZ grid cells.

    Returns a monthly time series of the spatial mean within EEZ polygons.
    """
    eez_gdf = load_pacific_eez(data_dir)
    temp = _as_celsius_if_kelvin(era5_ds[temp_var])
    if time_dim not in temp.dims:
        raise ValueError(f"Variable '{temp_var}' must contain dimension '{time_dim}'")

    if period_start is not None or period_end is not None:
        start = str(period_start) if period_start is not None else None
        end = str(period_end) if period_end is not None else None
        temp = temp.sel({time_dim: slice(start, end)})

    lons = temp["longitude"].values
    lats = temp["latitude"].values
    inside = _eez_inside_mask(lons, lats, eez_gdf)

    import xarray as xr

    inside_da = xr.DataArray(
        inside,
        dims=("latitude", "longitude"),
        coords={"latitude": lats, "longitude": lons},
    )
    lat_weights = xr.DataArray(
        np.cos(np.deg2rad(lats)),
        dims=("latitude",),
        coords={"latitude": lats},
    )
    cell_weights = inside_da * lat_weights

    masked = temp.where(inside_da)
    weighted_sum = (masked * cell_weights).sum(dim=("latitude", "longitude"), skipna=True)
    weight_total = xr.where(masked.notnull(), cell_weights, 0).sum(
        dim=("latitude", "longitude"), skipna=True
    )
    spatial_mean = weighted_sum / weight_total
    spatial_mean.name = "eez_mean_temperature_c"
    spatial_mean.attrs["units"] = "°C"
    return spatial_mean


def _plot_pacific_eez_mini_map(
    ax,
    eez_gdf: gpd.GeoDataFrame,
    extent: tuple[float, float, float, float] = PACIFIC_EXTENT,
    eez_facecolor: str = "#9a9a9a",
    eez_edgecolor: str = "#555555",
    show_title: bool = True,
):
    """Draw a compact Pacific map highlighting EEZ zones used for regional averaging."""
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.set_facecolor("#eef2f5")
    if hasattr(ax, "patch"):
        ax.patch.set_alpha(0.92)

    eez_gdf.plot(
        ax=ax,
        transform=ccrs.PlateCarree(),
        facecolor=eez_facecolor,
        edgecolor=eez_edgecolor,
        linewidth=0.35,
        alpha=0.9,
        zorder=2,
    )
    ax.add_feature(
        cfeature.LAND,
        facecolor="white",
        edgecolor="#cccccc",
        linewidth=0.2,
        zorder=3,
    )
    ax.add_feature(cfeature.COASTLINE, linewidth=0.25, edgecolor="#888888", zorder=4)

    gl = ax.gridlines(draw_labels=False, linewidth=0.25, color="gray", alpha=0.35, linestyle="--")
    gl.xlines = True
    gl.ylines = True
    if show_title:
        ax.set_title("Pacific EEZs", fontsize=9, pad=4)


def _add_pacific_eez_inset(ax, eez_gdf: gpd.GeoDataFrame):
    """Add a small EEZ overview map inset in the upper-left corner of ``ax``."""
    axins = inset_axes(
        ax,
        width="34%",
        height="46%",
        loc="upper left",
        axes_class=GeoAxes,
        axes_kwargs={"map_projection": ccrs.PlateCarree(central_longitude=180)},
        borderpad=0.8,
    )
    _plot_pacific_eez_mini_map(axins, eez_gdf, show_title=False)
    axins.set_zorder(10)
    for spine in axins.spines.values():
        spine.set_edgecolor("#666666")
        spine.set_linewidth(0.8)
    return axins


def plot_era5_eez_temperature_anomaly(
    era5_ds,
    data_dir: str | Path,
    period_start: int = 1950,
    period_end: int = 2020,
    baseline_start: int = 1961,
    baseline_end: int = 1990,
    smooth_years: int = 5,
    temp_var: str = "t2m",
    time_dim: str = "valid_time",
    figsize: tuple[float, float] = (8, 4),
    show_eez_map: bool = True,
    ax=None,
):
    """
    Annual temperature anomaly (°C) for the EEZ area-weighted ERA5 mean.

    Solid line: annual anomaly relative to ``baseline_start``–``baseline_end``.
    Dashed line: centred rolling mean (``smooth_years``).
    When ``show_eez_map`` is True, a small Pacific EEZ map inset is shown inside the plot.
    """
    eez_gdf = load_pacific_eez(data_dir) if show_eez_map else None

    spatial_mean = compute_era5_eez_mean_temperature_series(
        era5_ds,
        data_dir,
        temp_var=temp_var,
        time_dim=time_dim,
    )
    year_coord = f"{time_dim}.year"
    annual = spatial_mean.groupby(year_coord).mean(time_dim)
    if "year" in annual.coords:
        year_coord = "year"

    baseline = annual.sel({year_coord: slice(baseline_start, baseline_end)}).mean(
        dim=year_coord, skipna=True
    )
    anomaly = annual - baseline

    anomaly = anomaly.sel({year_coord: slice(period_start, period_end)})
    anomaly_df = pd.Series(
        anomaly.values,
        index=anomaly[year_coord].values.astype(int),
        name="temperature_anomaly_c",
    )
    smooth = anomaly_df.rolling(window=smooth_years, center=True, min_periods=1).mean()

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    else:
        fig = ax.figure

    ax.plot(anomaly_df.index, anomaly_df.values, color="black", marker="o", markersize=4, linewidth=1)
    ax.plot(smooth.index, smooth.values, color="black", linestyle="--", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlim(period_start, period_end)
    ax.set_xlabel("Year")
    ax.set_ylabel("Temperature anomaly (°C)")
    ax.set_title(
        f"ERA5 mean temperature anomaly over Pacific EEZs\n"
        f"(baseline {baseline_start}–{baseline_end})"
    )

    if show_eez_map and eez_gdf is not None:
        _add_pacific_eez_inset(ax, eez_gdf)

    return fig, ax, anomaly_df, smooth


def load_or_compute_era5_annual_rainfall(
    era5_ds,
    cache_path: str | Path,
    metric: str,
    period_start: int = 1951,
    period_end: int = 2020,
    precip_var: str = "tp",
    force_recompute: bool = False,
):
    """Compute the ERA5 annual-rainfall mean/trend field, cached as NetCDF.

    Pulling and aggregating a global monthly ERA5 field over the network is
    slow; once computed for a given ``metric``/period it is saved at
    ``cache_path`` so later notebook runs load it straight from disk instead
    of recomputing. Pass ``era5_ds=None`` when reusing a cache you know
    exists -- it is only touched on a cache miss.

    Parameters
    ----------
    era5_ds : xarray.Dataset or None
        Opened ERA5 dataset (e.g. from ``xr.open_dataset(..., engine="zarr")``).
        Only read if ``cache_path`` doesn't exist yet or ``force_recompute``.
    cache_path : str or pathlib.Path
        NetCDF file to read from / write to.
    metric : str
        ``"trend"`` (mm/decade) or ``"mean"`` (mm).
    force_recompute : bool, optional
        Recompute and overwrite the cache even if it already exists.

    Returns
    -------
    xarray.DataArray
    """
    import xarray as xr

    # h5netcdf avoids depending on the system netCDF4 install (which can be
    # broken/architecture-mismatched in some conda setups); fall back to
    # xarray's default engine detection if h5netcdf isn't available either.
    try:
        import h5netcdf  # noqa: F401
        netcdf_engine = "h5netcdf"
    except ImportError:
        netcdf_engine = None

    cache_path = Path(cache_path)
    if cache_path.exists() and not force_recompute:
        return xr.open_dataarray(cache_path, engine=netcdf_engine)

    if metric == "trend":
        field = compute_era5_annual_rainfall_trend(
            era5_ds, period_start=period_start, period_end=period_end, precip_var=precip_var,
        )
    elif metric == "mean":
        field = compute_era5_annual_mean_rainfall(
            era5_ds, period_start=period_start, period_end=period_end, precip_var=precip_var,
        )
    else:
        raise ValueError("metric must be 'mean' or 'trend'")

    field = field.load()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    field.to_netcdf(cache_path, engine=netcdf_engine)
    return field


def plot_monthly_rainfall_with_era5_background(
    dict_lon_lat: dict,
    monthly_data: dict[str, pd.DataFrame] | None,
    data_dir: str | Path,
    era5_ds,
    metric: str = "trend",
    period_start: int = 1951,
    period_end: int = 2020,
    precip_var: str = "tp",
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str | None = None,
    figsize: tuple[float, float] = (14, 9),
    label_fontsize: int = 9,
    variable_labels: dict | None = None,
    *,
    annual_data: dict[str, pd.DataFrame] | None = None,
    variable: str = "RAIN",
    era5_field=None,
    min_years: int = 2,
):
    """
    Pacific rainfall map with ERA5 EEZ background and station points.

    ``metric`` is ``"mean"`` (multi-year mean annual rainfall) or ``"trend"``
    (linear trend in mm/decade). Station data is either CIPSAP-style
    ``monthly_data`` (with a monthly ``"RAIN"`` column, summed to annual
    internally) or already-annual ``annual_data`` (e.g. the ``total_annual_mm``
    column from ``compute_regional_rainfall_indicators``) -- provide exactly
    one, and set ``variable`` to the column name when using ``annual_data``.

    ``era5_field`` lets a caller pass an already-computed field (e.g. loaded
    from a cache via :func:`load_or_compute_era5_annual_rainfall`) instead of
    recomputing it from ``era5_ds`` -- pass ``era5_ds=None`` in that case.
    """
    if metric not in {"mean", "trend"}:
        raise ValueError("metric must be 'mean' or 'trend'")
    if (annual_data is None) == (monthly_data is None):
        raise ValueError("Provide exactly one of annual_data or monthly_data.")

    variable_labels = variable_labels or {variable: "annual total rainfall"}
    label = variable_labels.get(variable, variable)

    if metric == "trend":
        if era5_field is None:
            era5_field = compute_era5_annual_rainfall_trend(
                era5_ds,
                period_start=period_start,
                period_end=period_end,
                precip_var=precip_var,
            )
        default_cmap = "BrBG"
        default_vmin, default_vmax = -60.0, 60.0
        color_label = "mm / decade"
        station_source = "CIPSAP stations" if monthly_data is not None else "GHCN stations"
        title = (
            f"Trend in {label.lower()} over {period_start}–{period_end}\n"
            f"(ERA5 background within EEZs, {station_source})"
        )
        show_significance = True
    else:
        if era5_field is None:
            era5_field = compute_era5_annual_mean_rainfall(
                era5_ds,
                period_start=period_start,
                period_end=period_end,
                precip_var=precip_var,
            )
        default_cmap = "YlGnBu"
        default_vmin, default_vmax = None, None
        color_label = "mm"
        station_source = "CIPSAP stations" if monthly_data is not None else "GHCN stations"
        title = (
            f"Mean {label.lower()} ({period_start}–{period_end})\n"
            f"(ERA5 background within EEZs, {station_source})"
        )
        show_significance = False

    config = RegionalMapConfig(
        variable=variable,
        metric=metric,
        period_start=period_start,
        period_end=period_end,
        vmin=vmin if vmin is not None else default_vmin,
        vmax=vmax if vmax is not None else default_vmax,
        color_label=color_label,
        cmap=cmap or default_cmap,
        min_years=min_years,
    )

    return _plot_era5_field_with_cipsap_stations(
        dict_lon_lat,
        monthly_data,
        data_dir,
        era5_field,
        config,
        annual_data=annual_data,
        variable_labels=variable_labels,
        vmin=vmin if vmin is not None else default_vmin,
        vmax=vmax if vmax is not None else default_vmax,
        cmap=cmap or default_cmap,
        color_label=color_label,
        title=title,
        show_significance=show_significance,
        figsize=figsize,
        label_fontsize=label_fontsize,
    )


def plot_monthly_temperature_with_era5_background(
    dict_lon_lat: dict,
    monthly_data: dict[str, pd.DataFrame] | None,
    data_dir: str | Path,
    era5_ds,
    metric: str = "trend",
    period_start: int = 1951,
    period_end: int = 2020,
    temp_var: str = "t2m",
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str | None = None,
    figsize: tuple[float, float] = (14, 9),
    label_fontsize: int = 9,
    variable_labels: dict | None = None,
    *,
    annual_data: dict[str, pd.DataFrame] | None = None,
    variable: str = "TMEAN",
    era5_field=None,
    min_years: int = 2,
):
    """
    Pacific temperature map with ERA5 EEZ background and station points.

    ``metric`` is ``"mean"`` (multi-year mean annual temperature) or ``"trend"``
    (linear trend in °C/decade). Station data is either CIPSAP-style
    ``monthly_data`` (with a monthly ``"TMEAN"`` column, averaged to annual
    internally) or already-annual ``annual_data`` (e.g. the ``tmean_annual``
    column from ``compute_regional_temperature_indicators``) -- provide exactly
    one, and set ``variable`` to the column name when using ``annual_data``.

    ``era5_field`` lets a caller pass an already-computed field (e.g. loaded
    from a cache) instead of recomputing it from ``era5_ds`` -- pass
    ``era5_ds=None`` in that case.
    """
    if metric not in {"mean", "trend"}:
        raise ValueError("metric must be 'mean' or 'trend'")
    if (annual_data is None) == (monthly_data is None):
        raise ValueError("Provide exactly one of annual_data or monthly_data.")

    variable_labels = variable_labels or {variable: "mean annual air temperature"}
    label = variable_labels.get(variable, variable)

    if metric == "trend":
        if era5_field is None:
            era5_field = compute_era5_annual_temperature_trend(
                era5_ds,
                period_start=period_start,
                period_end=period_end,
                temp_var=temp_var,
            )
        default_cmap = "BrBG"
        default_vmin, default_vmax = -0.5, 0.5
        color_label = "°C / decade"
        station_source = "CIPSAP stations" if monthly_data is not None else "GHCN stations"
        title = (
            f"Trend in {label.lower()} over {period_start}–{period_end}\n"
            f"(ERA5 background within EEZs, {station_source})"
        )
        show_significance = True
    else:
        if era5_field is None:
            era5_field = compute_era5_annual_mean_temperature(
                era5_ds,
                period_start=period_start,
                period_end=period_end,
                temp_var=temp_var,
            )
        default_cmap = "RdYlBu_r"
        default_vmin, default_vmax = None, None
        color_label = "°C"
        station_source = "CIPSAP stations" if monthly_data is not None else "GHCN stations"
        title = (
            f"Mean {label.lower()} ({period_start}–{period_end})\n"
            f"(ERA5 background within EEZs, {station_source})"
        )
        show_significance = False

    config = RegionalMapConfig(
        variable=variable,
        metric=metric,
        period_start=period_start,
        period_end=period_end,
        vmin=vmin if vmin is not None else default_vmin,
        vmax=vmax if vmax is not None else default_vmax,
        color_label=color_label,
        cmap=cmap or default_cmap,
        min_years=min_years,
    )

    return _plot_era5_field_with_cipsap_stations(
        dict_lon_lat,
        monthly_data,
        data_dir,
        era5_field,
        config,
        annual_data=annual_data,
        variable_labels=variable_labels,
        vmin=vmin if vmin is not None else default_vmin,
        vmax=vmax if vmax is not None else default_vmax,
        cmap=cmap or default_cmap,
        color_label=color_label,
        title=title,
        show_significance=show_significance,
        figsize=figsize,
        label_fontsize=label_fontsize,
    )


