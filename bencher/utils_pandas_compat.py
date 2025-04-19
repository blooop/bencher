"""
Utility module for handling compatibility issues with newer pandas versions.
Specifically addresses issues with MultiIndex creation in HoloViews.
"""

import pandas as pd
import logging


class DataFrameAdapter:
    """
    Adapter class that provides DataFrame with xarray-like interface
    so HoloViews can work with DataFrame as if it were xarray Dataset.
    """

    def __init__(self, df):
        """
        Initialize with a DataFrame

        Args:
            df (pandas.DataFrame): The DataFrame to adapt
        """
        self._df = df

        # Create sizes attribute (missing in DataFrame but expected by HoloViews)
        self.sizes = {}

        # From index levels
        if isinstance(df.index, pd.MultiIndex):
            for level_name in df.index.names:
                if level_name is not None:
                    self.sizes[level_name] = len(df.index.get_level_values(level_name).unique())
        elif df.index.name:
            self.sizes[df.index.name] = len(df.index.unique())

        # From regular columns
        for col in df.columns:
            if col not in self.sizes:
                self.sizes[col] = len(df[col].unique()) if not df[col].isna().all() else 0

    def __getattr__(self, attr):
        """Pass through attributes to the wrapped DataFrame"""
        if hasattr(self._df, attr):
            return getattr(self._df, attr)
        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{attr}'")

    def to_dataframe(self):
        """Return the underlying DataFrame"""
        return self._df

    @property
    def data(self):
        """Access to the data property"""
        return self._df

    @property
    def dims(self):
        """xarray-like dims attribute"""
        return list(self.sizes.keys())


def adapt_for_holoviews(dataset):
    """
    Adapts a dataset (DataFrame or xarray Dataset) for use with HoloViews

    Args:
        dataset: The dataset to adapt

    Returns:
        A dataset that works with HoloViews
    """
    if isinstance(dataset, pd.DataFrame):
        return DataFrameAdapter(dataset)
    return dataset


def prepare_dataframe_for_holoviews(df, index_cols):
    """
    Prepares a DataFrame for HoloViews by ensuring necessary index columns exist.

    Args:
        df (pd.DataFrame): The DataFrame to prepare
        index_cols (list): List of column names that will be used as index

    Returns:
        pd.DataFrame: The prepared DataFrame with all necessary columns
    """
    if not isinstance(index_cols, list):
        index_cols = [index_cols]

    # Check if any columns are missing
    missing_cols = [col for col in index_cols if col not in df.columns]

    if missing_cols:
        # Create a copy to avoid modifying the original
        df_copy = df.copy()

        # For MultiIndex dataframes, reset the index to get index levels as columns
        if isinstance(df.index, pd.MultiIndex):
            df_copy = df_copy.reset_index()

        # Add any still missing columns
        still_missing = [col for col in missing_cols if col not in df_copy.columns]
        for col in still_missing:
            logging.warning(f"Adding missing column '{col}' as None for HoloViews compatibility")
            df_copy[col] = None

        return df_copy

    return df


def prepare_dataset_for_holoviews(dataset, index_cols=None):
    """
    Prepares an xarray Dataset for HoloViews plotting.

    Args:
        dataset (xr.Dataset): The xarray Dataset to prepare
        index_cols (list, optional): List of column names to ensure exist

    Returns:
        xr.Dataset or pd.DataFrame: Prepared dataset for HoloViews
    """
    # If it's already a DataFrame, just prepare it
    if isinstance(dataset, pd.DataFrame):
        return prepare_dataframe_for_holoviews(dataset, index_cols or [])

    # If index_cols not provided, use all dimensions from the dataset
    if index_cols is None:
        index_cols = list(dataset.dims)

    # Convert to pandas DataFrame and prepare
    df = dataset.to_dataframe()
    return prepare_dataframe_for_holoviews(df, index_cols)
