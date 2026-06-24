import time
from pathlib import Path
from queue import Empty
import numpy as np


class FileWriter:
    def __init__(
            self,
            outdir: str,
            filename: str,
            queues=None,

    ):
        self.queues = queues or {}
        self.outdir = Path(outdir)
        if not self.outdir.exists():
            self.outdir.mkdir(parents=True, exist_ok=True)
        self.filename = filename

        self.frame_queue = self.queues.get("tof")

    def write_npy(self, data: np.ndarray, filename: str):
        if data is None:
            return
        output_path = self.outdir / filename
        np.save(output_path, data.astype(np.float32))

    def run(self, stop_event):
        while not stop_event.is_set():
            if self.frame_queue is not None:
                try:
                    item = self.frame_queue.get_nowait()
                    frame, ts, global_frame = item
                    filename = f"frames_tof/tof_frame_{ts}.npy"
                    filename_global = f"frames_tof/global_frames_tof/global_tof_frame_{ts}.npy"
                    self.write_npy(frame, filename)
                    self.write_npy(global_frame, filename_global)

                    time.sleep(0.001)
                except Empty:
                    time.sleep(0.005)
                    continue
