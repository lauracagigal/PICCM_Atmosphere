"""Shared site-configuration and output-path helpers for PICCM Atmosphere notebooks.

Both ``rainfall.py`` and ``air_temp.py`` re-export everything in this module
so existing notebook imports (``from rainfall import site_config_filename``,
``from air_temp import site_config_filename``, ...) keep working unchanged --
this module exists purely to avoid maintaining two copies of the same code
(which had already drifted: the rainfall-side ``_trend_pvalue``/``_series_stats``
had bug fixes the air-temperature copy never received).

Covers:

- **Site configuration** -- JSON files in ``data/sites/`` written by
  ``00_site_setup.ipynb`` and read by every analysis notebook (rainfall and
  air temperature alike).
- **Output paths** -- site-tagged figures in ``outputs/figures/<site_tag>/``
  and tables in ``outputs/tables/<site_tag>/``.
- **Persist-helper internals** -- the small pieces ``persist_*_outputs()`` in
  ``rainfall.py``/``air_temp.py`` build on (trend p-values, series stats,
  metadata blocks, table export).

Site configuration schema (``data/sites/<site>.json``)::

    site_name, site_lon, site_lat, country,
    ghcn_station_id, ghcn_station_name,
    vars_interest,              # e.g. ["TMIN", "TMAX", "PRCP"]
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
        One row per site config, columns ``site_key`` (the filename stem --
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
        Object returned by ``table_rain_*`` / ``table_temp_*`` helpers in
        ``ind_setup.tables``.

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


# ---------------------------------------------------------------------------
# Persist-helper internals (used by rainfall.py's / air_temp.py's persist_*_outputs)
# ---------------------------------------------------------------------------

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
