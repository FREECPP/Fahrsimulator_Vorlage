from logger.logger import Logger, LOG_TIME_KEY
from pathlib import Path
from typing import Union, Optional
import tobii_research
import time
import queue as _queue

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
        "right_pupil_diameter"
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

        self.eyetracker_queue = self.queues.get("eyetracker")

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

        # Rohdaten zum errechnen wie viel monotic clock time ein Tick der Tobii Device Time
        self._values_for_device_tick_calc = []

        # Kalibrierung der Latenz abgeschlossen
        self.calibration_finished = False

        

    def _gaze_callback(self, gaze_data):
        device_ts = gaze_data.get("device_time_stamp")
        if device_ts is not None:
            self.capture_time = self.transform_to_unix(device_ts)
        self.process_data(gaze_data)
        if self.eyetracker_queue is not None:
            put_latest(self.eyetracker_queue, gaze_data)

    def _sync_callback(self, sync_data):

        # Sync Handler -> sync_data enthält die sys_time_request von tobbi, den device_time_stamp von tobii sowie die sys_response_time von tobii   
        # Sys_req_ts und sys_resp_ts werden ausgehend von der Monotic Clock gesetzt deshalb nicht gleich Unix-Time
        self.sys_req_ts = sync_data.get("system_request_time_stamp") # Gibt den Zeitstempel zurück, wenn ein Datum angefragt wird
        self.device_ts = sync_data.get("device_time_stamp") # Gibt den Zeitstempel zurück, wenn ein Datum erzeugt wird
        self.sys_resp_ts = sync_data.get("system_response_time_stamp") # Gibt den Zeitstempel zurück, wenn ein Datum ankommt
        
        # Abschätzen, zu welcher Monotic clock Zeit der device Timestamp ungefär kommt
        self.monotic_ts_raw = (self.sys_req_ts + self.sys_resp_ts) / 2

        # Liste mit Wertepaaren füllen 
        self._values_for_device_tick_calc.append((self.monotic_ts_raw, self.device_ts))


    def calibrate_time(self):
        if self.calibration_finished == False:
            mono_per_tick_list = []
            offset_calc_ts_and_ts = []
            for i in range(len(self._values_for_device_tick_calc)):
                monotic_ts_raw_delta = self._values_for_device_tick_calc[i][0] - self._values_for_device_tick_calc[0][0]
                device_ts_delta = self._values_for_device_tick_calc[i][1] - self._values_for_device_tick_calc[0][1]

                if monotic_ts_raw_delta > 0:
                    mono_per_tick = monotic_ts_raw_delta / device_ts_delta
                    mono_per_tick_list.append(mono_per_tick)
                    offset = self._values_for_device_tick_calc[i-1][0] - mono_per_tick * self._values_for_device_tick_calc[i-1][1] 
                    offset_calc_ts_and_ts.append(offset)

            self.mean_mono_per_tick = sum(mono_per_tick_list) / len(mono_per_tick_list)
            self.mean_offset = sum(offset_calc_ts_and_ts) / len(offset_calc_ts_and_ts)
            t_perf = time.perf_counter()
            t_unix = time.time()
            self.offset_monotic_unix = t_unix - t_perf
            self.calibration_finished = True
        else:
            pass

    def transform_to_unix(self, device_time):
        return self.mean_mono_per_tick * device_time + self.mean_offset + self.offset_monotic_unix

    def process_data(self, data: Union[bytes, str, dict]) -> None:
        """Expects dict from SDK; writes CSV-Row."""
        if isinstance(data, dict):
            if self.capture_time is not None:
                data[LOG_TIME_KEY] = self.capture_time
            self.write_row(data)
            return

        raise ValueError(f"Unexpected data type: {type(data)}")

    def start_sensor(self) -> None:
        super().start_sensor()

    def start_logging(self, stop_event) -> None:
        super().start_logging()

        try:
            found_eyetrackers = tobii_research.find_all_eyetrackers()
            self._device = found_eyetrackers[self.device_index]
            print(f"Using eyetracker: {self._device.device_name} @ {self._device.address}")

            # Systemzeit in Nanosekunden festhalten bevor Streaming startet – Referenz für Latenzberechnung
            self._stream_start_ns = time.time_ns()
            self._device.subscribe_to(tobii_research.EYETRACKER_TIME_SYNCHRONIZATION_DATA, self._sync_callback,
                                      as_dictionary=True)
            time.sleep(2)
            self._device.unsubscribe_from(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback)
            self.calibrate_time()
            self._device.subscribe_to(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback,
                                  as_dictionary=self.as_dictionary)


            while not stop_event.is_set():
                time.sleep(0.1)

        except Exception as e:
            print(f"Error in EyetrackerLogger: {e}")

    def stop_logging(self) -> None:
        """Stop eyetracker subscription."""
        if self._device is not None:
            try:
                self._device.unsubscribe_from(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback)
            except Exception:
                pass
            self._device = None

        super().stop_logging() 