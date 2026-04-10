from logger import Logger
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
        queues = None
    ):
        super().__init__(file, self.CSV_FIELDS)
        self._device: Optional[object] = None
        self.device_index = device_index
        self.as_dictionary = as_dictionary
        self.queues = queues or {}

        self.eyetracker_queue = self.queues.get("eyetracker")

    def _gaze_callback(self, gaze_data):
        self.process_data(gaze_data)
        if self.eyetracker_queue is not None:
            put_latest(self.eyetracker_queue, gaze_data)

    def process_data(self, data: Union[bytes, str, dict]) -> None:
        """Expects dict from SDK; writes CSV-Row."""
        if isinstance(data, dict):
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

            self._device.subscribe_to(tobii_research.EYETRACKER_GAZE_DATA, self._gaze_callback, as_dictionary=self.as_dictionary)

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
        