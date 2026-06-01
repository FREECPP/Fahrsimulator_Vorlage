# /pose_analysis/live_pose_depth_overlay.py

import cv2
import numpy as np
import sys
import os
import time
from pathlib import Path
import mediapipe as mp
from typing import Optional
import threading

# 1. SDK-SETUP (Analog Devices ToF)
try:
    SDK_BIN_PFAD = r"C:\Analog Devices\TOF_Evaluation_ADTF3175D-Rel5.0.0\bin"

    if not Path(SDK_BIN_PFAD).exists():
        print(f"FATALER FEHLER: Der SDK-Pfad wurde nicht gefunden:")
        print(f"{SDK_BIN_PFAD}")
        sys.exit(1)

    os.environ["PATH"] = SDK_BIN_PFAD + os.pathsep + os.environ.get("PATH", "")
    sys.path.insert(0, SDK_BIN_PFAD)

    import aditofpython as tof

except ImportError:
    print(f"FEHLER: Konnte 'aditofpython' nicht laden.")
    sys.exit(1)

# 2. KONFIGURATION
TOF_CONFIG_FILE = "config_adsd3500_adsd3030.json"



# 3. KLASSE: ALIGNER (Rektifizierung)
class DepthRGBAligner:
    """
    Lädt die Kalibrierungsdaten und erstellt Maps.
    """

    def __init__(self):
        calibration_file = Path(__file__).parent / 'calibration_data.npz'
        if not calibration_file.exists():
            print(f"FEHLER: '{calibration_file}' nicht gefunden.")
            sys.exit(1)

        print(f"Lade Kalibrierungsdaten von {calibration_file.name}...")
        calib = np.load(str(calibration_file))

        self.P1 = calib['P1']  # RGB Projektionsmatrix
        self.P2 = calib['P2']  # Depth Projektionsmatrix

        # Maps erstellen
        self.map1_rgb, self.map2_rgb = cv2.initUndistortRectifyMap(
            calib['K_rgb'], calib['D_rgb'], calib['R1'], calib['P1'],
            tuple(calib['rgb_shape']), cv2.CV_16SC2
        )
        self.map1_depth, self.map2_depth = cv2.initUndistortRectifyMap(
            calib['K_depth'], calib['D_depth'], calib['R2'], calib['P2'],
            tuple(calib['rgb_shape']), cv2.CV_16SC2
        )

    def rectify_images(self, rgb_raw, depth_raw):
        rgb_rect = cv2.remap(rgb_raw, self.map1_rgb, self.map2_rgb, cv2.INTER_LINEAR)
        depth_rect = cv2.remap(depth_raw, self.map1_depth, self.map2_depth, cv2.INTER_NEAREST)
        return rgb_rect, depth_rect


