import time

from logger.logger import Logger
from pathlib import Path
from typing import Optional, Union
import socket
import threading

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
        "acc_pedal", "brake_pedal", "clutch_pedal"
    ]

    def __init__(
        self,
        file: Union[Path, str],
        udp_ip: str = "127.0.0.1",
        udp_port: int = 6666,
        timeout: float = 2.0,
        queues = None,
    ):
        super().__init__(file, self.CSV_FIELDS)
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.timeout = timeout
        self.queues = queues or {}

        self.silab_queue = self.queues.get("silab")
        self.silab_model_queue = self.queues.get("silab_model")


    def start_sensor(self) -> None:
        super().start_sensor()

    def start_logging(self, stop_event) -> None:
        """Initialize the UDP socket for SiLab data, then start the background thread."""
        super().start_logging()

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self.udp_ip, self.udp_port))
        self._socket.settimeout(self.timeout)
        self._running.set()

        print(f"SiLab logger listening on {self.udp_ip}:{self.udp_port}")

        while not stop_event.is_set():
            try:
                data, addr = self._socket.recvfrom(1024)
                parsed = parse_silab_data(data)
                self.write_row(parsed)

                if self.silab_queue is not None:
                    put_latest(self.silab_queue, parsed)

                if self.silab_model_queue is not None:
                    put_latest(self.silab_model_queue, parsed)
                time.sleep(0.01)

                # if self.data_processor:
                #     self.data_processor.set_data(parsed)

            except socket.timeout:
                continue
            except ValueError as e:
                print(f"Parse error: {e}")
                continue
        

        self._thread = threading.Thread(target=self._run_loop, args=(stop_event,), daemon=True)
        self._thread.start()

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

    def _run_loop(self, stop_event) -> None:
        """Background thread loop that receives and logs SiLab UDP packets."""
        try:
            while self._running.is_set():
                try:
                    data, addr = self._socket.recvfrom(1024)
                    parsed = parse_silab_data(data)
                    self.write_row(parsed)
                
                    if self.silab_queue is not None:
                        put_latest(self.silab_queue, parsed)
                    
                    if  self.silab_model_queue is not None:
                        put_latest(self.silab_model_queue, parsed)
                    
                    
                    # if self.data_processor:
                    #     self.data_processor.set_data(parsed)
                        
                except socket.timeout:
                    continue
                except ValueError as e:
                    print(f"Parse error: {e}")
                    continue
        except Exception as e:
            print(f"SilabLogger error: {e}")