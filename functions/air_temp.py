"""Air-temperature-specific helpers for PICCM Atmosphere notebooks.

Site configuration, output-path building and the small pieces
``persist_*_outputs()`` builds on live in ``site_common.py`` and are
re-exported here unchanged, so ``from air_temp import site_config_filename``
(etc.) keeps working exactly as before -- ``rainfall.py`` re-exports the same
names from the same shared module. See ``site_common.py`` for their
docstrings.

Site configuration schema (``data/sites/<site>.json``)::

    site_name, site_lon, site_lat, country,
    ghcn_station_id, ghcn_station_name,
    vars_interest,              # e.g. ["TMIN", "TMAX"]
    reference_period_start,     # e.g. "1961"
    reference_period_end,       # e.g. "1990"
    completeness_threshold      # e.g. 0.75
"""

import numpy as np
import pandas as pd

from site_common import (  # noqa: F401 -- re-exported for `from air_temp import ...`
    site_config_filename,
    save_site_config,
    load_site_config,
    list_available_sites,
    build_site_tag,
    build_output_filename,
    build_site_figures_dir,
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


def persist_mean_temperature_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    st_data,
    df2,
    top_10,
    summary_table,
    trend,
    mean_ref,
    ref_start,
    ref_end,
    show_table=True,
):
    """Display the summary table and persist all mean-temperature CSV/JSON outputs."""
    from scipy import stats

    if show_table:
        _display_site_table(summary_table)

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    annual_mean = _frame_with_year_column(st_data, ["TMEAN", "TMEAN_ref"])
    save_table_to_csv(
        annual_mean,
        site_tables_dir,
        build_output_filename("T_mean_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table),
        site_tables_dir,
        build_output_filename("T_mean_summary_table", site_name, site_lon, site_lat, ext="csv"),
    )

    oni_cols = [c for c in ["ONI", "oni_cat", "tmean", "tmean_ref", "tmin", "tmax", "tdiff"] if c in df2.columns]
    oni_annual = df2[oni_cols].copy()
    oni_annual = oni_annual.reset_index()
    index_col = oni_annual.columns[0]
    oni_annual.insert(0, "year", pd.to_datetime(oni_annual[index_col]).dt.year)
    if index_col != "year":
        oni_annual = oni_annual.drop(columns=[index_col])
    save_table_to_csv(
        oni_annual,
        site_tables_dir,
        build_output_filename("T_mean_ONI_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    oni_mask = oni_annual["ONI"].notna() & oni_annual["tmean_ref"].notna()
    enso_slope, _, enso_r, enso_p, _ = stats.linregress(
        oni_annual.loc[oni_mask, "ONI"],
        oni_annual.loc[oni_mask, "tmean_ref"],
    )
    save_table_to_csv(
        pd.DataFrame(
            {
                "metric": ["slope_C_per_ONI", "r", "p_value"],
                "value": [float(enso_slope), float(enso_r), float(enso_p)],
            }
        ),
        site_tables_dir,
        build_output_filename("ENSO_temperature_summary", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    top_10_table = _frame_with_year_column(top_10, ["TMEAN", "TMEAN_ref"])
    save_table_to_csv(
        top_10_table,
        site_tables_dir,
        build_output_filename("T_mean_top10_warmest_years", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    n_years = len(np.unique(st_data.index.year))
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": int(st_data.index.year.min()), "end": int(st_data.index.year.max())},
        "reference_period": {"start": ref_start, "end": ref_end},
        "mean_ref_C": float(mean_ref),
        "trend_C_per_year": float(trend),
        "trend_C_per_decade": float(trend * 10),
        "change_C_over_window": float(trend * n_years),
        "top_10_warmest_years": [
            {
                "year": int(row["year"]),
                "TMEAN_C": float(row["TMEAN"]),
                "anomaly_C": float(row["TMEAN_ref"]),
            }
            for _, row in top_10_table.iterrows()
        ],
        "enso": {
            "slope_C_per_ONI": float(enso_slope),
            "r": float(enso_r),
            "p_value": float(enso_p),
            "data_source": "NOAA ONI",
        },
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("T_mean_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir


def persist_minmax_temperature_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    st_data,
    summary_table,
    trend_minimum,
    trend_maximum,
    trend_diff,
    show_table=True,
):
    """Display the summary table and persist all min/max temperature CSV/JSON outputs."""
    if show_table:
        _display_site_table(summary_table)

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    annual_minmax = _frame_with_year_column(st_data, ["TMIN", "TMAX", "diff"])
    save_table_to_csv(
        annual_minmax,
        site_tables_dir,
        build_output_filename("T_minmax_annual", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table),
        site_tables_dir,
        build_output_filename("T_minmax_summary_table", site_name, site_lon, site_lat, ext="csv"),
    )

    n_years = len(np.unique(st_data.index.year))
    period_start = int(st_data.dropna().index[0].year)
    period_end = int(st_data.dropna().index[-1].year)
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": period_start, "end": period_end},
        "tmin": {
            "annual_mean_C": float(st_data.TMIN.mean()),
            "trend_C_per_year": float(trend_minimum[0]),
            "trend_C_per_decade": float(trend_minimum[0] * 10),
            "change_C_over_window": float(trend_minimum[0] * n_years),
            "p_value": _trend_pvalue(st_data["TMIN"]),
        },
        "tmax": {
            "annual_mean_C": float(st_data.TMAX.mean()),
            "trend_C_per_year": float(trend_maximum[0]),
            "trend_C_per_decade": float(trend_maximum[0] * 10),
            "change_C_over_window": float(trend_maximum[0] * n_years),
            "p_value": _trend_pvalue(st_data["TMAX"]),
        },
        "diurnal_range": {
            "annual_mean_C": float(st_data["diff"].mean()),
            "trend_C_per_year": float(trend_diff[0]),
            "trend_C_per_decade": float(trend_diff[0] * 10),
            "change_C_over_window": float(trend_diff[0] * n_years),
            "p_value": _trend_pvalue(st_data["diff"]),
        },
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("T_minmax_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir


def persist_hot_cold_outputs(
    outputs_dir,
    site_name,
    site_lon,
    site_lat,
    ghcn_station_id,
    ghcn_station_name,
    country,
    df_exceed,
    annual_hot,
    annual_cold,
    summary_table_etccdi,
    summary_table_percentiles,
    trends_etccdi,
    trends_percentiles,
    st_max_counts,
    st_min_counts,
    q90,
    q10,
    show_tables=True,
):
    """Display summary tables and persist all hot/cold days CSV/JSON outputs."""
    if show_tables:
        _display_site_table(summary_table_etccdi)
        _display_site_table(summary_table_percentiles)

    site_tables_dir = build_site_tables_dir(outputs_dir, site_name, site_lon, site_lat)

    hot_days_per_year = df_exceed.groupby("YEAR")["HOT_DAY"].sum().reset_index()
    hot_days_per_year.columns = ["year", "hot_days"]
    save_table_to_csv(
        hot_days_per_year,
        site_tables_dir,
        build_output_filename("T_hot_days_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    cold_nights_per_year = df_exceed.groupby("YEAR")["COLD_NIGHT"].sum().reset_index()
    cold_nights_per_year.columns = ["year", "cold_nights"]
    save_table_to_csv(
        cold_nights_per_year,
        site_tables_dir,
        build_output_filename("T_cold_nights_per_year", site_name, site_lon, site_lat, ext="csv"),
        index=False,
    )

    save_table_to_csv(
        table_to_dataframe(summary_table_etccdi),
        site_tables_dir,
        build_output_filename("T_hot_cold_summary_table_etccdi", site_name, site_lon, site_lat, ext="csv"),
    )

    save_table_to_csv(
        table_to_dataframe(summary_table_percentiles),
        site_tables_dir,
        build_output_filename("T_hot_cold_summary_table_percentiles", site_name, site_lon, site_lat, ext="csv"),
    )

    period_start = int(df_exceed["YEAR"].min())
    period_end = int(df_exceed["YEAR"].max())
    summary_metrics = {
        **_site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country),
        "period": {"start": period_start, "end": period_end},
        "etccdi": {
            "threshold_definition": "TX90p / TN10p (1961-1990 base period)",
            "hot_days_per_year_stats": _series_stats(hot_days_per_year.set_index("year")["hot_days"]),
            "cold_nights_per_year_stats": _series_stats(cold_nights_per_year.set_index("year")["cold_nights"]),
            "slope_hot_days_per_year": float(trends_etccdi[1]),
            "p_value_hot_days": _trend_pvalue(annual_hot["Perc_Anom"]),
            "slope_cold_nights_per_year": float(trends_etccdi[0]),
            "p_value_cold_nights": _trend_pvalue(annual_cold["Perc_Anom"]),
        },
        "fixed_percentile": {
            "threshold_definition": "TMAX > q90 and TMIN < q10 (1961-1991)",
            "q90_TMAX_C": float(q90),
            "q10_TMIN_C": float(q10),
            "hot_days_per_year_stats": _series_stats(st_max_counts["TMAX"]),
            "cold_nights_per_year_stats": _series_stats(st_min_counts["TMIN"]),
            "slope_hot_days_per_year": float(trends_percentiles[1]),
            "p_value_hot_days": _trend_pvalue(st_max_counts["TMAX"]),
            "slope_cold_nights_per_year": float(trends_percentiles[0]),
            "p_value_cold_nights": _trend_pvalue(st_min_counts["TMIN"]),
        },
    }
    save_dict_json(
        summary_metrics,
        site_tables_dir,
        build_output_filename("T_hot_cold_summary_metrics", site_name, site_lon, site_lat, ext="json"),
    )
    return site_tables_dir
