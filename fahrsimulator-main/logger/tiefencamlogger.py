from tkinter import Event

from logger.logger import Logger, LOG_TIME_KEY

from multiprocessing import (
    Process,
    Event,
    Queue
)

import numpy as np
import imageio
from matplotlib import cm
from typing import Optional
from pathlib import Path
import os
import time
import sys

from utils.queue_utils import put_latest

# Kamera-SDK-Pfad hinzufügen, damit Python das Modul aditofpython findet
CAM_BIN_STR = str(Path(__file__).resolve().parent.parent / "timeOfFlightCam" / "bin")
os.environ["PATH"] = CAM_BIN_STR + os.pathsep + os.environ.get("PATH", "")
sys.path.insert(0, CAM_BIN_STR)
import aditofpython as tof

"""
Command for Executing first_Frame.py to get first depth frame from TiefenCam:
Add C:\Analog Devices\TOF_Evaluation_ADTF3175D-Rel5.0.0\bin; to python path to make it work
python ./first_frame.py lr-qnative 10.43.0.1 ./config_adsd3500_adsd3030.json
"""
import queue as _queue


class TiefenCamLogger(Logger):
    CSV_FIELDS = [
        "timestamp",
        "frame_path"
    ]

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    CAM_DIR = PROJECT_ROOT / "timeOfFlightCam" / "bin"
    CAM_DIR = str(CAM_DIR) + "/"

    modemapping = {
        "lr-native": {"width": 1024, "height": 1024},
        "lr-qnative": {"width": 512, "height": 512},
        "lr-mixed": {"width": 512, "height": 512},
        "sr-native": {"width": 1024, "height": 1024},
        "sr-qnative": {"width": 512, "height": 512},
        "sr-mixed": {"width": 512, "height": 512},
    }

    def __init__(
            self,
            config: str = "config_adsd3500_adsd3100.json",
            ip: str = "ip:10.43.0.1",
            mode: str = "lr-qnative",
            output_dir: Optional[Path] = None,
            fps: float = 10.0,
            log_path: Optional[Path] = None,
            raw_pixel_csv: bool = True,
            csv_compressed: bool = True,
            queues=None
    ):
        """
        Initializes the TiefenCamLogger class.

        Args:
            config (str): Path to the camera configuration file.
            ip (str): IP address of the camera.
            mode (str): Camera mode (e.g., "lr-qnative").
            output_dir (Optional[Path]): Directory to save output files.
            fps (float): Frames per second for video recording.
            log_path (Optional[Path]): Path to the log file.
            raw_pixel_csv (bool): Whether to save raw pixel data as CSV.
            csv_compressed (bool): Whether to compress CSV files.
        """
        super().__init__(log_path, self.CSV_FIELDS)
        self.config_path = self.CAM_DIR + "config/" + config
        self.ip = ip
        self.fps = fps
        self.mode = mode
        self.queues = queues or {}  # Für Kommunikation mit anderen Prozessen/Threads

        self.sensor_status_queue = self.queues.get(
            "sensor_status"
        )

        self.sensor_latency_queue = self.queues.get(
            "sensor_latency"
        )

        print("TOF sensor_latency queue =  ", self.sensor_latency_queue)
        self.sensor_key = "tof"
        self.sensor_name = "TOF"


        self.connection_started_at = None

        self.system = tof.System()
        self.cam_bin = Path(CAM_BIN_STR)
        self.camera = None
        self._running = False
        self.video_output_dir = Path(output_dir)

        self.jet_colormap = cm.get_cmap("jet")
        self._video_writer = None
        self._video_file: Optional[Path] = None
        self._screen = None

        self.raw_pixel_csv = bool(raw_pixel_csv)
        self.csv_compressed = bool(csv_compressed)

        self.frames_dir = Path(self.video_output_dir) / "frames_tof"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.data = []

        # Latenz Global in der Klasse bekannt machen (Wird gesetzt durch get_latency falls nicht standart 8ms)
        self.mean_latency = 8000000

    def connect_camera(self) -> None:
        """
        Connects to the ToF camera and initializes it with the specified configuration.

        Raises:
            Exception: If the camera initialization fails.
        """
        cameras = []
        types = []

        # Kamera im Netzwerk suchen
        status = self.system.getCameraList(cameras, self.ip)
        print(cameras, self.ip)
        if status:
            print("TOF Camera found on network:", self.ip)

        # erste gefundene Kamera auswählen
        self.camera = cameras[0]

        cam_bin = Path(CAM_BIN_STR)
        try:
            os.chdir(cam_bin)
            self.camera.initialize(self.config_path)  # Kamera initialisieren mit durch die Konfig-Datei
        except Exception as e:
            print("camera.initialize() failed:", e)

        self.camera.getAvailableFrameTypes(types)
        self.camera.setFrameType(self.mode)  # Modus setzen

        cam_details = tof.CameraDetails()
        status = self.camera.getDetails(cam_details)
        print("TOF Camera Details: .getDetails()", status)
        print("camera1 details:", "id:", cam_details.cameraId, "connection:", cam_details.connection)
        status = self.camera.start()  # Ab hier werden Frames geliefert
        if status:
            print("TOF Camera started")

    def start_sensor(
            self, stop_event, log_event) -> None:  # Prüft ob Kamera gestartet ist, ansonsten wird die Funktion connect_camera() aufgerufen
        """
        Ensures the camera is connected and started. Implements the abstract Logger.start_sensor method.

        Raises:
            Exception: If the camera connection or initialization fails.
        """
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

        if getattr(self, "camera", None) is not None:
            return
        try:
            self.connect_camera()

        except Exception as e:

            if self.sensor_status_queue:
                self.sensor_status_queue.put({
                    "key": self.sensor_key,
                    "name": self.sensor_name,
                    "status": "error",
                    "duration": (time.time() - self.connection_started_at),
                    "error": str(e),
                    "ready": False,
                })
            print("TiefenCamLogger.start_sensor failed:", e)
            raise
        self.start_logging(stop_event,log_event)

    def get_latency(self, val_amount_mean_calc: int) -> None:
        test_list = []
        try:
            frame = tof.Frame()

            # Für X wiederholungen den zeitstempel Vor und Nach dem holen des Frames abspeichern anhand daran die Durchschnittliche Latenz berechnen
            for i in range(val_amount_mean_calc):
                ts_1 = time.time_ns()
                status = self.camera.requestFrame(frame)
                ts_2 = time.time_ns()

                # Wenn der Frame OK dann Füge die Zeitdifferenz in die Liste hinzu
                if status:
                    test_list.append(ts_2 - ts_1)

                # Warten damit der Frame-Aufruf nicht Blockiert und so das Latenz Ergebnis verfälscht
                time.sleep(0.5)

        except Exception as e:
            print("Frame processing error:", e)

        mean_val = np.mean(test_list)
        self.mean_latency = mean_val / 2
        print(f"ToF-Latency: {self.mean_latency / 1e6:.2f} ms")

    def start_logging(self, stop_event, log_event):
        """
        Starts the logging process, including video recording and frame processing.

        This method continuously requests frames from the camera, processes them,
        and sends them to the frame processor.

        IMPORTANT: this function will also be called from start_sensor(). Therefore
        the "starting_sensors_flag" exists, to make clear who is the caller.
        If it will be called form start_sensor(), the logging-functionality will be
        deactivated.

        Raises:
            Exception: If there is an error during frame processing.
        """
        super().start_logging()

        self.get_latency(100)
        if self.sensor_status_queue:
            self.sensor_status_queue.put({
                "key": self.sensor_key,
                "name": self.sensor_name,
                "status": "success",
                "duration": (
                        time.time() - self.connection_started_at
                ),
                "error": "",
                "ready": True,
            })

            if self.sensor_latency_queue:
                print("RGB latency put start")
                self.sensor_latency_queue.put({
                    "key": "tof_scelet",
                    "latency_ms": round(
                        self.mean_latency / 1e6,
                        2
                    )
                })

                print("RGB latency put end")
        self._video_file = Path(self.video_output_dir / "tof_recording.mp4")
        self._video_writer = imageio.get_writer(str(self._video_file), fps=self.fps, codec="libx264", quality=8)
        self._running = True

        try:
            while self._running and not stop_event.is_set():
                try:
                    frame = tof.Frame()
                    status = self.camera.requestFrame(frame)  # Ein Frame wird geholt
                    # Korrigierter Aufnahmezeitpunkt in Sekunden: Empfangszeit minus gemessene Latenz
                    ts = time.time() - self.mean_latency / 1e9

                    if status:
                        # Daten aus dem Frame werden extrahiert
                        image = np.array(frame.getData("depth"), copy=False)
                        image_ab = np.array(frame.getData("ab"), copy=False)

                        q_tof = self.queues.get("tof") # Vermutlich nicht gebraucht
                        q_pose = self.queues.get("pose_queue") # Geht an merged_skelett... und wird damit wahrscheinlich mit dem Model verarbeitet

                        # Daten werden in dict abgelegt
                        data_packet = {
                            "ts": ts,
                            "depth": image,
                            "ab": image_ab
                        }

                        if q_tof is not None:
                            put_latest(q_tof, (image, ts))
                        if q_pose is not None:
                            put_latest(q_pose, data_packet)

                        if log_event.is_set():
                            frame_path = f"frames_tof/tof_frame_{ts}.npy"
                            self.write_row({
                                LOG_TIME_KEY: ts,
                                "timestamp": ts,
                                "frame_path": frame_path
                            })

                        time.sleep(0.05)  # Dadurch gehen bewusst Frames verloren?

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

                    print("Frame processing error:", e)
                    time.sleep(0.005)
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
        finally:
            pass

    def stop_logging(self):
        """
        Stops the logging process and releases all resources.

        This method stops the camera, closes the video writer, and computes the
        total size of the recorded frames' directory.
        """
        self._running = False
        try:
            if getattr(self, "camera", None):
                try:
                    self.camera.stop()
                except Exception:
                    pass

            if self._video_writer:
                try:
                    self._video_writer.close()
                except Exception:
                    pass

            try:

                frames_dir = None
                if getattr(self, "frames_dir", None) is not None:
                    frames_dir = Path(self.frames_dir)
                elif getattr(self, "video_output_dir", None) is not None:
                    frames_dir = Path(self.video_output_dir) / "frames_tof"

                if frames_dir is not None and frames_dir.exists():
                    total_bytes = 0
                    npz_bytes = 0
                    csv_bytes = 0
                    file_count = 0
                    for p in frames_dir.rglob("*"):
                        if p.is_file():
                            try:
                                b = p.stat().st_size
                            except Exception:
                                b = 0
                            total_bytes += b
                            file_count += 1
                            if p.suffix.lower() == ".npz":
                                npz_bytes += b
                            if p.name.lower().endswith((".csv", ".csv.gz")):
                                csv_bytes += b

                    total_gb = total_bytes / (1024 ** 3)
                    npz_gb = npz_bytes / (1024 ** 3)
                    csv_gb = csv_bytes / (1024 ** 3)
                    print(f"Frames directory: {frames_dir}")
                    print(
                        f"  files: {file_count}, total: {total_gb:.3f} GB (npz: {npz_gb:.3f} GB, csv: {csv_gb:.3f} GB)")
                else:
                    print("No frames directory found to compute sizes.")
            except Exception as e:
                print("Error computing frames sizes:", e)
        except Exception:
            pass
        finally:
            self._running = False
            self.camera = None
            self._video_writer = None
            self._video_file = None
            self._screen = None


# Komponententests only
if __name__ == "__main__":
    run_log_dir = Path("C:/Users/louis/fahrsimulator/logger/logfiles/tof_test2")
    logger1 = TiefenCamLogger(
        config="config_adsd3500_adsd3030.json",
        mode="lr-qnative",
        output_dir=run_log_dir,
        fps=10.0,
        ip="ip:10.43.0.1",
        log_path=run_log_dir / "tof_camera_log.csv",
        raw_pixel_csv=True,
        csv_compressed=False,
    )
    logger1.start_sensor()
    try:
        logger1.start_logging()
    except KeyboardInterrupt:
        logger1.stop_logging()