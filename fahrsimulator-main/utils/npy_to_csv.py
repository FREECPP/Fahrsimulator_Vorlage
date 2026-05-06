import glob
import re
import os
import argparse
import numpy as np
import pandas as pd

def npy_to_file(directory=".", output_file="output.csv"):
    pattern = os.path.join(directory, "tof_frame_*.npy")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"Keine Dateien gefunden in: {directory}")
        return

    rows = []
    for filepath in files:
        match = re.search(r"tof_frame_(\d+\.\d+)\.npy$", filepath)
        if not match:
            print(f"Überspringe {filepath}: Zeitstempel nicht erkannt")
            continue
        timestamp = float(match.group(1))
        data = np.load(filepath).flatten()
        rows.append({"timestamp": timestamp, "data": data})

    if not rows:
        print("Keine gültigen Dateien gefunden.")
        return

    df = pd.DataFrame({
        "timestamp": [r["timestamp"] for r in rows],
        **{f"v{i}": [r["data"][i] for r in rows] for i in range(len(rows[0]["data"]))}
    })

    df.to_csv(output_file, index=False)
    print(f"{len(rows)} Dateien verarbeitet -> {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Konvertiert tof_frame_*.npy Dateien in CSV.")
    parser.add_argument("directory", nargs="?", default=".", help="Verzeichnis mit den .npy Dateien (Standard: aktuelles Verzeichnis)")
    args = parser.parse_args()
    npy_to_file(directory=args.directory)