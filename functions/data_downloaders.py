"""Data download and quality-control helpers for PICCM Rainfall notebooks.

This module provides access to:

- **GHCN-Daily** station catalogs and per-station precipitation time series.
- **NOAA ONI** (Oceanic Niño Index) for ENSO analysis in ``a_Total_rainfall``.
- **Time-completeness filtering** applied during ``00_site_setup.ipynb``.

All rainfall notebooks use the ``PRCP`` variable (daily precipitation in mm after
the GHCN tenths scaling factor is applied).
"""

from io import StringIO

import numpy as np
import pandas as pd
import requests

GHCND_ACCESS_URL = (
    "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/"
)
ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"


class GHCN:
    """Helpers for the GHCN-Daily station archive (NOAA NCEI).

    GHCN-Daily is the primary data source for historical rainfall indicators in
    this repository. Station metadata, country codes and per-station CSV files
    are fetched directly from NOAA servers.

    Typical workflow (``00_site_setup.ipynb``)::

        df_countries = GHCN.download_country_codes()
        df_stations = GHCN.download_stations_info()
        df_inventory = GHCN.download_station_inventory()
        records, ids = GHCN.extract_dict_data_var(GHCND_ACCESS_URL, "PRCP", df_target)
    """

    @staticmethod
    def download_country_codes():
        """Download the GHCN country-code table.

        Returns
        -------
        pandas.DataFrame
            Two columns: ``Code`` (2-letter GHCN country code) and ``Country``
            (official country name as used in the GHCN catalog).
        """
        url = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-countries.txt"
        country_codes = requests.get(url).text.split("\n")
        codes = [line.split(" ")[0] for line in country_codes]
        countries = [" ".join(line.split(" ")[1:]).strip() for line in country_codes]
        return pd.DataFrame({"Code": codes, "Country": countries})

    @staticmethod
    def get_country_code(country):
        """Look up the GHCN country code for an exact country name.

        Parameters
        ----------
        country : str
            Country name exactly as it appears in the GHCN catalog
            (e.g. ``"Palau"``).

        Returns
        -------
        pandas.DataFrame
            Zero or one rows matching ``Country == country``.
        """
        df = GHCN.download_country_codes()
        return df.loc[df["Country"] == country]

    @staticmethod
    def download_stations_info():
        """Download GHCN-Daily station metadata.

        Returns
        -------
        pandas.DataFrame
            Columns: ``ID``, ``Latitude``, ``Longitude``, ``Elevation``, ``Name``.
            The first two characters of ``ID`` are the GHCN country code.
        """
        url = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
        processed_data = []
        for line in requests.get(url).text.split("\n"):
            if not line:
                continue
            parts = line.split()
            processed_data.append([
                parts[0],
                float(parts[1]),
                float(parts[2]),
                float(parts[3]),
                " ".join(parts[4:]),
            ])
        return pd.DataFrame(
            processed_data,
            columns=["ID", "Latitude", "Longitude", "Elevation", "Name"],
        )

    @staticmethod
    def download_station_inventory():
        """Download the GHCN-Daily station-element inventory.

        The inventory lists, for each station and meteorological element, the
        first and last year with observations.

        Returns
        -------
        pandas.DataFrame
            Columns: ``ID``, ``Latitude``, ``Longitude``, ``ELEMENT``,
            ``FIRSTYEAR``, ``LASTYEAR``.
        """
        url = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt"
        rows = []
        for line in requests.get(url).text.splitlines():
            if not line.strip():
                continue
            rows.append(
                {
                    "ID": line[0:11].strip(),
                    "Latitude": float(line[12:20].strip()),
                    "Longitude": float(line[21:29].strip()),
                    "ELEMENT": line[31:35].strip(),
                    "FIRSTYEAR": int(line[36:40].strip()),
                    "LASTYEAR": int(line[41:45].strip()),
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def summarize_record_years(inventory_df, station_ids, elements=("PRCP",)):
        """Summarise the combined record span per station for given elements.

        Parameters
        ----------
        inventory_df : pandas.DataFrame
            Output of :meth:`download_station_inventory`.
        station_ids : array-like
            GHCN station IDs to summarise.
        elements : tuple of str, optional
            GHCN element codes to include. Defaults to ``("PRCP",)``.

        Returns
        -------
        pandas.DataFrame
            One row per station with ``record_start``, ``record_end``,
            ``record_years`` (e.g. ``"1951-2024"``) and ``elements``.
        """
        station_ids = list(station_ids)
        subset = inventory_df[
            inventory_df["ID"].isin(station_ids) & inventory_df["ELEMENT"].isin(elements)
        ].copy()
        base = pd.DataFrame({"ID": station_ids})
        if subset.empty:
            return base.assign(
                record_start=pd.NA,
                record_end=pd.NA,
                record_years=pd.NA,
                elements=pd.NA,
            )

        summary = (
            subset.groupby("ID", as_index=False)
            .agg(record_start=("FIRSTYEAR", "min"), record_end=("LASTYEAR", "max"))
        )
        element_lists = (
            subset.groupby("ID")["ELEMENT"]
            .apply(lambda values: ", ".join(sorted(set(values))))
            .reset_index(name="elements")
        )
        summary = base.merge(summary, on="ID", how="left").merge(element_lists, on="ID", how="left")
        summary["record_years"] = summary.apply(
            lambda row: (
                f"{int(row['record_start'])}-{int(row['record_end'])}"
                if pd.notna(row["record_start"]) and pd.notna(row["record_end"])
                else pd.NA
            ),
            axis=1,
        )
        return summary

    @staticmethod
    def extract_dict_data_var(GHCND_dir, var, df_country_stations):
        """Download per-station daily time series for a single GHCN variable.

        For each station in ``df_country_stations``, downloads the GHCN-Daily
        CSV from ``GHCND_dir`` and packages the result for plotting helpers in
        ``indicators_setup``.

        Parameters
        ----------
        GHCND_dir : str
            Base URL of the GHCN-Daily access directory (typically
            :data:`GHCND_ACCESS_URL`).
        var : str
            GHCN element code (e.g. ``"PRCP"``).
        df_country_stations : pandas.DataFrame
            Station metadata table with an ``ID`` column.

        Returns
        -------
        records : list of dict
            Each dict has keys ``data``, ``var``, ``ax``, ``label``.
            ``TMIN``, ``TMAX`` and ``PRCP`` are divided by 10 (GHCN stores
            them in tenths of °C or mm).
        station_ids : list of str
            Station IDs for which data were successfully retrieved.
        """
        results = []
        station_ids = []
        for i in range(len(df_country_stations)):
            station = df_country_stations.iloc[i]
            url_download = GHCND_dir + station["ID"] + ".csv"
            df = pd.read_csv(url_download, na_values=["-9999"])
            df.index = pd.to_datetime(df["DATE"])

            if var not in df.columns:
                continue

            station_ids.append(station["ID"])
            if var in ("TMIN", "TMAX", "TAVG", "PRCP"):
                df[var] = df[var] / 10

            results.append({
                "data": df[[var]],
                "var": var,
                "ax": 1,
                "label": f"Station {station['ID']}",
            })

        return results, station_ids


def download_oni_index(url=ONI_URL):
    """Download the Oceanic Niño Index (ONI) from NOAA PSL.

    Parameters
    ----------
    url : str, optional
        URL of the ONI text file. Defaults to :data:`ONI_URL`.

    Returns
    -------
    pandas.DataFrame
        Single column ``ONI`` with a monthly :class:`~pandas.DatetimeIndex`.
        Missing values encoded as ``-99.9`` in the source file are replaced
        with NaN.
    """
    content = requests.get(url).content.decode()
    oni = pd.read_csv(StringIO(content), skiprows=1, sep=r"\s+", header=None, index_col=0)[1:-8]
    oni = oni.apply(pd.to_numeric, errors="coerce")

    df = pd.DataFrame(oni.values.reshape(-1), columns=["ONI"])
    df.index = pd.date_range(start=f"{oni.index[0]}-01-01", periods=len(df), freq="MS")
    df.replace(-99.9, np.nan, inplace=True)
    return df


def filter_by_time_completeness(
    df,
    time_col="time",
    month_threshold=0.75,
    year_threshold=0.75,
):
    """Filter daily data by month and year completeness thresholds.

    Applied once in ``00_site_setup.ipynb`` before caching the station pickle.
    A month is retained when at least ``month_threshold`` of its calendar days
    have observations. A year is retained when at least ``year_threshold`` of
    its months pass the month-level test.

    Parameters
    ----------
    df : pandas.DataFrame
        Daily data with a DatetimeIndex (column ``PRCP``).
    time_col : str, optional
        Reserved for API compatibility; the index is used directly.
    month_threshold : float, optional
        Minimum fraction of days required to keep a month (default 0.75).
    year_threshold : float, optional
        Minimum fraction of valid months required to keep a year (default 0.75).

    Returns
    -------
    df_filtered : pandas.DataFrame
        Filtered daily DataFrame (helper columns removed).
    removed_months : pandas.DataFrame
        Months dropped by the filter, with a ``month_completeness`` column.
        Index: (year, month).
    removed_years : pandas.Series
        Years dropped by the filter, indexed by year.
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index)
    df["year"] = df.index.year
    df["month"] = df.index.month
    df["day"] = df.index.day

    days_present = df.groupby(["year", "month"])["day"].nunique().rename("days_present")
    days_in_month = (
        days_present.reset_index()
        .assign(
            days_in_month=lambda x: pd.to_datetime(
                dict(year=x.year, month=x.month, day=1)
            ).dt.days_in_month
        )
        .set_index(["year", "month"])["days_in_month"]
    )
    month_completeness = days_present / days_in_month
    valid_months = month_completeness >= month_threshold
    removed_months = month_completeness[~valid_months].to_frame(name="month_completeness")

    valid_months_per_year = valid_months.groupby("year").sum()
    total_months_per_year = df.groupby("year")["month"].nunique()
    year_completeness = valid_months_per_year / total_months_per_year
    valid_years = year_completeness >= year_threshold
    removed_years = year_completeness[~valid_years]

    df_filtered = df[df.set_index(["year", "month"]).index.isin(valid_months[valid_months].index)]
    df_filtered = df_filtered[df_filtered["year"].isin(valid_years[valid_years].index)]
    df_filtered = df_filtered.drop(columns=["year", "month", "day"])

    return df_filtered, removed_months, removed_years
