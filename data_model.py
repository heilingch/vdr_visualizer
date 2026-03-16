"""
VDR Data Model - Manages parsed data with filtering and resampling.
"""
import pandas as pd
from typing import List, Optional, Dict
from vdr_parser import VDRParser, VARIABLE_CATEGORIES, get_category


class VDRDataModel:
    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.parser = VDRParser()

    def load_files(self, filepaths: List[str]):
        """Load and merge multiple VDR files."""
        dfs = []
        for fp in filepaths:
            df = self.parser.parse_file(fp)
            if not df.empty:
                dfs.append(df)

        if dfs:
            self.raw_data = pd.concat(dfs).sort_index()
            # Forward-fill sparse sensor data (up to 5 rows) so that
            # rows recorded at the same second can be plotted together.
            self.raw_data = self.raw_data.ffill(limit=5)
        else:
            self.raw_data = pd.DataFrame()

    def get_data(
        self,
        variables: List[str],
        time_range_hours: Optional[float] = None,
        downsample_str: Optional[str] = None,
        moving_average_window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Retrieve data for specific variables, optionally filtered by time
        and downsampled.
        """
        if self.raw_data is None or self.raw_data.empty:
            return pd.DataFrame()

        cols = [c for c in variables if c in self.raw_data.columns]
        if not cols:
            return pd.DataFrame()

        df = self.raw_data[cols].copy()

        # Time-range filter
        if time_range_hours is not None and time_range_hours > 0:
            end_time = df.index.max()
            start_time = end_time - pd.Timedelta(hours=time_range_hours)
            df = df.loc[start_time:end_time]

        # Downsample
        if downsample_str:
            df = df.resample(downsample_str).mean()
            
        # Moving Average
        if moving_average_window is not None and moving_average_window > 1:
            df = df.rolling(window=moving_average_window, min_periods=1).mean()

        # Drop rows where ALL selected variables are NaN
        df = df.dropna(how='all')
        return df

    @property
    def available_variables(self) -> List[str]:
        if self.raw_data is not None and not self.raw_data.empty:
            return sorted(self.raw_data.columns.tolist())
        return []

    @property
    def available_categories(self) -> Dict[str, List[str]]:
        """Return available variables grouped by category."""
        cats: Dict[str, List[str]] = {}
        for var in self.available_variables:
            cat = get_category(var)
            cats.setdefault(cat, []).append(var)
        return cats
