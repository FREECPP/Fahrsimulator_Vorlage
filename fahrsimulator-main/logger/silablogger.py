import time
import math

from logger.logger import Logger, LOG_TIME_KEY
from pathlib import Path
from typing import Optional, Union
import socket
import threading
from multiprocessing import Event

from utils.queue_utils import put_latest
from utils.silab_parser import parse_silab_data
from queue import Full, Empty


class SilabLogger(Logger):
    """Logger for SiLab driving simulator data received via UDP."""

    CSV_FIELDS = [
        "sim_time",
        "speed",
        "rpm",
        "x", "y", "z",
        "pitch", "roll",
        "steering",
        "acc_pedal", "brake_pedal", "clutch_pedal",
        "gearauto"
    ]

    def __init__(
            self,
            file: Union[Path, str],
            udp_ip: str = "127.0.0.1",
            udp_port: int = 6666,
            timeout: float = 2.0,
            queues=None,
    ):
        super().__init__(file, self.CSV_FIELDS)
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.timeout = timeout
        self.queues = queues or {}
        self.connection_started_at = None
        self.total_distance_m = 0.0
        self.last_pos = None

        self.silab_queue = self.queues.get("silab")
        self.silab_model_queue = self.queues.get("silab_model")

        self.sensor_status_queue = self.queues.get(
            "sensor_status"
        )

        self.sensor_latency_queue = self.queues.get(
            "sensor_latency")

        self.sensor_key = "silab"
        self.sensor_name = "SiLab"
        self.drive_started = False
        self.drive_start_sim_time = None
    def update_distance(self, packet):
        current_pos = (
            packet["x"],
            packet["y"],
            packet["z"]
        )

        if self.last_pos is not None:
            dx = current_pos[0] - self.last_pos[0]
            dy = current_pos[1] - self.last_pos[1]
            dz = current_pos[2] - self.last_pos[2]

            segment = math.sqrt(
                dx * dx +
                dy * dy +
                dz * dz
            )

            self.total_distance_m += segment

        self.last_pos = current_pos

        return self.total_distance_m / 1000.0

    def start_sensor(self, stop_event, log_event) -> None:
        print("Silab start")
        print("sensor_status_queue loading", self.sensor_status_queue)

        self.connection_started_at = time.time()

        if self.sensor_status_queue:
            self.sensor_status_queue.put({
                "key": self.sensor_key,
                "name": self.sensor_name,
                "status": "loading",
                "duration": 0,
                "error": "",
                "ready": False,
                "started_at": self.connection_started_at

            })

        try:
            super().start_sensor()

            self._socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            self._socket.bind(
                (self.udp_ip, self.udp_port)
            )

            self._socket.settimeout(
                self.timeout
            )

            self._running.set()
            print("sensor_status_queue success", self.sensor_status_queue)

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "success",
                    "duration": (time.time() - self.connection_started_at),

                    "error": "",
                    "ready": True,
                })

            if self.sensor_latency_queue:
                self.sensor_latency_queue.put({
                    "key": self.sensor_key,
                    "latency_ms": None
                })

            print(
                f"SiLab logger listening on "
                f"{self.udp_ip}:{self.udp_port}"
            )

            self._run_loop(
                stop_event,
                log_event
            )

        except Exception as e:
            print("sensor_status_queue error", self.sensor_status_queue)

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "error",
                    "duration": (time.time() - self.connection_started_at),
                    "error": str(e),
                    "ready": False,
                })

            raise

    def start_logging(self, stop_event, log_event) -> None:
        """Initialize the UDP socket for SiLab data, then start the background thread."""
        super().start_logging()

    def stop_logging(self) -> None:
        """Stop background thread, close UDP socket and file."""
        self._running.clear()

        if self._thread is not None:
            self._thread.join(timeout=self.timeout)
            self._thread = None

        if self._socket is not None:
            self._socket.close()
            self._socket = None

        super().stop_logging()

    def _run_loop(self, stop_event, log_event) -> None:
        """Background thread loop that receives and logs SiLab UDP packets."""
        try:
            # start_logging flag damit diese Funktion einmalig aufgerufen wird
            x = 0
            while self._running.is_set() and not stop_event.is_set():
                try:
                    data, addr = self._socket.recvfrom(1024)
                    parsed = parse_silab_data(data)

                    parsed["distance_km"] = self.update_distance(parsed)
                    parsed[LOG_TIME_KEY] = parsed["sim_time"]

                    # Fahrzeugbewegung erkennen
                    if parsed["speed"] > 2.0:
                        self.moving_counter += 1
                    else:
                        self.moving_counter = 0

                    # Erst nach mehreren gültigen Paketen starten
                    if (
                            not self.drive_started
                            and self.moving_counter >= 10
                    ):
                        self.drive_started = True
                        self.drive_start_sim_time = parsed["sim_time"]

                    # Fahrzeit berechnen
                    if self.drive_started:
                        drive_seconds = (
                                parsed["sim_time"]
                                - self.drive_start_sim_time
                        )
                    else:
                        drive_seconds = 0

                    minutes = int(drive_seconds // 60)
                    seconds = int(drive_seconds % 60)

                    parsed["drive_time"] = (
                        f"{minutes:02d}:{seconds:02d}"
                    )

                    if log_event.is_set():
                        if x == 0:
                            self.start_logging(stop_event, log_event)
                            x = 1
                        self.write_row(parsed)

                    if self.silab_queue is not None:
                        put_latest(self.silab_queue, parsed)

                    if self.silab_model_queue is not None:
                        put_latest(self.silab_model_queue, parsed)

                    # if self.data_processor:
                    #     self.data_processor.set_data(parsed)

                except socket.timeout:
                    continue
                except ValueError as e:
                    print(f"Parse error: {e}")
                    continue
        except Exception as e:
            print("sensor_status_queue error", self.sensor_status_queue)

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "error",
                    "duration": (time.time() - self.connection_started_at),
                    "error": str(e),
                    "ready": False,
                })
            print(f"SilabLogger error: {e}")