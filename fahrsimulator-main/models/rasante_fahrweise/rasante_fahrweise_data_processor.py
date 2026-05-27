import os
from typing import List, Optional

import pandas as pd
from pandas import DataFrame

def get_raw_data_files(folder: str = None):
    """
    Retrieves the data files from the raw_data directory.
    Args:
        folder: The dir name of the raw_data directory
    Returns:
        Files that are in the raw_data directory
    """
    path_to_raw_data_dir = './raw_data/' if folder is None else folder

    files = []
    for (root, dirs, file) in os.walk(path_to_raw_data_dir):
        for f in file:
            if f.startswith('silab') and f.endswith('.csv'):
                files.append(os.path.join(root, f))
    return files

def identify_driving_style(filename: str) -> str:
    """
    Retrieves the driving style that is extracted from the filename.
    Args:
        filename: The filename of the CSV file
    Returns:
        The driving style that was identified
    """
    return filename.split("/")[-1].split('_')[-1].split(".")[0]

def get_raw_dataframe(csv_file) -> DataFrame:
    """
    Reads the CSV file, appends the driving style column, and returns a list of DataFrames.
    Args:
        csv_file: Silab data file
    Returns:
        DataFrame
    """
    print()
    print(f"Reading file: {csv_file}")
    df: DataFrame = pd.read_csv(csv_file, encoding='ISO-8859-1')
    driving_style = identify_driving_style(csv_file)
    df["driving_style"] = [driving_style for _ in range(df.shape[0])]
    print(f"Driving style: {driving_style}")
    print(f"Raw data size: {df.size}")
    print()
    return df


def get_dataframe_windows(
        df: DataFrame,
        window_length_seconds: int = 10,
        windows_offset_seconds: int = 1
) -> List[DataFrame]:
    """
    Data will be grouped into windows of window_length_seconds seconds, each windows_difference_seconds seconds apart from one another.
    Args:
        df: Raw data as Pandas DataFrame
        window_length_seconds: windows length of each group in seconds
        windows_offset_seconds: windows offset from each other in seconds
    Returns:
        Groups, each window_length_seconds seconds-long
    """
    groups = []

    min_time = df['log_time'].min()
    max_time = df['log_time'].max()

    group_index = 0

    start_time = min_time + (group_index * windows_offset_seconds)
    latest_start_time = max_time - window_length_seconds

    while start_time <= latest_start_time:
        end_time = start_time + window_length_seconds

        # Filter data within a window_length_seconds window
        window_data = df[(df['log_time'] >= start_time) & (df['log_time'] < end_time)].copy()

        if not window_data.empty:
            window_data['window_id'] = group_index
            groups.append(window_data)

        group_index += 1

        # New start time
        start_time = min_time + (group_index * windows_offset_seconds)

    return groups


def filter_out_standstill_data(df: DataFrame) -> DataFrame | None:
    speed_series = df['speed']
    all_zero = (speed_series == 0).all()
    if all_zero:
        # Driver stood still for this group, no sensible data can be extracted
        return None

    return df


def filter_data(df: DataFrame) -> DataFrame | None:
    df = df.dropna()

    if df.empty:
        return None

    df = filter_out_standstill_data(df)
    return df


def process_group(group_dataframe: DataFrame) -> dict:
    """
    Extract important data from a group DataFrame.
    Returns:
        Dictionary with aggregated features.
    """

    speed_dif = group_dataframe['steering'].diff()
    max_acceleration = speed_dif.max()
    max_deceleration = speed_dif.min()

    steering_diff = group_dataframe['steering'].diff().abs()
    max_steering_diff = steering_diff.max()

    try:
        driving_style = group_dataframe['driving_style'].iloc[0]
    except KeyError:
        driving_style = None


    group_data = {
        'driving_style': driving_style,

        'avg_speed': group_dataframe['speed'].mean(),
        'min_speed': group_dataframe['speed'].min(),
        'max_speed': group_dataframe['speed'].max(),
        'max_acceleration': max_acceleration,
        'max_deceleration': max_deceleration,

        'max_steering': group_dataframe['steering'].max(),
        'max_steering_diff': max_steering_diff,

        'min_acc_pedal': group_dataframe['acc_pedal'].min(),
        'max_acc_pedal': group_dataframe['acc_pedal'].max(),
        'quantile_0.25_acc_pedal': group_dataframe['acc_pedal'].quantile(0.25),
        'median_acc_pedal': group_dataframe['acc_pedal'].median(),
        'quantile_0.75_acc_pedal': group_dataframe['acc_pedal'].quantile(0.75),

        'min_brake_pedal': group_dataframe['brake_pedal'].min(),
        'max_brake_pedal': group_dataframe['brake_pedal'].max(),
        'quantile_0.25_brake_pedal': group_dataframe['acc_pedal'].quantile(0.25),
        'median_brake_pedal': group_dataframe['brake_pedal'].median(),
        'quantile_0.75_brake_pedal': group_dataframe['brake_pedal'].quantile(0.25),
    }
    return group_data


def process_dataframe(df: DataFrame) -> Optional[DataFrame]:
    try:
        groups = get_dataframe_windows(df)
        filtered_groups = [filter_data(group) for group in groups]
        filtered_groups = [g for g in filtered_groups if g is not None]

        processed_groups_list = [process_group(group) for group in filtered_groups]
        result_df = pd.DataFrame(processed_groups_list)
        return result_df
    except Exception as e:
        #print(f"Error processing dataframe: {e}")
        return None


def process_raw_data(files_dir: str = None) -> DataFrame:
    csv_files = get_raw_data_files(files_dir)
    raw_dataframes = [get_raw_dataframe(file) for file in csv_files]
    processed_data = [process_dataframe(df) for df in raw_dataframes]
    merged_data = pd.concat(processed_data)

    print(f"Merged data size: {merged_data.size}")

    return merged_data