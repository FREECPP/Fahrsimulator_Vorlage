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
        """Callback-Funktion für Daten

        Sendet der Tobii-Sensor Daten, wird diese Funktion aufgerufen, 
        um diese Daten zunächst weiterzuverarbeiten. Hier findet auch 
        die Wandlung der Device-Time zur Unix-Time statt. 
    
        """

        # Device Time erhalten und zur Unix-Time wandeln
        device_ts = gaze_data.get("device_time_stamp")
        if device_ts is not None:
            self.capture_time = self.transform_to_unix(device_ts)
        
        # Gaze Data in Queue zur weiterverarbeitung legen
        self.process_data(gaze_data)
        if self.eyetracker_queue is not None:
            put_latest(self.eyetracker_queue, gaze_data)

    def _sync_callback(self, sync_data):
        """Callback-Funktion für Sync-Daten

        Hier werden die Daten verarbeitet, die während der
        Synchronisationsphase erhoben werden. Das besondere
        Augenmerk liegt dabei auf "system_request_time_stamp",
        "device_time_stamp" und "system_response_time_stamp".  
    
        """
        # "system_request_time_stamp" und "system_response_time_stamp" 
        # sind im Format des Perf_Counters des Rechners und entsprechen damit
        # nicht der Unix-Time
        self.sys_req_ts = sync_data.get(
            "system_request_time_stamp")  # Gibt den Zeitstempel zurück, wenn ein Datum angefragt wird
        self.device_ts = sync_data.get("device_time_stamp")  # Gibt den Zeitstempel zurück, wenn ein Datum erzeugt wird
        self.sys_resp_ts = sync_data.get(
            "system_response_time_stamp")  # Gibt den Zeitstempel zurück, wenn ein Datum ankommt

        # Abschätzen, zu welcher Rechnerzeit der device Timestamp ungefär kommt
        self.monotic_ts_raw = (self.sys_req_ts + self.sys_resp_ts) / 2

        # Liste mit Wertepaaren füllen (geschätzte Rechnerzeit vs. gemessener Device-Timestamp)
        self._values_for_device_tick_calc.append((self.monotic_ts_raw, self.device_ts))

    def calibrate_time(self):
        """Berechnet den Offset und den Umrechnungsfaktor, um Device-Ticks in Unix-Time zu wandeln.

        Die Kalibrierung basiert auf einer Liste von Paaren aus System-Monotonic-Zeit 
        und Device-Time-Ticks. Daraus wird die Steigung (Ticks zu Zeit) und der 
        Nullpunkt-Versatz ermittelt.  
    
        """
        if self.calibration_finished == False:
            mono_per_tick_list = []
            offset_calc_ts_and_ts = []

            # 1. Schritt: Berechnung der Tick-Rate (Steigung)
            # Wir vergleichen jeden Messpunkt mit dem Startpunkt, um die durchschnittliche
            # Dauer eines einzelnen Device-Ticks in monotoner Systemzeit zu bestimmen.    
            for i in range(1, len(self._values_for_device_tick_calc)):
                monotic_ts_raw_delta = self._values_for_device_tick_calc[i][0] - self._values_for_device_tick_calc[0][0]
                device_ts_delta = self._values_for_device_tick_calc[i][1] - self._values_for_device_tick_calc[0][1]

                if device_ts_delta > 0:
                    # Zeitdifferenz pro Tick berechnen
                    mono_per_tick = monotic_ts_raw_delta / device_ts_delta
                    mono_per_tick_list.append(mono_per_tick)

            if not mono_per_tick_list:  # Leere Liste checken!
                print("Error: Could not calculate tick rate")
                return
            
            # Durchschnittliche Dauer eines Ticks speichern
            self.mean_mono_per_tick = sum(mono_per_tick_list) / len(mono_per_tick_list)

            # 2. Schritt: Berechnung des Offsets (Y-Achsenabschnitt)
            # Basierend auf der berechneten Tick-Rate bestimmen wir für jeden Punkt den
            # theoretischen Nullpunkt der Device-Time relativ zur Monotonic-Time.
            for i in range(len(self._values_for_device_tick_calc)):
                # Formel: Systemzeit - (Tick-Rate * Device-Ticks)
                offset_calc_ts_and_ts.append(self._values_for_device_tick_calc[i][0] - self.mean_mono_per_tick *
                                             self._values_for_device_tick_calc[i][1])

            self.mean_offset = sum(offset_calc_ts_and_ts) / len(offset_calc_ts_and_ts)

            # 3. Schritt: Relation zur Unix-Zeit herstellen
            # Da monotonic_time keine absolute Zeit ist, berechnen wir hier die Differenz
            # zwischen der monotonen Systemzeit und der tatsächlichen Unix-Epoche (in Mikrosekunden).
            t_perf = time.perf_counter_ns() //1000
            t_unix = time.time_ns() //1000
            self.offset_monotic_unix = t_unix - t_perf
            print("####TIME-SYNC####: Kalibrierung Eyetracker abgeschlossen") 
            self.calibration_finished = True
        else:
            pass

    def transform_to_unix(self, device_time):
        """Wandelt einen gerätespezifischen Zeitstempel (Ticks) in die Unix-Epochenzeit um.
    
        Die Umrechnung erfolgt in zwei Schritten:
        1. Geräteticks -> Monotone Systemzeit (via linearer Regression/Mittelwert)
        2. Monotone Systemzeit -> Unix-Zeit (Sekunden seit 01.01.1970)
    
        """
        if not self.calibration_finished:
            return None
        else:

            # 1. Schritt: Umrechnung von Device-Ticks in die monotone Systemzeit.
            # Dies entspricht der Geradenformel: y = m * x + b
            # m = mean_mono_per_tick (Steigung), b = mean_offset (Y-Achsenabschnitt)
            t_monotonic = self.mean_mono_per_tick * device_time + self.mean_offset

            # 2. Schritt: Verschiebung der monotonen Zeit auf die Unix-Ebene.
             # t_unix ist hier noch in Mikrosekunden (basierend auf der Kalibrierung).
            
            t_unix = t_monotonic + self.offset_monotic_unix
            # 3. Schritt: Konvertierung von Mikrosekunden in Sekunden.
            # Da Unix-Timestamps in Python üblicherweise in Sekunden (float) angegeben werden.
            return t_unix / 1e6

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
            # Alle im Netzwerk oder lokal verfügbaren Eyetracker suchen
            found_eyetrackers = tobii_research.find_all_eyetrackers()

            # Den Eyetracker anhand des Indexes (meist 0) auswählen und Instanz speichern
            self._device = found_eyetrackers[self.device_index]
            print(f"Using eyetracker: {self._device.device_name} @ {self._device.address}")

            # Systemzeit in Nanosekunden festhalten bevor Streaming startet – Referenz für Latenzberechnung
            self._stream_start_ns = time.time_ns()

            # 1. Phase: Zeitsynchronisations-Daten abonnieren
            # Diese Daten werden benötigt, um die interne Uhr des Eyetrackers mit der Systemzeit zu korrelieren.
            self._device.subscribe_to(tobii_research.EYETRACKER_TIME_SYNCHRONIZATION_DATA, self._sync_callback,
                                      as_dictionary=True)
            
            # 5 Sekunden warten, um genügend Samples für eine stabile Kalibrierung zu sammeln
            time.sleep(5)

            # Synchronisations-Stream stoppen, da die Datenmenge nun für die Berechnung ausreicht
            self._device.unsubscribe_from(tobii_research.EYETRACKER_TIME_SYNCHRONIZATION_DATA, self._sync_callback)

            # Die zuvor gesammelten Daten nutzen, um Zeit zu kalibrieren
            self.calibrate_time()
            
            # 2. Phase: Eigentliches Gaze-Streaming (Blickdaten) starten
            # Die Daten werden nun über den _gaze_callback verarbeitet
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
