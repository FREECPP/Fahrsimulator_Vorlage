from pyshimmer import ShimmerBluetooth, DataPacket
from pyshimmer.dev.channels import EChannelType
from logger.logger import Logger, LOG_TIME_KEY
from pathlib import Path
from typing import Union, Optional
from utils.bt_connector import connect_to_shimmer
from utils.heart_rate_analyser import get_hr_measures
import time
from multiprocessing import Event
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

    # Bitbreite des Shimmer-Hardware-Timestamps. Der Zähler läuft alle
    # 2**24 / 32768 Hz ≈ 8,5 min um; bei Überlauf wird ein voller Umlauf addiert.
    # (Falls dein Gerät eine andere Timestamp-Breite nutzt, hier anpassen.)
    SHIMMER_TS_MODULO = 2 ** 24

    def __init__(
        self,
        file: Union[Path, str],
        queues = None,
    ):
        super().__init__(file, self.CSV_FIELDS)
        self.adc_values = list()
        self._shimmer_device: Optional[ShimmerBluetooth] = None
        self.adc_value_count = 0
        self._latest_hrv = {
            "heart_rate": None,
            "rmssd": None,
            "sdnn": None,
        }

        self.connection_started_at = None
        self._latest_gsr_raw = None

        self.queues = queues or {}
        self.shimmer_queue = self.queues.get("shimmer")

        self.sensor_status_queue = self.queues.get(
            "sensor_status"
        )

        self.sensor_latency_queue = self.queues.get("sensor_latency")

        self.sensor_key = "shimmer"
        self.sensor_name = "Shimmer"

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
        # Wrap-Handling des Hardware-Timestamps: akkumulierter Offset und letzter Rohwert,
        # damit aus dem umlaufenden Geräte-Zähler ein monoton steigender Tick wird
        self._ts_unwrap_offset = 0
        self._prev_raw_ts = None
        # Rohdaten für die Kalibrierung: Liste von (shimmer_ts, recv_ns)-Tupeln
        self._latency_cal_samples = []
        # Wird True gesetzt sobald die Kalibrierung abgeschlossen ist
        self._latency_cal_done = False
        # Flag damit start_logging einmalig ausgeführt werden kann
        self.x = 0
        self.log_event = None
        self.stop_event = None

    def start_sensor(self, stop_event, log_event) -> None:
        self.connection_started_at = time.time()
        if self.sensor_status_queue:
            self.sensor_status_queue.put({
                "key": self.sensor_key,
                "name": self.sensor_name,
                "status": "loading",
                "duration": 0,
                "error": "",
                "ready": False,
            })

        try:

            super().start_sensor()

            self.log_event = log_event
            self.stop_event = stop_event

            self._shimmer_device = connect_to_shimmer(
                self.shimmer_addr
            )

            self._shimmer_device.add_stream_callback(
                self.handler
            )

            self._stream_start_ns = time.time_ns()

            self._shimmer_device.start_streaming()

            while not stop_event.is_set():
                time.sleep(0.05)

        except Exception as e:

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "error",
                    "duration": 0,
                    "error": str(e),
                    "ready": False,
                })

            raise

    def start_logging(self) -> None:
        super().start_logging()


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
        try:
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

            gsr_value = mapped_data.get("gsr_raw")
            if gsr_value is not None:
                self._latest_gsr_raw = gsr_value

            if self.shimmer_queue is not None:
                payload = dict(mapped_data)
                if self._latest_hrv.get("heart_rate") is not None:
                    payload["heart_rate"] = self._latest_hrv["heart_rate"]
                if self._latest_hrv.get("rmssd") is not None:
                    payload["rmssd"] = self._latest_hrv["rmssd"]
                if self._latest_hrv.get("sdnn") is not None:
                    payload["sdnn"] = self._latest_hrv["sdnn"]
                if self._latest_gsr_raw is not None:
                    payload["skin_resistance"] = self._latest_gsr_raw
                put_latest(self.shimmer_queue, payload)

            self.handle_hrv(mapped_data)

            if self.log_event.is_set():
                if self.x == 0:
                    self.start_logging()
                    self.x = 1
                if self.capture_time is not None:
                    mapped_data[LOG_TIME_KEY] = self.capture_time
                self.write_row(mapped_data)
        except Exception as e:

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "error",
                    "duration": 0,
                    "error": str(e),
                    "ready": False,
                })

            raise

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
                    """if self.sensor_status_queue:
                        self.sensor_status_queue.put({
                            "key": self.sensor_key,
                            "name": self.sensor_name,
                            "status": "success",
                            "duration": (
                                    time.time() - self.connection_started_at
                            ),
                            "latency_ms": round(
                                self.mean_latency / 1e6,
                                2
                            ),
                            "error": "",
                            "ready": True,
                        })
                    printlog(f"Shimmer Latenz kalibriert: {self.mean_latency / 1e6:.2f} ms", "info")"""
                    if self.sensor_latency_queue:
                        self.sensor_latency_queue.put({
                            "key": "shimmer",
                            "latency_ms": round(self.mean_latency / 1e6, 2),
                                                    })
            return

        # Korrekter Aufnahmezeitpunkt aus dem Geräte-Takt statt aus der Host-Empfangszeit:
        # shimmer_ts zählt pro Sample eindeutig hoch. recv_ns dagegen kollidiert, weil
        # Bluetooth die Samples gebündelt liefert und mehrere Pakete fast gleichzeitig
        # ankommen -> sonst doppelte log_time bei unterschiedlichen shimmer_timestamps.
        # Der entwrappte Tick wird über _ns_per_tick in die Systemzeit-Domäne abgebildet.
        unwrapped_ts = self._unwrap_ts(shimmer_ts)
        self.capture_time = (
            self._stream_start_ns
            + (unwrapped_ts - self._shimmer_ref_ts) * self._ns_per_tick
        ) / 1e9

    def _unwrap_ts(self, raw_ts: float) -> float:
        """Macht aus dem umlaufenden Hardware-Timestamp einen monoton steigenden Wert.

        Der Shimmer-Zähler springt nach SHIMMER_TS_MODULO Ticks zurück auf 0. Sinkt der
        Rohwert gegenüber dem letzten Paket, ist ein Überlauf passiert und wir addieren
        einen vollen Umlauf. Dadurch bleibt (unwrapped_ts - _shimmer_ref_ts) auch über
        lange Aufnahmen streng steigend -> eindeutige, monotone log_time.
        """
        if self._prev_raw_ts is not None and raw_ts < self._prev_raw_ts:
            self._ts_unwrap_offset += self.SHIMMER_TS_MODULO
        self._prev_raw_ts = raw_ts
        return raw_ts + self._ts_unwrap_offset

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
            self._latest_hrv = {
                "heart_rate": measures.get("bpm"),
                "rmssd": measures.get("rmssd"),
                "sdnn": measures.get("sdnn"),
            }
            if self.shimmer_queue is not None:
                payload = {
                    "heart_rate": self._latest_hrv.get("heart_rate"),
                    "rmssd": self._latest_hrv.get("rmssd"),
                    "sdnn": self._latest_hrv.get("sdnn"),
                    "skin_resistance": self._latest_gsr_raw,
                }
                put_latest(self.shimmer_queue, payload)