# 4. HAUPTKLASSE: POSEN-TRACKING
class LivePose3D_DepthView:
    def __init__(self, tof_frame_processor, rgb_frame_processor, consumer_idx_tof=0, consumer_idx_rgb=0):
        self.aligner = DepthRGBAligner()

        # Geometrische Konstanten aus P2 extrahieren
        self.fx = self.aligner.P2[0, 0]
        self.baseline_term = self.aligner.P2[0, 3]  # Das ist (Tx * fx)
        print(f"Geometrie geladen: fx={self.fx:.1f}, Baseline-Term={self.baseline_term:.1f}")

        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils

        self.drawing_spec_points = self.mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=4, circle_radius=3)
        self.drawing_spec_lines = self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2)

        self.consumer_idx_tof = consumer_idx_tof
        self.consumer_idx_rgb = consumer_idx_rgb
        self.tof_frame_processor = tof_frame_processor
        self.rgb_frame_processor = rgb_frame_processor

        self.fps_counter = 0
        self.fps_start_time = time.time()

    def run(self):
        print("--- STARTE TIEFEN-OVERLAY (MIT PARALLAXEN-KORREKTUR) ---")
        try:
            while True:
                # 1. Daten holen
                depth_data = self.tof_frame_processor.get_frame(consumer_idx=self.consumer_idx_tof)
                rgb_data = self.rgb_frame_processor.get_frame(consumer_idx=self.consumer_idx_rgb)

                if depth_data is None or rgb_data is None:
                    time.sleep(0.001)
                    continue

                depth_raw = np.array(depth_data, copy=False, dtype=np.float32)

                # 2. Rektifizierung
                rgb_rect, depth_rect = self.aligner.rectify_images(rgb_data, depth_raw)

                # 3. Pose auf RGB erkennen
                rgb_input = cv2.cvtColor(rgb_rect, cv2.COLOR_BGR2RGB)
                results = self.pose.process(rgb_input)

                # Filterung für sauberere Werte
                depth_filtered = cv2.medianBlur(depth_rect.astype(np.uint16), 5)

                # Visualisierung vorbereiten
                depth_vis = np.clip(depth_rect, 0, 1500)
                depth_vis = cv2.normalize(depth_vis, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_color_map = cv2.applyColorMap(depth_vis, cv2.COLORMAP_TURBO)

                h, w = depth_color_map.shape[:2]

                # KORREKTUR-LOGIK: RGB Landmarks -> Depth Landmarks
                if results.pose_landmarks:

                    # iterieren über alle Landmarks und verschieben
                    for landmark in results.pose_landmarks.landmark:
                        # 1. RGB Koordinaten holen
                        u_rgb = int(landmark.x * w)
                        v_rgb = int(landmark.y * h)

                        # Bounds Check
                        if 0 <= u_rgb < w and 0 <= v_rgb < h:
                            # 2. Tiefe an der "alten" RGB-Position schätzen
                            z_val = depth_filtered[v_rgb, u_rgb]

                            if z_val > 100:  # Nur wenn gültige Tiefe (>10cm)
                                # 3. FORMEL ANWENDEN
                                disparity = self.baseline_term / z_val

                                u_depth_new = u_rgb - disparity

                                # 4. Landmark updaten (zurück normalisieren auf 0..1)
                                landmark.x = u_depth_new / w

                    #
                    # ZEICHNEN (Jetzt mit korrigierten Koordinaten)
                    self.mp_drawing.draw_landmarks(
                        image=depth_color_map,
                        landmark_list=results.pose_landmarks,  # Wurde oben "in-place" modifiziert
                        connections=self.mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=self.drawing_spec_points,
                        connection_drawing_spec=self.drawing_spec_lines
                    )

                    # Text Anzeige für wichtige Punkte
                    keypoints = [15, 16, 11, 12, 0]  # Hände, Schultern, Nase
                    for idx in keypoints:
                        lm = results.pose_landmarks.landmark[idx]
                        cx, cy = int(lm.x * w), int(lm.y * h)

                        if 0 <= cx < w and 0 <= cy < h:
                            dist_mm = depth_filtered[cy, cx]
                            if dist_mm > 0:
                                cv2.putText(depth_color_map, f"{dist_mm / 1000:.2f}m", (cx + 10, cy),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                # FPS
                self.fps_counter += 1
                if time.time() - self.fps_start_time >= 1.0:
                    fps = self.fps_counter / (time.time() - self.fps_start_time)
                    cv2.putText(depth_color_map, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (255, 255, 255), 2)
                    self.fps_counter = 0
                    self.fps_start_time = time.time()

                cv2.imshow('Depth View (Corrected)', depth_color_map)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        finally:
            cv2.destroyAllWindows()



if __name__ == "__main__":
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))


    from logger.tiefencamlogger import TiefenCamLogger
    from logger.rgb_camera_logger import RgbCameraLogger
    from logger.frame_processor import Processor
    import threading

    dir = Path("C:/Users/louis/fahrsimulator/logger/logfiles/test_datatransfer")
    os.makedirs(dir, exist_ok=True)

    tof_processor = Processor()
    rgb_processor = Processor()

    tof_logger = TiefenCamLogger(
        config="config_adsd3500_adsd3030.json",
        mode="lr-qnative",
        output_dir=dir,
        fps=12.0,
        ip = "ip:10.43.0.1",
        log_path=dir / "tof_camera_log.csv",
        raw_pixel_csv = False,
        csv_compressed = False,
        frame_processor=tof_processor,
    )

    tof_logger.start_sensor()

    rgb_logger = RgbCameraLogger(
        camera_index=0,
        file=Path("rgb_camera_log.csv"),
        processor=  rgb_processor,
        live_view=False,
    )
    rgb_logger.start_sensor()

    model = LivePose3D_DepthView(
        tof_frame_processor=tof_processor,
        rgb_frame_processor=rgb_processor
    )

    logging_thread = threading.Thread(target=tof_logger.start_logging, daemon=True)
    logging_thread.start()
    print("TOF STARTED ========================================")
    logging_thread2 = threading.Thread(target=rgb_logger.start_logging, daemon=True)
    logging_thread2.start()
    print("RGB STARTED ========================================")
    time.sleep(5)

    try:
        model.run()
    except KeyboardInterrupt:
        print("Beende Logging...")
        tof_logger.stop_logging()
        rgb_logger.stop_logging()
        logging_thread.join()
        logging_thread2.join()
        print("Fertig.")