import heartpy as hp
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np



def process_data(file_path ='../logger/logfiles/20260107_173645_Logs/shimmer_log.csv'):
    """
    Data returned by hp.process:
    {
    'bpm': 114.12119804968656,
    'ibi': 525.7568359375,
    'sdnn': 179.19152682476226,
    'sdsd': 74.62502062635069,
    'rmssd': 88.52767258378005,
    'pnn20': 0.40384615384615385,
    'pnn50': 0.23076923076923078,
    'hr_mad': 93.75,
    'sd1': 62.591215306439935,
    'sd2': 210.47908438175006,
    's': 41387.78674449894,
    'sd1/sd2': 0.2973749885424103,
    'breathingrate': 0.13333333333333333
    }
    sdnn is standard deviation of nn intervals and is useful for heart rate variability over a long time
    rmssd is the root-mean-square of successive differences and is a valuable measure for heart rate variability over a short time
    """
    df = _read_values_from_file(file_path=file_path)
    data = df['internal_adc_13'].values
    working_data, measures = get_hr_measures(data)
    print(f"sdnn: {measures['sdnn']}   ----   rmssd: {measures['rmssd']}")
    return working_data, measures

def _read_values_from_file(file_path):
    df = pd.read_csv(file_path)
    return df

def get_hr_measures(data):
    sample_rate = 128  # Sample rate of PPG. See: https://www.shimmersensing.com/support/sample-data/
    data_array = np.array(data, dtype=np.float64)
    working_data, measures = hp.process(hrdata=data_array, sample_rate=sample_rate)
    plt.figure(figsize=(12, 4))
    hp.plotter(working_data, measures)

    # The below way of processing could be interesting, sadly, segment_plotter does not seem to work
    #working_data, measures = hp.process_segmentwise(hrdata=data, sample_rate=sample_rate, segment_width=10, segment_overlap=0.25)
    #hp.segment_plotter(working_data=working_data, measures=measures)

    return working_data, measures