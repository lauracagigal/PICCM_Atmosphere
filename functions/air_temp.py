"""Shared helpers for PICCM Air Temperature notebooks.

This module is the air-temperature counterpart of ``sea_level.py`` in the
``PICCM_SeaLevel`` repository. It centralises **site configuration handling**
so that every historical notebook (``a_mean_temperature``,
``b_min_max_temperature``, ``c_hot_cold_days``) can be parameterised from a
single ``00_site_setup`` notebook.

The site configuration is a plain dictionary persisted as JSON in
``data/sites/<site>.json``. Typical keys include:

- ``site_name`` (str): Human-readable site name (e.g. ``"Palau"``).
- ``site_lon`` / ``site_lat`` (float): Site coordinates in decimal degrees.
- ``country`` (str): Country name used by the GHCN downloader.
- ``ghcn_station_id`` (str): GHCN-Daily station identifier (e.g. ``"PSW00040309"``).
- ``ghcn_station_name`` (str, optional): Human-readable station name.
- ``vars_interest`` (list[str]): Variables to fetch (e.g. ``["TMIN", "TMAX"]``).
- ``reference_period_start`` / ``reference_period_end`` (str): Climatology window
  bounds (years as 4-character strings, used for pandas label-based slicing).
- ``completeness_threshold`` (float): Minimum fraction of valid days/months
  required to keep a period.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def haversine_km(lon1, lat1, lon2, lat2):
    """Great-circle distance in kilometres between two points.

    Vectorised over the inputs: each argument may be a scalar or a
    numpy array, and the standard broadcasting rules apply. Coordinates
    are in decimal degrees.

    Used in ``00_site_setup`` to rank GHCN-Daily stations by distance to
    the user's site coordinates.

    Parameters
    ----------
    lon1, lat1 : float or array-like
        Longitude and latitude of the first point(s) in decimal degrees.
    lon2, lat2 : float or array-like
        Longitude and latitude of the second point(s) in decimal degrees.

    Returns
    -------
    float or numpy.ndarray
        Great-circle distance in kilometres. The output shape follows
        numpy broadcasting between the inputs.
    """
    r = 6371.0
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def site_config_filename(site_key):
    """Return the JSON filename for a site key.

    Parameters
    ----------
    site_key : str
        Human-readable site name (e.g. ``"Palau"``).

    Returns
    -------
    str
        Slugified filename (e.g. ``"palau.json"``).

    Examples
    --------
    >>> site_config_filename("Palau")
    'palau.json'
    """
    safe_name = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(site_key)).strip("_")
    safe_name = "_".join(part for part in safe_name.split("_") if part)
    return f"{safe_name}.json"


def save_site_config(config_dict, output_path):
    """Persist a site-configuration dictionary as a JSON file.

    The parent directory of ``output_path`` is created if it does not exist.
    The dictionary is serialised through :class:`pandas.Series` so non-ASCII
    characters in site names (e.g. accented letters) are preserved.

    Parameters
    ----------
    config_dict : dict
        Site configuration. Keys are stored verbatim. See the module
        docstring for the conventional schema.
    output_path : str or pathlib.Path
        Destination JSON file (e.g. ``"../../data/sites/palau.json"``).

    Returns
    -------
    pathlib.Path
        Resolved path of the file that was written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.Series(config_dict).to_json(output_path, indent=2, force_ascii=False)
    return output_path


