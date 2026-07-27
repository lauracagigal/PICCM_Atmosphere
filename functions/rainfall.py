"""Shared helpers for PICCM Rainfall notebooks.

This module is the rainfall counterpart of ``air_temp.py`` in the
``PICCM_AirTemp`` repository. It centralises:

- **Site configuration** — JSON files in ``data/sites/`` written by
  ``00_site_setup.ipynb`` and read by all analysis notebooks.
- **Output paths** — site-tagged figures in ``outputs/figures/<site_tag>/``
  and tables in ``outputs/tables/<site_tag>/``.
- **Dry-spell metrics** — consecutive dry-day calculations for
  ``b_Consecutive_dry_days.ipynb``.
- **Persist helpers** — CSV / JSON export called at the end of each analysis
  notebook.

Site configuration schema (``data/sites/<site>.json``)::

    site_name, site_lon, site_lat, country,
    ghcn_station_id, ghcn_station_name,
    vars_interest,              # e.g. ["PRCP"]
    reference_period_start,     # e.g. "1961"
    reference_period_end,       # e.g. "1990"
    completeness_threshold      # e.g. 0.75
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Site configuration
# ---------------------------------------------------------------------------

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

    Parameters
    ----------
    config_dict : dict
        Site configuration. See the module docstring for the conventional
        schema.
    output_path : str or pathlib.Path
        Destination JSON file (e.g. ``../../data/sites/palau.json``).

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
    """Load a site-configuration dictionary written with :func:`save_site_config`.

    Parameters
    ----------
    config_path : str or pathlib.Path
        Path to the JSON site-config file.

    Returns
    -------
    dict
        Site configuration mapping.

    Raises
    ------
    FileNotFoundError
        If ``config_path`` does not exist. Run ``00_site_setup.ipynb`` first.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Site config not found: {config_path}. "
            "Run notebooks/historical/00_site_setup.ipynb first."
        )
    return pd.read_json(config_path, typ="series").to_dict()


