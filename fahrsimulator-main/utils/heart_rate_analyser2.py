import heartpy as hp
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


def process_data(file_path='../logger/logfiles/20260107_173645_Logs/shimmer_log.csv'):
    """
    Verarbeitet Shimmer PPG-Daten mit Preprocessing für heartpy.
    """
    df = _read_values_from_file(file_path=file_path)
    data = df['internal_adc_13'].values

    # Preprocessing: Filterung und Normalisierung
    filtered_data = preprocess_ppg_signal(data)

    working_data, measures = get_hr_measures(filtered_data)
    print(f"sdnn: {measures['sdnn']:.2f}   ----   rmssd: {measures['rmssd']:.2f}")
    return working_data, measures


def preprocess_ppg_signal(data, sample_rate=128):
    """
    Preprocessing für rohe PPG-Daten von Shimmer.

    Args:
        data: Rohe Sensordaten
        sample_rate: Sample-Rate (128 Hz für Shimmer)

    Returns:
        Gefilterte und normalisierte Daten
    """
    # 1. NaN/Inf-Werte entfernen
    data = np.nan_to_num(data, nan=np.nanmean(data))

    # 2. Baseline-Entfernung (Detrending)
    data = signal.detrend(data)

    # 3. Butterworth High-Pass Filter (> 0.5 Hz)
    # Entfernt langsame Baseline-Drifts
    sos = signal.butter(3, 0.5, 'hp', fs=sample_rate, output='sos')
    data = signal.sosfilt(sos, data)

    # 4. Butterworth Low-Pass Filter (< 4 Hz)
    # Entfernt Hochfrequenz-Rauschen
    sos = signal.butter(3, 4.0, 'lp', fs=sample_rate, output='sos')
    data = signal.sosfilt(sos, data)

    # 5. Normalisierung auf [-1, 1]
    data_max = np.max(np.abs(data))
    if data_max > 0:
        data = data / data_max

    # 6. Optional: Verstärkung des Signals
    data = data * 100  # heartpy mag größere Werte

    return data


def _read_values_from_file(file_path):
    df = pd.read_csv(file_path)
    return df


def get_hr_measures(data, sample_rate=128):
    """
    Berechnet HRV-Metriken mit heartpy.

    Args:
        data: Gefilterte PPG-Daten
        sample_rate: Sample-Rate (128 Hz für Shimmer)
    """
    try:
        data_array = np.array(data, dtype=np.float64)

        # HeartPy Processing
        working_data, measures = hp.process(hrdata=data_array, sample_rate=sample_rate)

        # Plotting
        plt.figure(figsize=(12, 4))
        hp.plotter(working_data, measures)

        return working_data, measures

    except ValueError as e:
        print(f"❌ HeartPy Fehler: {e}")
        print("Tipps:")
        print("  - Signal-Länge prüfen (mind. 10 Sekunden empfohlen)")
        print("  - Sensor korrekt befestigt?")
        print("  - Bewegungsartefakte?")
        return None, None


if __name__ == "__main__":
    working_data, measures = process_data()

    if measures:
        print("\nHRV-Metriken:")
        print(f"  BPM: {measures['bpm']:.1f}")
        print(f"  SDNN: {measures['sdnn']:.2f} ms")
        print(f"  RMSSD: {measures['rmssd']:.2f} ms")
        print(f"  PNN50: {measures['pnn50']:.2%}")
        plt.show()