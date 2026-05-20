import threading
import time
from pathlib import Path
from typing import Union, Optional
import cv2
import numpy as np
import mediapipe as mp
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from logger.logger import Logger, LOG_TIME_KEY
from queue import Empty

from utils.queue_utils import put_latest
from multiprocessing import Event


class RgbCameraLogger(Logger):
    CSV_FIELDS = [
        "frame_nr",
        "mean_red",
        "mean_green",
        "mean_blue",
        "std_red",
        "std_green",
        "std_blue",
        "mean_brightness",
        "eyes_closed"
    ]

    def __init__(
            self,
            camera_index: int,
            file: Union[Path, str],
            live_view: bool = False,
            directory=None,
            queues=None,
            back_camera: bool = False,
    ):
        super().__init__(file, self.CSV_FIELDS)
        self._running = threading.Event()

        self._camera_index = camera_index
        self._cam: Optional[cv2.VideoCapture] = None
        self.writer: Optional[cv2.VideoWriter] = None

        self.fps_time = None
        self.face_mesh: Optional[mp.solutions.FaceMesh] = None
        self.mp_face_mesh = None
        self.mp_drawing_styles = None
        self.mp_drawing = None
        self.back_camera = back_camera
        self._frame_count = 0
        self.directory = directory
        self.video_file_path = Path(
            directory / "video" / "rgb_camera_recordings" / f"logitech_camera.avi")  # AVI Format

        self.EAR_THRESHOLD = load_ear()
        self.LEFT_EYE = [33, 160, 158, 133, 153, 144]  # Eye-Landmarks
        self.RIGHT_EYE = [362, 385, 387, 263, 373, 380]  # Eye-Landmarks

        self.frame_width = 640
        self.frame_height = 480

        self.eyes_closed = False
        self.frame_rgb = None

        self.live_view = live_view
        self.queues = queues or {}

        # Latenz Global in der Klasse bekannt machen (Wird gesetzt durch get_latency falls nicht standart 8ms)
        self.mean_latency = 8000000
        # Korrigierter Aufnahmezeitpunkt im time.time()-Format, wird pro Frame aktualisiert
        self.capture_time = None

    def start_sensor(self,stop_event, log_event):
        super().start_sensor()
        self._running.set()
        self.video_file_path.parent.mkdir(parents=True, exist_ok=True)

        self._cam = cv2.VideoCapture(self._camera_index)
        print("Kamera: ", self._cam)
        if not self._cam.isOpened():
            print(f"Kann Kamera {self._camera_index} nicht öffnen.")
            raise SystemExit(1)

        fps = self._cam.get(cv2.CAP_PROP_FPS) or 20.0
        width = int(self._cam.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        height = int(self._cam.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
        self.frame_width = width
        self.frame_height = height
        fourcc = cv2.VideoWriter_fourcc(*"I420")
        self.writer = cv2.VideoWriter(str(self.video_file_path), fourcc, fps, (width, height))
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.get_latency(100)
        self._run_loop(stop_event, log_event)


    def get_latency(self, val_amount_mean_calc: int) -> None:
        test_list = []
        try:
            # Für X wiederholungen den zeitstempel Vor und Nach dem holen des Frames abspeichern anhand daran die Durchschnittliche Latenz berechnen
            for i in range(val_amount_mean_calc):
                ts_1 = time.time_ns()
                read_successful, frame = self._cam.read()
                ts_2 = time.time_ns()

                # Wenn der Frame OK dann Füge die Zeitdifferenz in die Liste hinzu
                if read_successful:
                    test_list.append(ts_2 - ts_1)

                # Warten damit der Frame-Aufruf nicht Blockiert und so das Latenz Ergebnis verfälscht
                time.sleep(0.5)

        except Exception as e:
            print("Frame processing error:", e)

        mean_val = np.mean(test_list)
        self.mean_latency = mean_val / 2
        print(f"RGB-Latency {self._camera_index}: {self.mean_latency / 1e6:.2f} ms")

    def start_logging(self, stop_event, log_event):
        super().start_logging()
        self._running.set()
        self.fps_time = time.time()



    def stop_logging(self):
        self._running.clear()
        self._cam.release()
        if self.writer.isOpened():
            self.writer.release()
        cv2.destroyAllWindows()

    def create_mediapipe_image(self, results, fps_time, frame_count, frame, camera_index):
        if camera_index == 0:
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    self.mp_drawing.draw_landmarks(
                        image=frame,
                        landmark_list=face_landmarks,
                        connections=self.mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
                    )

                    self.mp_drawing.draw_landmarks(
                        image=frame,
                        landmark_list=face_landmarks,
                        connections=self.mp_face_mesh.FACEMESH_CONTOURS,
                        landmark_drawing_spec=None,
                        connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
                    )
            status = "Eyes closed" if self.eyes_closed else "Eyes open"
            color = (0, 0, 255) if self.eyes_closed else (0, 255, 0)
            cv2.putText(frame, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

    def _run_loop(self, stop_event, log_event) -> None:
        try:
            # Flag um einmal start_logging funktion aufzurufen
            x = 0
            while self._running.is_set() and not stop_event.is_set():
                read_successful, frame = self._cam.read()
                # Aufnahmezeitpunkt berechnen: Empfangszeit minus gemessene Latenz
                self.capture_time = time.time() - self.mean_latency / 1e9

                if (not read_successful) or frame is None or frame.size == 0:
                    time.sleep(0.01)
                    continue
                if (self._camera_index == 0):
                    frame = cv2.rotate(frame, cv2.ROTATE_180)

                if not read_successful:
                    self.stop_logging()
                    break

                try:
                    if self._camera_index == 0:
                        rgb_queue = self.queues.get("rgb_frame")
                    elif self._camera_index == 1:
                        rgb_queue = self.queues.get("rgb_frame2")
                    else:
                        rgb_queue = None

                    if rgb_queue is not None:
                        ok, buffer = cv2.imencode(".jpg", frame)
                        if ok:
                            put_latest(rgb_queue, buffer.tobytes())
                except Empty:
                    pass

                if log_event.is_set():
                    # Start Logging muss einmal aufgerufen werden sonst werden keine Logs in das csv geschrieben
                    if x == 0:
                        self.start_logging(stop_event, log_event)
                        x = 1

                    file = f"rgb_camera_{self._camera_index}_frame_{self.capture_time}.npy"
                    if self._camera_index == 0:
                        path = self.directory / "rgb_frames" / "rgb_camera_1_frames"
                    elif self._camera_index == 1:
                        path = self.directory / "rgb_frames" / "rgb_camera_2_frames"
                    path.mkdir(parents=True, exist_ok=True)
                    np.save(path / file, frame)

                    if self.writer.isOpened():
                        self.writer.write(frame)

                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = self.face_mesh.process(frame_rgb)
                    self.create_mediapipe_image(results, self.fps_time, self._frame_count, frame,
                                                camera_index=self._camera_index)

                    # Live-Vorschau
                    if self.live_view:
                        cv2.imshow("Live", frame)
                        cv2.waitKey(1)

                    if results.multi_face_landmarks:
                        landmarks = results.multi_face_landmarks[0]
                        self.detect_eyes_closed(landmarks)

                    self.results = results
                    self.frame_rgb = frame_rgb
                    self.write_csv(frame_rgb)

                    self._frame_count += 1

        except Exception as e:
            import traceback
            print(f"RgbCameraLogger error: {e}")
            traceback.print_exc()

    def write_csv(self, frame_rgb):
        r = frame_rgb[:, :, 0]
        g = frame_rgb[:, :, 1]
        b = frame_rgb[:, :, 2]

        mean_r = np.mean(r)
        mean_g = np.mean(g)
        mean_b = np.mean(b)
        std_r = np.std(r)
        std_g = np.std(g)
        std_b = np.std(b)
        brightness = np.mean(frame_rgb)

        if not self.back_camera:
            self.write_row({
                LOG_TIME_KEY: self.capture_time,  # Korrigierter Aufnahmezeitpunkt statt time.time()
                "frame_nr": float(self._frame_count),
                "mean_red": float(mean_r),
                "mean_green": float(mean_g),
                "mean_blue": float(mean_b),
                "std_red": float(std_r),
                "std_green": float(std_g),
                "std_blue": float(std_b),
                "mean_brightness": float(brightness),
                "eyes_closed": self.eyes_closed
            })
        else:
            self.write_row({
                LOG_TIME_KEY: self.capture_time,  # Korrigierter Aufnahmezeitpunkt statt time.time()
                "frame_nr": float(self._frame_count),
                "mean_red": float(mean_r),
                "mean_green": float(mean_g),
                "mean_blue": float(mean_b),
                "std_red": float(std_r),
                "std_green": float(std_g),
                "std_blue": float(std_b),
                "mean_brightness": float(brightness),
                "eyes_closed": None
            })

    # ==========================================================================================================
    # EAR -> Eye Aspect Ratio
    # ==========================================================================================================
    @staticmethod
    def calculate_ear(landmarks, eye_indices, frame_width, frame_height) -> float:
        """
        Berechnet Eye Aspect Ratio für ein Auge.
        Um den Threshold richtig anzuwenden, benötigen wir eine Baseline für die Öffnung der Augen.
        Dieser EAR - Eye Aspect Ration, calculiert den durchschnitt der Augenöffnung anhand von 4 Punkten aus der Landmark.
        """
        # Landmarks in den Pixel-Koordinaten bestimmen.
        coords = []
        for idx in eye_indices:
            landmark = landmarks.landmark[idx]
            x = int(landmark.x * frame_width)
            y = int(landmark.y * frame_height)
            coords.append((x, y))

        # Vertikale Distanzen berechnen
        vertical1 = np.linalg.norm(np.array(coords[1]) - np.array(coords[5]))
        vertical2 = np.linalg.norm(np.array(coords[2]) - np.array(coords[4]))

        # Horizontale Distanz berechnen
        horizontal = np.linalg.norm(np.array(coords[0]) - np.array(coords[3]))

        # EAR Formel
        if horizontal <= 0:
            return 0.0
        ear = (vertical1 + vertical2) / (2.0 * horizontal)

        return ear

    def detect_eyes_closed(self, landmarks) -> None:
        """
        Erkennt ob Augen geschlossen (True) oder offen (False).
        :return: True oder False
        """
        left_ear = self.calculate_ear(landmarks, self.LEFT_EYE, self.frame_width, self.frame_height)
        right_ear = self.calculate_ear(landmarks, self.RIGHT_EYE, self.frame_width, self.frame_height)
        avg_ear = (left_ear + right_ear) / 2.0

        if avg_ear < float(self.EAR_THRESHOLD):
            self.eyes_closed = True
        else:
            self.eyes_closed = False


def load_ear() -> float:
    import configparser
    import os
    config = configparser.ConfigParser()
    config_path = Path(__file__).resolve().parents[1] / "config.ini"

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini nicht gefunden: {config_path}")
    config.read(config_path)
    try:
        ear = float(config.get('Mediapipe', 'EyeAspectRatio'))
        return ear
    except Exception as e:
        print(
            f"Daten aus 'config.ini' konnten nicht gelesen werden. Versichern Sie sich, dass PORT und HOST unter [General] existieren. {e}")

        return 0.21