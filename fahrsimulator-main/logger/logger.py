from abc import ABC, abstractmethod
from pathlib import Path
import threading
import csv
import time
from typing import Union, Optional, List, Dict  

LOG_TIME_KEY = "log_time"

class Logger(ABC):
    """Abstract Logger-Interface."""

    def __init__(self, file: Union[Path, str], csv_fields: Optional[List[str]]):
        self._lock = threading.Lock()
        self.file_path = Path(file)
        if csv_fields:
            self.csv_fields = [LOG_TIME_KEY] + csv_fields
        self._file_handle = None
        if self.file_path and self.csv_fields:
            self.init_logfile()

    @abstractmethod
    def start_logging(self) -> None:
        """Starts the logging process."""
        with self._lock:
            if self._file_handle is None:
                self._file_handle = open(self.file_path, "a", encoding="utf-8", buffering=1, newline="")
        ...

    @abstractmethod
    def stop_logging(self) -> None:
        """Stops the logging process."""
        with self._lock:
            if self._file_handle:
                self._file_handle.flush()
                self._file_handle.close()
                self._file_handle = None
        ...

    @abstractmethod
    def start_sensor(self) -> None:
        """Starts the sensor if needed and returns when the device is ready"""
        ...

    def init_logfile(self) -> None:
        """Creates the logfile."""
        with self._lock:
            if not self.file_path.exists():
                self.file_path.touch()
            
            with open(self.file_path, "a", encoding="utf-8", newline="") as f: 
                writer = csv.DictWriter(f, fieldnames=self.csv_fields)
                if self.file_path.stat().st_size == 0:
                    writer.writeheader()

    def write_row(self, row: Dict) -> None:
        """Thread-safe write a CSV row to the log file."""
        with self._lock:
            if self._file_handle:
                row[LOG_TIME_KEY] = time.time()
                writer = csv.DictWriter(self._file_handle, fieldnames=self.csv_fields)
                writer.writerow({k: row.get(k, "") for k in self.csv_fields})
             
         
