import pandas as pd
import numpy as np
from typing import List

FEATURE_BASE_COLS = [
    "head_distance",
    "yaw",
    "yaw_abs",
    "head_pitch_deg",
    "right_wrist_on_wheel",
    "left_wrist_on_wheel",
    "right_thumb_on_wheel",
    "left_thumb_on_wheel",
]

def build_time_segments(
    input_csv: str,
    output_csv: str,
    timestamp_col: str = "timestamp",
    label_col: str = "label",
    window_s: float = 2.0,
    step_s: float = 1.0,
    min_frames_per_seg: int = 2,
) -> pd.DataFrame:
    """
    Erzeugt überlappende Zeitsegmente aus Frame-Daten und speichert aggregierte Features pro Segment.

    - Liest eine CSV mit Frame-basierten Daten (inkl. Timestamp und Label pro Frame)
    - Bildet überlappende Zeitfenster (z.B. 2s Window, 1s Schritt)
    - Aggregiert numerische Features (mean, std) pro Segment
    - Bestimmt das Segment-Label über Mehrheitsentscheidung (>50% Label=1 → 1, sonst 0)
    - Speichert das Ergebnis als neue CSV und gibt das Segment-DataFrame zurück.
    """
    df = pd.read_csv(input_csv)
    df[timestamp_col] = df[timestamp_col].astype(float)
    df = df.sort_values(by=timestamp_col).reset_index(drop=True)

    t_min = df[timestamp_col].min()
    t_max = df[timestamp_col].max()

    segments = []

    window_start = t_min
    while window_start + window_s <= t_max:
        window_end = window_start + window_s

        mask = (df[timestamp_col] >= window_start) & (df[timestamp_col] < window_end)
        seg_df = df[mask]

        if len(seg_df) >= min_frames_per_seg:
            seg_data = {}

            seg_data["t_start"] = window_start
            seg_data["t_end"] = window_end
            seg_data["num_frames"] = len(seg_df)

            for col in FEATURE_BASE_COLS:
                seg_data[f"{col}_mean"] = seg_df[col].mean()

            frac_ones = seg_df[label_col].mean()
            seg_data["frac_label_1"] = frac_ones   

            seg_label = 1 if frac_ones > 0.5 else 0
            seg_data[label_col] = seg_label

            segments.append(seg_data)

        window_start += step_s

    seg_df_out = pd.DataFrame(segments)
    seg_df_out.to_csv(output_csv, index=False)

    print(f"Gespeichert: {output_csv}")
    print(f"Anzahl Segmente: {len(seg_df_out)}")
    print("Spalten:", list(seg_df_out.columns))
    return seg_df_out


if __name__ == "__main__":
    INPUT_CSV = r"C:/Users/louis/fahrsimulator/driverDistractionModel/model_train/train_data/extracted_features.csv"
    OUTPUT_CSV = r"C:/Users/louis/fahrsimulator/driverDistractionModel/model_train/train_data/extracted_segments.csv"

    build_time_segments(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        timestamp_col="timestamp",
        label_col="label",
        window_s=2.0,
        step_s=1.0,
        min_frames_per_seg=2,
    )