def list_available_sites(sites_dir):
    """Summarise the site configurations already saved in ``sites_dir``.

    Call this before setting ``site_key`` in an analysis notebook to see
    which sites ``00_local_site_setup.ipynb`` has already produced, and
    which ``site_key`` value loads each one back with :func:`load_site_config`.

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


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

def build_site_tag(site_name, site_lon, site_lat):
    """Build a filename-safe identifier that uniquely tags a site.

    Coordinates are formatted with three decimals; ``.`` becomes ``p`` and
    negative signs become ``m`` so the tag is safe on every filesystem.

    Parameters
    ----------
    site_name : str
        Human-readable site name.
    site_lon, site_lat : float
        Site coordinates in decimal degrees.

    Returns
    -------
    str
        Filesystem-safe site tag, e.g. ``palau_lat7p337_lon134p477``.

    Examples
    --------
    >>> build_site_tag("Palau", 134.477, 7.337)
    'palau_lat7p337_lon134p477'
    """
    safe_name = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(site_name)).strip("_")
    safe_name = "_".join(part for part in safe_name.split("_") if part)
    lat_str = f"{float(site_lat):.3f}".replace(".", "p").replace("-", "m")
    lon_str = f"{float(site_lon):.3f}".replace(".", "p").replace("-", "m")
    return f"{safe_name}_lat{lat_str}_lon{lon_str}"


def build_site_figures_dir(base_outputs_dir, site_name, site_lon, site_lat):
    """Return ``outputs/figures/<site_tag>/``, creating it if needed.

    Parameters
    ----------
    base_outputs_dir : str or pathlib.Path
        Repository ``outputs/`` directory.
    site_name, site_lon, site_lat
        Forwarded to :func:`build_site_tag`.

    Returns
    -------
    pathlib.Path
        Per-site figures directory.
    """
    fig_dir = Path(base_outputs_dir) / "figures" / build_site_tag(site_name, site_lon, site_lat)
    fig_dir.mkdir(parents=True, exist_ok=True)
    return fig_dir


def build_output_filename(base_name, site_name, site_lon, site_lat, ext="png"):
    """Build a standardised output filename ``<base_name>_<site_tag>.<ext>``.

    Parameters
    ----------
    base_name : str
        Figure or table identifier (e.g. ``"F5_Rain_anom_top10"``).
    site_name, site_lon, site_lat
        Forwarded to :func:`build_site_tag`.
    ext : str, optional
        File extension without leading dot. Defaults to ``"png"``.

    Returns
    -------
    str
        Composed filename (no directory component).
    """
    site_tag = build_site_tag(site_name, site_lon, site_lat)
    ext = ext.lstrip(".")
    return f"{base_name}_{site_tag}.{ext}"


def build_site_tables_dir(base_outputs_dir, site_name, site_lon, site_lat):
    """Return ``outputs/tables/<site_tag>/``, creating it if needed.

    Parameters
    ----------
    base_outputs_dir : str or pathlib.Path
        Repository ``outputs/`` directory.
    site_name, site_lon, site_lat
        Forwarded to :func:`build_site_tag`.

    Returns
    -------
    pathlib.Path
        Per-site tables directory.
    """
    tables_dir = Path(base_outputs_dir) / "tables" / build_site_tag(site_name, site_lon, site_lat)
    tables_dir.mkdir(parents=True, exist_ok=True)
    return tables_dir


def table_to_dataframe(table_obj):
    """Convert a table helper result or Styler to a plain DataFrame.

    Parameters
    ----------
    table_obj : pandas.DataFrame, Styler, or array-like
        Object returned by ``table_rain_*`` helpers in ``ind_setup.tables``.

    Returns
    -------
    pandas.DataFrame
    """
    if isinstance(table_obj, pd.DataFrame):
        return table_obj
    if hasattr(table_obj, "data"):
        return table_obj.data
    return pd.DataFrame(table_obj)


def save_table_to_csv(table_df, output_dir, filename, index=True):
    """Save a table DataFrame to CSV.

    Parameters
    ----------
    table_df : pandas.DataFrame
    output_dir : str or pathlib.Path
    filename : str
        Target filename (typically from :func:`build_output_filename`).
    index : bool, optional
        Whether to write the DataFrame index. Defaults to ``True``.

    Returns
    -------
    pathlib.Path
        Path of the saved file.
    """
    output_path = Path(output_dir) / filename
    table_df.to_csv(output_path, index=index)
    return output_path


def save_dict_json(data_dict, output_dir, filename):
    """Save a dictionary as a JSON file.

    NumPy scalars and arrays are converted to native Python types.

    Parameters
    ----------
    data_dict : dict
    output_dir : str or pathlib.Path
    filename : str

    Returns
    -------
    pathlib.Path
        Path of the saved file.
    """
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


def _trend_pvalue(series):
    """Return the p-value of a linear trend against calendar year."""
    from scipy import stats

    if pd.api.types.is_numeric_dtype(series.index):
        years = pd.Index(series.index)
    else:
        years = pd.to_datetime(series.index).year
    mask = series.notna()
    if mask.sum() < 2:
        return None
    _, _, _, p_value, _ = stats.linregress(years[mask], series[mask])
    return float(p_value)


def _series_stats(series):
    """Return basic descriptive statistics for a numeric series."""
    values = series.dropna()
    if len(values) == 0:
        return {"n": 0, "mean": None, "min": None, "max": None, "std": None}
    return {
        "n": int(len(values)),
        "mean": float(values.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "std": float(values.std()),
    }


def _site_meta(site_name, site_lon, site_lat, ghcn_station_id, ghcn_station_name, country):
    """Build a standard metadata block for JSON summary files."""
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


def _display_site_table(summary_table, title=None):
    """Render a styled summary table in the active Jupyter notebook."""
    from IPython.display import display
    from ind_setup.tables import style_matrix

    styled = style_matrix(summary_table, title=title) if title else style_matrix(summary_table)
    display(styled)
    return styled


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
