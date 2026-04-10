from pyshimmer import ShimmerBluetooth, DataPacket
from pyshimmer.dev.channels import EChannelType
from logger.logger import Logger
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

    def start_sensor(self) -> None:
        super().start_sensor()
        self._shimmer_device = connect_to_shimmer(self.shimmer_addr)
        self._shimmer_device.add_stream_callback(self.handler)

    def start_logging(self, stop_event) -> None:
        super().start_logging()
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
        
        if self.shimmer_queue is not None:
            put_latest(self.shimmer_queue, mapped_data)

        self.write_row(mapped_data)
        self.handle_hrv(mapped_data)

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