def load_site_config(config_path):
    """Load a site-configuration dictionary previously written with
    :func:`save_site_config`.

    Parameters
    ----------
    config_path : str or pathlib.Path
        Path to the JSON site-config file.

    Returns
    -------
    dict
        Site configuration mapping. Values keep the JSON-native types
        (``str``, ``int``, ``float``, ``list``, ``None``).

    Raises
    ------
    FileNotFoundError
        If ``config_path`` does not exist. The site-setup notebook
        (``00_site_setup.ipynb``) must be executed at least once before
        any other historical notebook can be run.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Site config not found: {config_path}")
    return pd.read_json(config_path, typ="series").to_dict()


def list_available_sites(sites_dir):
    """Summarise the site configurations already saved in ``sites_dir``.

    Call this before setting ``site_key`` in an analysis notebook to see
    which sites ``00_site_setup.ipynb`` has already produced, and which
    ``site_key`` value loads each one back with :func:`load_site_config`.

    Parameters
    ----------
    sites_dir : str or pathlib.Path
        Directory containing ``<site_key>.json`` files written by
        :func:`save_site_config` (typically ``data/sites``).

    Returns
    -------
    pandas.DataFrame
        One row per site config, columns ``site_key`` (the filename stem —
        pass this to :func:`site_config_filename` / use as ``site_key``),
        ``site_name``, ``country``, ``ghcn_station_id``,
        ``ghcn_station_name`` and ``vars_interest``. Empty if ``sites_dir``
        does not exist or contains no JSON files.
    """
    columns = [
        "site_key", "site_name", "country",
        "ghcn_station_id", "ghcn_station_name", "vars_interest",
    ]
    sites_dir = Path(sites_dir)
    if not sites_dir.exists():
        return pd.DataFrame(columns=columns)

    rows = []
    for config_path in sorted(sites_dir.glob("*.json")):
        cfg = load_site_config(config_path)
        rows.append({
            "site_key": config_path.stem,
            "site_name": cfg.get("site_name"),
            "country": cfg.get("country"),
            "ghcn_station_id": cfg.get("ghcn_station_id"),
            "ghcn_station_name": cfg.get("ghcn_station_name"),
            "vars_interest": cfg.get("vars_interest"),
        })
    return pd.DataFrame(rows, columns=columns)


def build_site_tag(site_name, site_lon, site_lat):
    """Build a filename-safe identifier that uniquely tags a site.

    The tag combines a slugified version of ``site_name`` with both
    coordinates so that exported figures and tables for different sites
    never overwrite each other. Coordinates are formatted with three
    decimals; ``.`` is replaced by ``p`` and the negative sign by ``m`` to
    keep the result safe on every filesystem.

    Examples
    --------
    >>> build_site_tag("Palau", 134.620, 7.340)
    'palau_lat7p340_lon134p620'
    >>> build_site_tag("American Samoa", -170.7, -14.3)
    'american_samoa_latm14p300_lonm170p700'

    Parameters
    ----------
    site_name : str
        Human-readable site name. Non-alphanumeric characters are
        replaced with underscores and the result is lowercased.
    site_lon, site_lat : float
        Site coordinates in decimal degrees.

    Returns
    -------
    str
        Filesystem-safe site tag.
    """
    safe_name = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(site_name)).strip("_")
    safe_name = "_".join(part for part in safe_name.split("_") if part)
    lat_str = f"{float(site_lat):.3f}".replace(".", "p").replace("-", "m")
    lon_str = f"{float(site_lon):.3f}".replace(".", "p").replace("-", "m")
    return f"{safe_name}_lat{lat_str}_lon{lon_str}"


def build_output_filename(base_name, site_name, site_lon, site_lat, ext="png"):
    """Build a standardised output filename of the form
    ``"<base_name>_<site_tag>.<ext>"``.

    Useful for figures and tables that need to live in a shared output
    directory but stay disambiguated per site.

    Parameters
    ----------
    base_name : str
        Plot/table identifier (e.g. ``"F2_ST_Annomalies_top10"``).
    site_name : str
        Site name forwarded to :func:`build_site_tag`.
    site_lon, site_lat : float
        Site coordinates forwarded to :func:`build_site_tag`.
    ext : str, optional
        File extension. Leading dots are stripped. Defaults to ``"png"``.

    Returns
    -------
    str
        Composed filename (no directory component).
    """
    site_tag = build_site_tag(site_name, site_lon, site_lat)
    ext = ext.lstrip(".")
    return f"{base_name}_{site_tag}.{ext}"


def build_site_figures_dir(base_outputs_dir, site_name, site_lon, site_lat):
    """Return the per-site figures directory ``outputs/figures/<site_tag>/``.

    The directory is created if it does not exist.
    """
    fig_dir = Path(base_outputs_dir) / "figures" / build_site_tag(site_name, site_lon, site_lat)
    fig_dir.mkdir(parents=True, exist_ok=True)
    return fig_dir


def build_site_tables_dir(base_outputs_dir, site_name, site_lon, site_lat):
    """Return the per-site tables directory ``outputs/tables/<site_tag>/``.

    The directory is created if it does not exist.
    """
    tables_dir = Path(base_outputs_dir) / "tables" / build_site_tag(site_name, site_lon, site_lat)
    tables_dir.mkdir(parents=True, exist_ok=True)
    return tables_dir


def table_to_dataframe(table_obj):
    """Return a plain DataFrame from a table helper result or Styler."""
    if isinstance(table_obj, pd.DataFrame):
        return table_obj
    if hasattr(table_obj, "data"):
        return table_obj.data
    return pd.DataFrame(table_obj)


def save_table_to_csv(table_df, output_dir, filename, index=True):
    """Save a table DataFrame to ``output_dir`` and return the saved path."""
    output_path = Path(output_dir) / filename
    table_df.to_csv(output_path, index=index)
    return output_path


def save_dict_json(data_dict, output_dir, filename):
    """Save a dictionary as JSON in ``output_dir`` and return the saved path."""
    output_path = Path(output_dir) / filename

    def _default(obj):
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, "isoformat"):
            try:
                return obj.isoformat()
            except Exception:
                pass
        return str(obj)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data_dict, f, indent=2, ensure_ascii=False, default=_default)
    return output_path


def _trend_pvalue(series):
    from scipy import stats

    years = series.index.year
    mask = series.notna()
    _, _, _, p_value, _ = stats.linregress(years[mask], series[mask])
    return float(p_value)


def _series_stats(series):
    values = series.dropna()
    return {
        "n": int(len(values)),
        "mean": float(values.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "std": float(values.std()),
    }


def _site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country):
    return {
        "site_name": site_name,
        "ghcn_station_id": ghcn_station_id,
        "ghcn_station_name": ghcn_station_name,
        "country": country,
        "data_source": "GHCN-Daily",
    }


def _frame_with_year_column(df, value_cols):
    """Return a copy of ``df`` with a plain integer ``year`` column."""
    reset = df[value_cols].reset_index()
    index_col = reset.columns[0]
    reset["year"] = pd.to_datetime(reset[index_col]).dt.year
    return reset[["year", *value_cols]]


def _display_site_table(summary_table):
    """Render a styled summary table in the active Jupyter notebook."""
    from IPython.display import display
    from ind_setup.tables import style_matrix

    styled = style_matrix(summary_table)
    display(styled)
    return styled


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
