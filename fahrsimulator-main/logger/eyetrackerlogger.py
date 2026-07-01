from sqlalchemy.testing.plugin.plugin_base import stop_test_class_outside_fixtures

from logger.logger import Logger, LOG_TIME_KEY
from pathlib import Path
from typing import Union, Optional
import tobii_research
import time
import queue as _queue
import json
from multiprocessing import Event
import utils.Koordinaten_Tranformation.transform_coord as tc

from utils.queue_utils import put_latest


class EyetrackerLogger(Logger):
    CSV_FIELDS = [
        "device_time_stamp",
        "system_time_stamp",
        "left_gaze_point_on_display_area",
        "right_gaze_point_on_display_area",
        "left_gaze_origin_in_user_coordinate_system",
        "right_gaze_origin_in_user_coordinate_system",
        "left_gaze_point_in_user_coordinate_system",
        "right_gaze_point_in_user_coordinate_system",
        "left_pupil_diameter",
        "right_pupil_diameter",
        "left_gaze_origin_in_global_coordinate_system",
        "right_gaze_origin_in_global_coordinate_system"
    ]

    def __init__(
            self,
            file: Union[Path, str],
            device_index: int = 0,
            as_dictionary: bool = True,
            queues=None
    ):
        super().__init__(file, self.CSV_FIELDS)
        self._device: Optional[object] = None
        self.device_index = device_index
        self.as_dictionary = as_dictionary
        self.queues = queues or {}
        self.connection_started_at = None
        self.eyetracker_queue = self.queues.get("eyetracker")
        self.status_queue = self.queues.get("sensor_status")
        self.sensor_latency_queue = self.queues.get("sensor_latency")
        # Korrigierter Aufnahmezeitpunkt im time.time()-Format, wird pro Paket aktualisiert
        self.capture_time = None
        # Systemzeit in Nanosekunden direkt vor subscribe_to() als Referenzpunkt für die Latenzberechnung
        self._stream_start_ns = None
        # device_time_stamp des ersten empfangenen Pakets als Takt-Referenz
        self._device_ref_ts = None
        # Umrechnungsfaktor: wie viele Nanosekunden Systemzeit entsprechen einem device_time_stamp-Tick
        self._ns_per_tick = None
        # Mittlere Übertragungslatenz in Nanosekunden (wird nach Kalibrierung eingefroren)
        self.mean_latency = 0.0
        # Rohdaten für die Kalibrierung: Liste von (device_ts, recv_ns)-Tupeln
        self._latency_cal_samples = []
        # Wird True gesetzt sobald die Kalibrierung abgeschlossen ist
        self._latency_cal_done = False
        self.log_event = None
        self.x = 0
        self.transformations_matrizen = tc.lade_sensor_matrizen()

    def _gaze_callback(self, gaze_data):
        # Empfangszeit so früh wie möglich messen um Verarbeitungszeit nicht einzurechnen
        recv_ns = time.time_ns()
        device_ts = gaze_data.get("device_time_stamp")
        if device_ts is not None:
            self._update_latency(device_ts, recv_ns)
        #print(f"Tobii-Device-Timestamp: {device_ts}")
        if self.log_event.is_set():
            if self.x == 0:
                self.start_logging()
                x = 1
        if self.capture_time is not None:
            self.process_data(gaze_data)
        if self.eyetracker_queue is not None:
            # NaN/Infinity (z.B. Blick weg, keine Augen erkannt) -> None, statt das Paket zu verwerfen.
            # So bleibt der Datenstrom (und damit der Heartbeat) erhalten, solange der Tobii sendet.
            cleaned_data = json.loads(
                json.dumps(gaze_data, default=lambda v: None),
                parse_constant=lambda c: None,
            )
            put_latest(self.eyetracker_queue, cleaned_data)

    def _sync_callback(self, sync_data):
        #print(f"System_time_synced: {sync_data}")
        self._device.subscribe_to(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback,
                                  as_dictionary=self.as_dictionary)

    def _update_latency(self, device_ts: float, recv_ns: int) -> None:
        # Erstes Paket: device_time_stamp als Takt-Referenz speichern, noch keine Berechnung möglich
        if self._device_ref_ts is None:
            self._device_ref_ts = device_ts
            return

        # Kalibrierungsphase: erste 100 Pakete sammeln um ns_per_tick und mean_latency zu berechnen
        if not self._latency_cal_done:
            self._latency_cal_samples.append((device_ts, recv_ns))
            if len(self._latency_cal_samples) >= 100:
                # Vergangene device-Ticks und Systemzeit über alle Kalibrierungspakete
                ts_delta = self._latency_cal_samples[-1][0] - self._latency_cal_samples[0][0]
                sys_delta = self._latency_cal_samples[-1][1] - self._latency_cal_samples[0][1]
                if ts_delta > 0:
                    # Umrechnungsfaktor: Nanosekunden pro device_time_stamp-Tick (empirisch abgeleitet)
                    self._ns_per_tick = sys_delta / ts_delta

                    #offsets_i = Empfangszeit - verstrichene Gerätezeit = C_ref + Latenz
                    offsets = []
                    for d_ts, r_ns in self._latency_cal_samples:
                        # Erwartete Systemzeit dieses Pakets basierend auf device-Takt
                        sensor_elapsed_ns = (d_ts - self._device_ref_ts) * self._ns_per_tick
                        # Latenz = tatsächliche Empfangszeit minus erwartete Empfangszeit
                        offsets.append(r_ns - sensor_elapsed_ns)

                    # kleinster offset = schnellstes Paket = beste Annäherung für die echte 
                    # Unix-Aufnahmezeit des Referenzpakets (C_ref)
                    self._capture_offset_ns = min(offsets)

                    # Mittlere Latenz einfrieren – wird für alle weiteren Pakete verwendet
                    self.mean_latency = sum(offsets) / len(offsets) - self._capture_offset_ns
                    self._latency_cal_done = True
                    if self.sensor_latency_queue:
                        self.sensor_latency_queue.put({
                            "key": "eyetracker",
                            "latency_ms": round(self.mean_latency / 1e6, 2),

                        })
                    print(f"Eyetracker Latenz kalibriert: {self.mean_latency / 1e6:.2f} ms")
            return

        # Korrekter Aufnahmezeitpunkt aus dem Geräte-Takt
        self.capture_time = (
            self._capture_offset_ns
            + (device_ts - self._device_ref_ts) * self._ns_per_tick
        ) / 1e9

    def process_data(self, data: Union[bytes, str, dict]) -> None:
        """Expects dict from SDK; writes CSV-Row."""
        if isinstance(data, dict):
            if self.capture_time is not None:
                data[LOG_TIME_KEY] = self.capture_time

                # aus globalen Koordinaten lokale erstellen
                local_left_eye_coord = data.get("left_gaze_origin_in_user_coordinate_system")
                local_right_eye_coord = data.get("right_gaze_origin_in_user_coordinate_system")
                if local_left_eye_coord is not None and local_right_eye_coord is not None:
                    local_point_right_in_m = [coord / 1000.0 for coord in local_right_eye_coord]
                    local_point_left_in_m = [coord / 1000.0 for coord in local_left_eye_coord]
                    global_right_eye_point = tc.transform_lokal_coordinate_in_global_space(local_point_right_in_m, "tobii", self.transformations_matrizen)
                    global_left_eye_point = tc.transform_lokal_coordinate_in_global_space(local_point_left_in_m, "tobii", self.transformations_matrizen)
                    data["left_gaze_origin_in_global_coordinate_system"] = global_left_eye_point
                    data["right_gaze_origin_in_global_coordinate_system"] = global_right_eye_point
            self.write_row(data)
            return

        raise ValueError(f"Unexpected data type: {type(data)}")

    def start_sensor(self, stop_event, log_event) -> None:

        self.connection_started_at = time.time()

        if self.status_queue:
            self.status_queue.put({
                "key": "eyetracker",
                "name": "Eyetracker",
                "status": "loading",
                "duration": 0,
                "error": "",
                "ready": False,
                "started_at": self.connection_started_at
            })

        super().start_sensor()
        self.log_event = log_event

        try:
            found_eyetrackers = tobii_research.find_all_eyetrackers()
            self._device = found_eyetrackers[self.device_index]
            print(f"Using eyetracker: {self._device.device_name} @ {self._device.address}")

            if self.status_queue:
                self.status_queue.put({
                    "key": "eyetracker",
                    "name": "Eyetracker",
                    "status": "success",
                    "duration": (time.time() - self.connection_started_at),
                    "error": "",
                    "ready": True,

                })
            # Systemzeit in Nanosekunden festhalten bevor Streaming startet – Referenz für Latenzberechnung
            self._stream_start_ns = time.time_ns()
            self._device.subscribe_to(tobii_research.EYETRACKER_TIME_SYNCHRONIZATION_DATA, self._sync_callback,
                                      as_dictionary=True)

            while not stop_event.is_set():
                time.sleep(0.1)

        except Exception as e:

            if self.status_queue:
                self.status_queue.put({
                    "key": "eyetracker",
                    "name": "Eyetracker",
                    "status": "error",
                    "duration": (time.time() - self.connection_started_at),
                    "error": str(e),
                    "ready": False,

                })
            print(f"Error in EyetrackerLogger: {e}")

    def start_logging(self) -> None:
        super().start_logging()



    def stop_logging(self) -> None:
        """Stop eyetracker subscription."""
        if self._device is not None:
            try:
                self._device.unsubscribe_from(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback)
            except Exception:
                pass
            self._device = None

        super().stop_logging() 