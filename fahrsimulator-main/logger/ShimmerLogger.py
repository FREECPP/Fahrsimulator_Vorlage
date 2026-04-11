from pyshimmer import ShimmerBluetooth, DataPacket
from pyshimmer.dev.channels import EChannelType
from logger.logger import Logger, LOG_TIME_KEY
from pathlib import Path
from typing import Union, Optional
from utils.bt_connector import connect_to_shimmer
from utils.heart_rate_analyser import get_hr_measures
import time
from queue import Full, Empty
import configparser
import os
from utils.app_logging_utils import printlog
from utils.queue_utils import put_latest
import matplotlib
matplotlib.use('Agg') 

def load_shimmer_addr() -> str:
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found: {config_path}")
    config.read(config_path)

    try:
        mac_addr = str(config.get('General', 'ShimmerAddress'))
        return mac_addr
    except Exception as e:
        printlog(
            f"Data from 'config.ini' couldn't be read. Versichern Sie sich, dass PORT und HOST unter [General] existieren. {e}",
            "error")
        return "00:06:66:1C:40:75"

class ShimmerLogger(Logger):
    CSV_FIELDS = [
        "shimmer_timestamp",
        "accel_ln_x",
        "accel_ln_y",
        "accel_ln_z",
        "internal_adc_13",
        "gsr_raw"
    ]

    def __init__(
        self,
        file: Union[Path, str],
        queues = None,
    ):
        super().__init__(file, self.CSV_FIELDS)
        self.adc_values = list()
        self._shimmer_device: Optional[ShimmerBluetooth] = None
        self.adc_value_count = 0

        self.queues = queues or {}
        self.shimmer_queue = self.queues.get("shimmer")
        self.shimmer_hrv_queue = self.queues.get("shimmer_hrv")

        self.shimmer_addr = load_shimmer_addr()

        # Mittlere Übertragungslatenz in Nanosekunden (wird nach Kalibrierung eingefroren)
        self.mean_latency = 0.0
        # Korrigierter Aufnahmezeitpunkt im time.time()-Format (Sekunden)
        self.capture_time = None
        # Systemzeit direkt vor start_streaming() als Referenzpunkt für die Latenzberechnung
        self._stream_start_ns = None
        # Shimmer-Timestamp des ersten empfangenen Pakets als Takt-Referenz
        self._shimmer_ref_ts = None
        # Umrechnungsfaktor: wie viele Nanosekunden entsprechen einem Shimmer-Tick
        self._ns_per_tick = None
        # Rohdaten für die Kalibrierung: Liste von (shimmer_ts, recv_ns)-Tupeln
        self._latency_cal_samples = []
        # Wird True gesetzt sobald die Kalibrierung abgeschlossen ist
        self._latency_cal_done = False

    def start_sensor(self) -> None:
        super().start_sensor()
        self._shimmer_device = connect_to_shimmer(self.shimmer_addr)
        self._shimmer_device.add_stream_callback(self.handler)

    def start_logging(self, stop_event) -> None:
        super().start_logging()
        # Systemzeit festhalten bevor Streaming startet – dient als Referenz für die Latenzberechnung
        self._stream_start_ns = time.time_ns()
        self._shimmer_device.start_streaming()
        while not stop_event.is_set():
            time.sleep(0.05)

    def stop_logging(self) -> None:
        print("Stopping Shimmer logger.")

        if self._shimmer_device is not None:
            self._shimmer_device.stop_streaming()
            self._shimmer_device.remove_stream_callback(self.handler)
            self._shimmer_device.shutdown()
            self._shimmer_device = None

        super().stop_logging()
        print("Shimmer logger stopped.")

    def handler(self, pkt: DataPacket) -> None:
        # Empfangszeit so früh wie möglich messen um Verarbeitungszeit nicht einzurechnen
        recv_ns = time.time_ns()
        channel_mapping = {
            EChannelType.TIMESTAMP: "shimmer_timestamp",
            EChannelType.ACCEL_LN_X: "accel_ln_x",
            EChannelType.ACCEL_LN_Y: "accel_ln_y",
            EChannelType.ACCEL_LN_Z: "accel_ln_z",
            EChannelType.INTERNAL_ADC_13: "internal_adc_13",
            EChannelType.GSR_RAW: "gsr_raw"
        }

        mapped_data = {}
        for channel, value in pkt._values.items():
            if channel in channel_mapping:
                csv_field = channel_mapping[channel]
                mapped_data[csv_field] = value
        
        shimmer_ts = mapped_data.get("shimmer_timestamp")
        if shimmer_ts is not None:
            self._update_latency(shimmer_ts, recv_ns)

        if self.shimmer_queue is not None:
            put_latest(self.shimmer_queue, mapped_data)

        if self.capture_time is not None:
            mapped_data[LOG_TIME_KEY] = self.capture_time
        self.write_row(mapped_data)
        self.handle_hrv(mapped_data)

    def _update_latency(self, shimmer_ts: float, recv_ns: int) -> None:
        # Erstes Paket: Shimmer-Timestamp als Takt-Referenz speichern, noch keine Berechnung möglich
        if self._shimmer_ref_ts is None:
            self._shimmer_ref_ts = shimmer_ts
            return

        # Kalibrierungsphase: Sammle die ersten 100 Pakete um ns_per_tick und mean_latency zu berechnen
        if not self._latency_cal_done:
            self._latency_cal_samples.append((shimmer_ts, recv_ns))
            if len(self._latency_cal_samples) >= 100:
                # Vergangene Shimmer-Ticks und Systemzeit über alle Kalibrierungspakete
                ts_delta = self._latency_cal_samples[-1][0] - self._latency_cal_samples[0][0]
                sys_delta = self._latency_cal_samples[-1][1] - self._latency_cal_samples[0][1]
                if ts_delta > 0:
                    # Umrechnungsfaktor: Nanosekunden pro Shimmer-Tick (empirisch abgeleitet)
                    self._ns_per_tick = sys_delta / ts_delta
                    latency_samples = []
                    for ts, recv in self._latency_cal_samples:
                        # Erwartete Systemzeit dieses Pakets basierend auf Shimmer-Takt
                        sensor_elapsed_ns = (ts - self._shimmer_ref_ts) * self._ns_per_tick
                        # Latenz = tatsächliche Empfangszeit minus erwartete Empfangszeit
                        latency_samples.append(recv - (self._stream_start_ns + sensor_elapsed_ns))
                    # Mittlere Latenz einfrieren – wird für alle weiteren Pakete verwendet
                    self.mean_latency = sum(latency_samples) / len(latency_samples)
                    self._latency_cal_done = True
                    printlog(f"Shimmer Latenz kalibriert: {self.mean_latency / 1e6:.2f} ms", "info")
            return

        # Korrekter Aufnahmezeitpunkt: Empfangszeit minus eingefrorene Latenz, umgerechnet in Sekunden
        self.capture_time = (recv_ns - self.mean_latency) / 1e9

    def handle_hrv(self, data: dict):
        adc_value = data.get("internal_adc_13", None)
        if adc_value is None:
            return
        self.adc_values.append(adc_value)
        self.adc_values = self.adc_values[-10000:] # Only keep the last 10000 values
        self.adc_value_count += 1

        if self.adc_value_count % 200 == 0 and len(self.adc_values) >= 1000: # If we have at least 1000 values, calculate HRV for every 200 values
            working_data, measures = get_hr_measures(self.adc_values)
            print(f"sdnn: {measures['sdnn']}   ----   rmssd: {measures['rmssd']}")
            if self.shimmer_hrv_queue is not None:
                put_latest(self.shimmer_hrv_queue, measures)

