"""Rainfall-specific helpers for PICCM Atmosphere notebooks.

Site configuration, output-path building and the small pieces
``persist_*_outputs()`` builds on live in ``site_common.py`` and are
re-exported here unchanged, so ``from rainfall import site_config_filename``
(etc.) keeps working exactly as before -- ``air_temp.py`` re-exports the same
names from the same shared module. See ``site_common.py`` for their
docstrings.

This module adds the rainfall-only pieces on top:

- **Dry-spell metrics** — consecutive dry-day calculations for
  ``b_Consecutive_dry_days.ipynb``.
- **Persist helpers** — CSV / JSON export called at the end of each rainfall
  analysis notebook (``a_Total_rainfall.ipynb``, ``b_Consecutive_dry_days.ipynb``,
  ``c_Heavy_rainfall.ipynb``).

Site configuration schema (``data/sites/<site>.json``)::

    site_name, site_lon, site_lat, country,
    ghcn_station_id, ghcn_station_name,
    vars_interest,              # e.g. ["PRCP"]
    reference_period_start,     # e.g. "1961"
    reference_period_end,       # e.g. "1990"
    completeness_threshold      # e.g. 0.75
"""

import numpy as np
import pandas as pd

from site_common import (  # noqa: F401 -- re-exported for `from rainfall import ...`
    site_config_filename,
    save_site_config,
    load_site_config,
    list_available_sites,
    build_site_tag,
    build_site_figures_dir,
    build_output_filename,
    build_site_tables_dir,
    table_to_dataframe,
    save_table_to_csv,
    save_dict_json,
    _trend_pvalue,
    _series_stats,
    _site_meta,
    _frame_with_year_column,
    _display_site_table,
)


def _trend_slope(trend):
    """Extract a linear slope from assorted trend return types."""
    if trend is None:
        return None
    if isinstance(trend, (list, tuple)):
        return float(trend[0])
    if isinstance(trend, dict):
        for key in ("slope", "trend", "PRCP"):
            if key in trend:
                val = trend[key]
                if isinstance(val, (list, tuple)):
                    return float(val[0])
                return float(val)
    try:
        return float(trend)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Dry-spell metrics (used in b_Consecutive_dry_days)
# ---------------------------------------------------------------------------

def consecutive_dry_days(series):
    """Return the longest run of consecutive dry days in a boolean series.

    A dry day is marked ``True``. The count resets on the first wet day
    (``False``). The final run is included if the series ends on dry days.

    Parameters
    ----------
    series : array-like of bool
        Daily dry-day flags.

    Returns
    -------
    int
        Maximum number of consecutive dry days in the series.
    """
    consec_dry = 0
    max_consec_dry = 0
    for value in series:
        if value:
            consec_dry += 1
        else:
            max_consec_dry = max(max_consec_dry, consec_dry)
            consec_dry = 0
    return max(max_consec_dry, consec_dry)


def count_consecutive_days(series):
    """Return the running count of consecutive dry days at each timestep.

    Parameters
    ----------
    series : array-like of bool
        Daily dry-day flags (``True`` = dry).

    Returns
    -------
    list of int
        For each day, the length of the current dry spell ending on that day
        (0 on wet days).
    """
    count = 0
    result = []
    for value in series:
        if value:
            count += 1
        else:
            count = 0
        result.append(count)
    return result


# ---------------------------------------------------------------------------
# Persist analysis outputs (figures saved in notebooks; tables/JSON here)
# ---------------------------------------------------------------------------

def persist_total_rainfall_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    datag,
    datag_dry,
    datag_wet,
    top_10,
    summary_table,
    trend_da_mean,
    trend_ac_an,
    mean_ref,
    ref_start,
    ref_end,
    df_oni=None,
    show_table=True,
):
    """Display and persist all outputs from ``a_Total_rainfall.ipynb``.

    Figures are saved directly in the notebook. This function writes the
    summary table, annual CSVs and the JSON metrics file to
    ``outputs/tables/<site_tag>/``.

    Parameters
    ----------
    outputs_dir : str or pathlib.Path
        Repository ``outputs/`` directory.
    site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country
        Site metadata from the loaded config.
    datag : pandas.DataFrame
        Annual normalised accumulated precipitation.
    datag_dry, datag_wet : pandas.DataFrame
        Annual accumulated precipitation for dry and wet seasons.
    top_10 : pandas.DataFrame
        Ten wettest years relative to the reference period.
    summary_table
        Output of ``table_rain_21``.
    trend_da_mean, trend_ac_an
        Trend objects from the daily and accumulated precipitation plots.
    mean_ref : float
        Reference-period mean accumulated rainfall (mm/year).
    ref_start, ref_end : str
        Reference period bounds (e.g. ``"1961"``, ``"1990"``).
    df_oni : pandas.DataFrame, optional
        Annual ONI-joined precipitation data for the ENSO section.
    show_table : bool, optional
        If ``True``, render the styled summary table in the notebook.

    Returns
    -------
    pathlib.Path
        ``outputs/tables/<site_tag>/`` directory.
    """
    if show_table:
        _display_site_table(summary_table, title="Mean Precipitation Metrics and Trends")

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    annual = _frame_with_year_column(datag, ["PRCP", "PRCP_ref"] if "PRCP_ref" in datag.columns else ["PRCP"])
    save_table_to_csv(
        annual,
        site_tables_dir,
        build_output_filename("R_mean_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table),
        site_tables_dir,
        build_output_filename("R_mean_summary_table", site_name, site_lon, site_lat, ext="csv"),
    )

    top_10_table = _frame_with_year_column(top_10, ["PRCP", "PRCP_ref"])
    save_table_to_csv(
        top_10_table,
        site_tables_dir,
        build_output_filename("R_top10_wettest_years", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    dry_annual = _frame_with_year_column(datag_dry, ["PRCP"])
    save_table_to_csv(
        dry_annual,
        site_tables_dir,
        build_output_filename("R_dry_season_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    wet_annual = _frame_with_year_column(datag_wet, ["PRCP"])
    save_table_to_csv(
        wet_annual,
        site_tables_dir,
        build_output_filename("R_wet_season_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    if df_oni is not None:
        oni_cols = [c for c in ["ONI", "oni_cat", "prcp", "prcp_ref"] if c in df_oni.columns]
        oni_annual = df_oni[oni_cols].copy().reset_index()
        index_col = oni_annual.columns[0]
        oni_annual.insert(0, "year", pd.to_datetime(oni_annual[index_col]).dt.year)
        if index_col != "year":
            oni_annual = oni_annual.drop(columns=[index_col])
        save_table_to_csv(
            oni_annual,
            site_tables_dir,
            build_output_filename("R_ONI_annual", site_name, site_lon, site_lat, ext="csv"),
            index=False,
        )

    n_years = len(np.unique(datag.index.year))
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": int(datag.index.year.min()), "end": int(datag.index.year.max())},
        "reference_period": {"start": ref_start, "end": ref_end},
        "mean_ref_mm": float(mean_ref),
        "accumulated_trend_mm_per_year": _trend_slope(trend_ac_an),
        "accumulated_trend_mm_per_decade": (
            _trend_slope(trend_ac_an) * 10 if _trend_slope(trend_ac_an) is not None else None
        ),
        "accumulated_change_mm_over_window": (
            _trend_slope(trend_ac_an) * n_years if _trend_slope(trend_ac_an) is not None else None
        ),
        "daily_trend": trend_da_mean,
        "top_10_wettest_years": [
            {
                "year": int(row["year"]),
                "PRCP_mm": float(row["PRCP"]),
                "anomaly_mm": float(row["PRCP_ref"]),
            }
            for _, row in top_10_table.iterrows()
        ],
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("R_mean_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir


def persist_dry_days_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    data,
    dry_days_per_year,
    consecutive_max_per_year,
    consecutive_mean_per_year,
    summary_table,
    trend_dry_days,
    trend_max_ndays,
    show_table=True,
):
    """Display and persist all outputs from ``b_Consecutive_dry_days.ipynb``.

    Parameters
    ----------
    outputs_dir : str or pathlib.Path
        Repository ``outputs/`` directory.
    site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country
        Site metadata.
    data : pandas.DataFrame
        Filtered daily precipitation with derived dry-day columns.
    dry_days_per_year : pandas.DataFrame
        Columns ``year``, ``dry_days``.
    consecutive_max_per_year, consecutive_mean_per_year : pandas.Series
        Annual maximum and mean consecutive dry-day counts.
    summary_table
        Output of ``table_rain_22``.
    trend_dry_days, trend_max_ndays
        Trend objects from the dry-day bar plots.
    show_table : bool, optional
        If ``True``, render the styled summary table in the notebook.

    Returns
    -------
    pathlib.Path
        ``outputs/tables/<site_tag>/`` directory.
    """
    if show_table:
        _display_site_table(summary_table, title="Dry Conditions")

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    save_table_to_csv(
        dry_days_per_year,
        site_tables_dir,
        build_output_filename("R_dry_days_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    max_table = consecutive_max_per_year.reset_index()
    max_table.columns = ["year", "max_consecutive_dry_days"]
    save_table_to_csv(
        max_table,
        site_tables_dir,
        build_output_filename("R_consecutive_dry_max_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    mean_table = consecutive_mean_per_year.reset_index()
    mean_table.columns = ["year", "mean_consecutive_dry_days"]
    save_table_to_csv(
        mean_table,
        site_tables_dir,
        build_output_filename("R_consecutive_dry_mean_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table),
        site_tables_dir,
        build_output_filename("R_dry_summary_table", site_name, site_lon, site_lat, ext="csv"),
    )

    period_start = int(data.index.year.min())
    period_end = int(data.index.year.max())
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": period_start, "end": period_end},
        "dry_day_threshold_mm": 1.0,
        "dry_days_per_year_stats": _series_stats(dry_days_per_year.set_index("year")["dry_days"]),
        "max_consecutive_dry_days_stats": _series_stats(
            consecutive_max_per_year.rename("max_consecutive_dry_days")
        ),
        "mean_consecutive_dry_days_stats": _series_stats(
            consecutive_mean_per_year.rename("mean_consecutive_dry_days")
        ),
        "trend_dry_days_per_year": _trend_slope(trend_dry_days),
        "trend_max_consecutive_dry_days": _trend_slope(trend_max_ndays),
        "p_value_dry_days": _trend_pvalue(dry_days_per_year.set_index("year")["dry_days"]),
        "p_value_max_consecutive_dry_days": _trend_pvalue(
            consecutive_max_per_year.rename("max_consecutive_dry_days")
        ),
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("R_dry_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir


def persist_heavy_rainfall_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    wet_days_per_year,
    heavy_days_per_year,
    summary_table,
    trend_wet,
    trend_95,
    threshold_95_mm,
    show_table=True,
):
    """Display and persist all outputs from ``c_Heavy_rainfall.ipynb``.

    Parameters
    ----------
    outputs_dir : str or pathlib.Path
        Repository ``outputs/`` directory.
    site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country
        Site metadata.
    wet_days_per_year : pandas.DataFrame
        Columns ``year``, ``wet_days`` (days with PRCP > 1 mm).
    heavy_days_per_year : pandas.DataFrame
        Columns ``year``, ``heavy_days`` (days above the 95th percentile).
    summary_table
        Output of ``table_rain_23``.
    trend_wet, trend_95
        Trend objects from the wet-day and heavy-rainfall bar plots.
    threshold_95_mm : float
        95th-percentile rainfall threshold in mm.
    show_table : bool, optional
        If ``True``, render the styled summary table in the notebook.

    Returns
    -------
    pathlib.Path
        ``outputs/tables/<site_tag>/`` directory.
    """
    if show_table:
        _display_site_table(summary_table)

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    save_table_to_csv(
        wet_days_per_year,
        site_tables_dir,
        build_output_filename("R_wet_days_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        heavy_days_per_year,
        site_tables_dir,
        build_output_filename("R_heavy_days_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table),
        site_tables_dir,
        build_output_filename("R_heavy_summary_table", site_name, site_lon, site_lat, ext="csv"),
    )

    period_start = int(wet_days_per_year["year"].min())
    period_end = int(wet_days_per_year["year"].max())
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": period_start, "end": period_end},
        "wet_day_threshold_mm": 1.0,
        "heavy_rainfall_threshold_mm": float(threshold_95_mm),
        "heavy_rainfall_percentile": 95,
        "wet_days_per_year_stats": _series_stats(wet_days_per_year.set_index("year")["wet_days"]),
        "heavy_days_per_year_stats": _series_stats(heavy_days_per_year.set_index("year")["heavy_days"]),
        "trend_wet_days_per_year": _trend_slope(trend_wet),
        "trend_heavy_days_per_year": _trend_slope(trend_95),
        "p_value_wet_days": _trend_pvalue(wet_days_per_year.set_index("year")["wet_days"]),
        "p_value_heavy_days": _trend_pvalue(heavy_days_per_year.set_index("year")["heavy_days"]),
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("R_heavy_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir
