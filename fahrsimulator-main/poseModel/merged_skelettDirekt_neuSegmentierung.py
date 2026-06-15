import cv2
import numpy as np
import sys
import os
import time
from pathlib import Path
import mediapipe as mp
import threading
import csv
import queue as _queue
import open3d as o3d

# ==========================================
# KONFIGURATION
# ==========================================
VIEW_MODE = "2D"  # "2D" (sendet Bild an Queue) oder "3D" (öffnet lokales Open3D Fenster)

# Alle 33 MediaPipe-Pose-Landmarks (Index -> Spaltenname).
LANDMARK_COLUMNS = {
    0: "nose",
    1: "left_eye_inner", 2: "left_eye", 3: "left_eye_outer",
    4: "right_eye_inner", 5: "right_eye", 6: "right_eye_outer",
    7: "left_ear", 8: "right_ear",
    9: "mouth_left", 10: "mouth_right",
    11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    17: "left_pinky", 18: "right_pinky",
    19: "left_index", 20: "right_index",
    21: "left_thumb", 22: "right_thumb",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
    29: "left_heel", 30: "right_heel",
    31: "left_foot_index", 32: "right_foot_index",
}
# Spaltenreihenfolge der Skelett-CSV.
SKELETON_CSV_FIELDS = ["log_time"] + list(LANDMARK_COLUMNS.values())


def put_latest(q, item):
    """Hilfsfunktion für Non-Blocking Queue (Leaky Bucket)"""
    while True:
        try:
            q.put_nowait(item)
            return
        except _queue.Full:
            try:
                q.get_nowait()
            except _queue.Empty:
                pass
            time.sleep(0.001)


class DepthPoseClass:
    def __init__(self, queues=None, output_dir=None):
        self.queues = queues or {}

        # Skelett-Log: CSV mit allen Landmarks, ein Eintrag pro erkanntem Frame.
        self._skeleton_lock = threading.Lock()
        self._skeleton_file = None
        self._skeleton_writer = None
        if output_dir is not None:
            skeleton_path = Path(output_dir) / "tiefenskelett_log.csv"
            self._skeleton_file = open(
                skeleton_path, "a", encoding="utf-8", buffering=1, newline=""
            )
            self._skeleton_writer = csv.DictWriter(
                self._skeleton_file, fieldnames=SKELETON_CSV_FIELDS
            )
            if self._skeleton_file.tell() == 0:
                self._skeleton_writer.writeheader()

        # MediaPipe Setup
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # FPS & Data Container
        self.prev_time = 0
        self.idx_99_value = 0
        self.point_dict = []

        # 1. FARBSCHEMA

        self.body_part_colors = {
            'head': [1.0, 0.3, 0.3],  # Rot
            'torso': [0.3, 1.0, 0.3],  # Grün
            'arm': [1.0, 0.8, 0.2],  # Gelb
            'hand': [0.0, 0.8, 0.7],  # Türkis
            'left_leg': [1.0, 0.3, 1.0],  # Magenta
            'right_leg': [1.0, 0.3, 1.0],  # Magenta
        }

        # Verbindungen zuordnen
        self.connection_colors = {
            # KOPF
            (0, 1): 'head', (1, 2): 'head', (2, 3): 'head', (3, 7): 'head',
            (0, 4): 'head', (4, 5): 'head', (5, 6): 'head', (6, 8): 'head', (9, 10): 'head',
            # TORSO
            (11, 12): 'torso', (11, 23): 'torso', (12, 24): 'torso', (23, 24): 'torso',
            # ARME
            (11, 13): 'arm', (13, 15): 'arm', (15, 17): 'hand', (15, 19): 'hand', (15, 21): 'hand', (17, 19): 'hand',
            (12, 14): 'arm', (14, 16): 'arm', (16, 18): 'hand', (16, 20): 'hand', (16, 22): 'hand', (18, 20): 'hand',
            # BEINE
            (23, 25): 'left_leg', (25, 27): 'left_leg', (27, 29): 'left_leg', (27, 31): 'left_leg',
            (29, 31): 'left_leg',
            (24, 26): 'right_leg', (26, 28): 'right_leg', (28, 30): 'right_leg', (28, 32): 'right_leg',
            (30, 32): 'right_leg',
        }

        # 2. KALIBRIERUNG

        calib_path = Path(__file__).parent / 'calibration_data.npz'
        # Standardwerte
        self.fx, self.fy = 450.0, 450.0
        self.cx, self.cy = 256.0, 256.0

        if calib_path.exists():
            try:
                calib = np.load(str(calib_path))
                self.K_depth = calib['K_depth']
                self.fx = float(self.K_depth[0, 0])
                self.fy = float(self.K_depth[1, 1])
                self.cx = float(self.K_depth[0, 2])
                self.cy = float(self.K_depth[1, 2])
                """print(f"Kalibrierung geladen: fx={self.fx:.1f}, fy={self.fy:.1f}")"""
            except Exception as e:
                pass
                #print(f"Fehler beim Laden der Kalibrierung: {e}")
        else:
            pass
            #print("Keine calibration_data.npz gefunden, nutze Standardwerte.")

        # 3. 3D VIS VARIABLES
        self.vis = None
        self.pcd = None
        self.skeleton_mesh = None
        self.first_frame = True
        self.initialized_3d = False

    def _write_skeleton_row(self, mapped_points, ts):
        """Schreibt einen Skelett-Frame als CSV-Zeile (alle Landmarks als "(x, y, d)")."""
        if self._skeleton_writer is None:
            return
        row = {"log_time": ts}
        for idx, name in LANDMARK_COLUMNS.items():
            val = mapped_points.get(idx)
            # val ist (x, y, depth) oder None (Keypoint nicht im Bild).
            # Als Tupel mit nativen Typen schreiben -> CSV-Zelle "(x, y, d)".
            # Format exakt wie von process_dict.py erwartet (entfernt "()", split ",",
            # cast x/y=Int, d=Float); native Typen vermeiden numpy-Repr wie np.float32(..).
            if val is not None:
                row[name] = (int(val[0]), int(val[1]), float(val[2]))
            else:
                row[name] = ""
        with self._skeleton_lock:
            self._skeleton_writer.writerow(row)

    def close_skeleton_log(self):
        """Schließt die Skelett-Logdatei sauber."""
        with self._skeleton_lock:
            if self._skeleton_file is not None:
                self._skeleton_file.flush()
                self._skeleton_file.close()
                self._skeleton_file = None
                self._skeleton_writer = None

    # HILFSFUNKTIONEN FÜR 3D RENDERN ZU 2D
    def capture_3d_as_image(self):
        if not self.vis:
            return None

        image = self.vis.capture_screen_float_buffer(do_render=True)
        image_np = np.asarray(image)

        image_uint8 = (image_np * 255).astype(np.uint8)
        image_bgr = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2BGR)
        return image_bgr
    
    # HILFSFUNKTIONEN FÜR 3D & FARBEN
    def create_cylinder_mesh(self, p0, p1, radius=0.02, color=[0, 1, 0]):
        """Erstellt einen Zylinder zwischen zwei 3D-Punkten (Röhren)"""
        p0 = np.array(p0)
        p1 = np.array(p1)
        v = p1 - p0
        length = np.linalg.norm(v)

        if length < 0.001:
            return None

        cylinder = o3d.geometry.TriangleMesh.create_cylinder(radius=radius, height=length)
        cylinder.paint_uniform_color(color)
        cylinder.compute_vertex_normals()

        z_axis = np.array([0, 0, 1])
        v_norm = v / length
        axis = np.cross(z_axis, v_norm)

        if np.linalg.norm(axis) < 0.001:
            if np.dot(z_axis, v_norm) < 0:
                R = -np.eye(3)
                R[2, 2] = 1
            else:
                R = np.eye(3)
        else:
            angle = np.arccos(np.dot(z_axis, v_norm))
            R = cylinder.get_rotation_matrix_from_axis_angle(axis / np.linalg.norm(axis) * angle)

        cylinder.rotate(R, center=[0, 0, 0])
        cylinder.translate((p0 + p1) / 2)
        return cylinder

    def get_point_cloud_data(self, depth_img):
        """Berechnet 3D Punktwolke aus Tiefenbild"""
        h, w = depth_img.shape
        depth_m = depth_img.astype(np.float32) / 1000.0
        u, v = np.meshgrid(np.arange(w), np.arange(h))

        # Filter: 10cm bis 4m
        valid = (depth_m > 0.1) & (depth_m < 2.5)

        z = depth_m[valid]
        u_val = u[valid]
        v_val = v[valid]

        x = (u_val - self.cx) * z / self.fx
        y = (v_val - self.cy) * z / self.fy
        points = np.stack((x, y, z), axis=-1)

        # Farben basierend auf Tiefe (Turbo colormap)
        if len(z) > 0:
            z_norm = np.clip((z - 0.1) / (2.5 - 0.1), 0, 1)
            z_uint8 = (z_norm * 255).astype(np.uint8)
            colormap = cv2.applyColorMap(z_uint8, cv2.COLORMAP_TURBO)
            colors = colormap.reshape(-1, 3)[:, ::-1] / 255.0  # BGR zu RGB
        else:
            colors = np.zeros((0, 3))

        return points, colors

    def init_3d_vis(self):
        """Initialisiert das Open3D Fenster"""
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window("3D Skeleton View", width=800, height=600)
        opt = self.vis.get_render_option()
        opt.background_color = np.asarray([0.05, 0.05, 0.05])
        opt.point_size = 2.0

        self.pcd = o3d.geometry.PointCloud()
        self.skeleton_mesh = o3d.geometry.TriangleMesh()
        self.vis.add_geometry(self.pcd)
        self.vis.add_geometry(self.skeleton_mesh)
        self.vis.add_geometry(o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.3))

    def update_3d_logic(self, img_depth_rot, pose_landmarks):
        """Logik für das 3D Update"""
        if not self.initialized_3d:
            self.init_3d_vis()
            self.initialized_3d = True

        # 1. Punktwolke
        points, colors = self.get_point_cloud_data(img_depth_rot)
        if len(points) > 0:
            self.pcd.points = o3d.utility.Vector3dVector(points)
            self.pcd.colors = o3d.utility.Vector3dVector(colors)

            if self.first_frame:
                self.vis.reset_view_point(True)
                self.first_frame = False

        # 2. Skelett Röhren
        if pose_landmarks:
            h, w = img_depth_rot.shape
            skeleton_points_3d = {}
            full_skeleton = o3d.geometry.TriangleMesh()
            has_skeleton = False

            # Positionen berechnen
            for i, lm in enumerate(pose_landmarks.landmark):
                u_lm = int(lm.x * w)
                v_lm = int(lm.y * h)
                if 0 <= u_lm < w and 0 <= v_lm < h:
                    d = img_depth_rot[v_lm, u_lm]
                    if d > 100:
                        z_lm = d / 1000.0
                        # Kleiner Offset damit Skelett vor Punktwolke ist
                        z_vis = max(0.1, z_lm - 0.03)
                        x_lm = (u_lm - self.cx) * z_vis / self.fx
                        y_lm = (v_lm - self.cy) * z_vis / self.fy
                        skeleton_points_3d[i] = [x_lm, y_lm, z_vis]

            # Röhren bauen
            for start_idx, end_idx in self.mp_pose.POSE_CONNECTIONS:
                if start_idx in skeleton_points_3d and end_idx in skeleton_points_3d:
                    p0 = skeleton_points_3d[start_idx]
                    p1 = skeleton_points_3d[end_idx]

                    conn_key = (start_idx, end_idx)
                    body_part = self.connection_colors.get(conn_key, 'torso')
                    color = self.body_part_colors[body_part]

                    tube = self.create_cylinder_mesh(p0, p1, radius=0.008, color=color)
                    if tube:
                        full_skeleton += tube
                        has_skeleton = True

            self.skeleton_mesh.clear()
            if has_skeleton:
                self.skeleton_mesh.vertices = full_skeleton.vertices
                self.skeleton_mesh.triangles = full_skeleton.triangles
                self.skeleton_mesh.vertex_colors = full_skeleton.vertex_colors
                self.skeleton_mesh.compute_vertex_normals()

            self.vis.update_geometry(self.skeleton_mesh)

        self.vis.update_geometry(self.pcd)
        self.vis.poll_events()
        self.vis.update_renderer()

    def draw_colored_2d(self, image, pose_landmarks):
        """Zeichnet benutzerdefinierte farbige Linien im 2D Bild"""
        h, w = image.shape[:2]
        # Landmarks (Punkte)
        for lm in pose_landmarks.landmark:
            x, y = int(lm.x * w), int(lm.y * h)
            if 0 <= x < w and 0 <= y < h:
                cv2.circle(image, (x, y), 3, (255, 255, 255), -1)

        # Verbindungen (Linien)
        for start_idx, end_idx in self.mp_pose.POSE_CONNECTIONS:
            if start_idx >= len(pose_landmarks.landmark) or end_idx >= len(pose_landmarks.landmark):
                continue

            lm1 = pose_landmarks.landmark[start_idx]
            lm2 = pose_landmarks.landmark[end_idx]
            x1, y1 = int(lm1.x * w), int(lm1.y * h)
            x2, y2 = int(lm2.x * w), int(lm2.y * h)

            conn_key = (start_idx, end_idx)
            body_part = self.connection_colors.get(conn_key, 'torso')
            c_rgb = self.body_part_colors[body_part]
            c_bgr = (int(c_rgb[2] * 255), int(c_rgb[1] * 255), int(c_rgb[0] * 255))

            if 0 <= x1 < w and 0 <= y1 < h and 0 <= x2 < w and 0 <= y2 < h:
                cv2.line(image, (x1, y1), (x2, y2), c_bgr, 3)


    def run(self, stop_event, log_event=None):
        #print(f"Starte PoseToDepthApp (Modus: {VIEW_MODE})")

        # Indizes für Datenspeicherung
        landmark_indices = list(range(33)) + [99] + [98]
        mapped_points = {idx: None for idx in landmark_indices}

        # Queues holen
        pose_queue = self.queues.get("pose_queue")
        tof_scelet_queue = self.queues.get("tof_scelet")
        scelet_dict_queue = self.queues.get("scelet_dict")

        try:
            while not stop_event.is_set():
                img_depth = None
                img_ab = None
                ts = None
                try:
                    # 1. Daten aus Queue holen (Non-blocking check)
                    if pose_queue and not pose_queue.empty():
                        item = pose_queue.get_nowait()
                        img_depth = item.get("depth", None)
                        img_ab = item.get("ab", None)
                        # Latenz-korrigierter Aufnahmezeitpunkt des TOF-Frames
                        # (gesetzt vom TiefenCamLogger). Identisch zu tof_camera_log.csv
                        # und den tof_frame_{ts}.npy-Dateien.
                        ts = item.get("ts")

                    if img_ab is None or img_depth is None:
                        time.sleep(0.005)
                        continue

                    # Aufnahmezeitpunkt des Frames; Fallback auf Systemzeit, falls der
                    # Logger (noch) keinen ts mitliefert.
                    tm = ts if ts is not None else time.time()

                    # 2. Rotation und Vorbereitung
                    ab_map_rot = cv2.rotate(img_ab, cv2.ROTATE_180)
                    img_depth_rot = cv2.rotate(img_depth, cv2.ROTATE_180)

                    # 3. MediaPipe Verarbeitung
                    ab_map_uint8 = cv2.normalize(ab_map_rot, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                    ab_map_rgb = cv2.cvtColor(ab_map_uint8, cv2.COLOR_GRAY2RGB)
                    results_pose = self.pose.process(ab_map_rgb)

                    # 4. Daten-Extraktion (Mapping depth zu keypoints)
                    if results_pose.pose_landmarks:
                        h, w = img_depth_rot.shape[:2]
                        keypoints_mit_tiefe = [0, 11, 12, 13, 14, 15, 16, 23, 24]

                        for idx, landmark in enumerate(results_pose.pose_landmarks.landmark):
                            x = int(landmark.x * w)
                            y = int(landmark.y * h)
                            if 0 <= x < w and 0 <= y < h:
                                depth_value = img_depth_rot[y, x]
                                mapped_points[idx] = (x, y, depth_value)

                        mapped_points[99] = self.idx_99_value
                        mapped_points[98] = tm

                        # In Daten-Queue schreiben
                        if scelet_dict_queue is not None:
                            put_latest(scelet_dict_queue, mapped_points.copy())
                        self.point_dict.append(mapped_points.copy())

                        # Skelett nur schreiben wenn manuelles Logging aktiv ist
                        # (analog zu den Loggern, die ihr write_row an log_event koppeln).
                        # Ohne log_event (z.B. Auto-Start) wird immer geloggt.
                        if log_event is None or log_event.is_set():
                            self._write_skeleton_row(mapped_points, tm)

                    # 5. VISUALISIERUNG (2D oder 3D)

                    if VIEW_MODE == "3D":
                        # 3D Logik (lokales Fenster)
                        self.update_3d_logic(img_depth_rot, results_pose.pose_landmarks)
                        
                        # 3D zu 2D Image rendern
                        #rendered_image = self.capture_3d_as_image()
                        #rendered_image = cv2.rotate(rendered_image, cv2.ROTATE_180)

                        # Optional: Trotzdem ein einfaches 2D Bild in die Queue schicken, falls GUI es braucht
                        depth_vis = np.clip(img_depth_rot, 0, 2000)
                        depth_vis = cv2.normalize(depth_vis, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_TURBO)
                        if tof_scelet_queue is not None:
                            put_latest(tof_scelet_queue, depth_color)

                    else:
                        # 2D Logik
                        depth_vis = np.clip(img_depth_rot, 0, 2000)
                        depth_vis = cv2.normalize(depth_vis, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_TURBO)

                        if results_pose.pose_landmarks:
                            # Bunte Verbindungen
                            self.draw_colored_2d(depth_color, results_pose.pose_landmarks)

                            # Text Overlay
                            h, w = depth_color.shape[:2]
                            keypoints_mit_tiefe = [0, 11, 12, 13, 14, 15, 16, 23, 24]
                            for idx in keypoints_mit_tiefe:
                                val = mapped_points.get(idx)
                                if val:
                                    x, y, d_val = val
                                    dist_m = d_val / 1000.0
                                    cv2.putText(depth_color, f"{dist_m:.2f}m", (x + 6, y - 6),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                        # FPS Calculation
                        #curr_time = time.time()
                        #fps = 1 / (curr_time - self.prev_time) if (curr_time - self.prev_time) > 0 else 0
                        #self.prev_time = curr_time
                        #cv2.putText(depth_color, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                        #            (255, 255, 255), 2)

                        # In Image-Queue schreiben
                        if tof_scelet_queue is not None:
                            put_latest(tof_scelet_queue, depth_color)

                except Exception as e:
                    # import traceback
                    # traceback.print_exc()
                    # print(f"Fehler in Schleife: {e}")
                    time.sleep(0.5)

        finally:
            self.close_skeleton_log()
            if self.vis:
                self.vis.destroy_window()
            cv2.destroyAllWindows()
            #print("Beende DepthPoseClass.")


# 6. MAIN & LOGGER SETUP
if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

    from logger.tiefencamlogger import TiefenCamLogger

    cv2.setUseOptimized(True)

    # Verzeichnis für Logs (Optional, aber von Loggern benötigt)
    log_dir = Path("C:/Users/SILAB.SILAB1/Documents/fahrsimulator_newestVersion/test")
    os.makedirs(log_dir, exist_ok=True)

    # 2. ToF Logger/Sensor starten
    #print("Initialisiere ToF Kamera...")
    tof_logger = TiefenCamLogger(
        config="config_adsd3500_adsd3030.json",
        mode="lr-qnative",
        output_dir=log_dir,
        fps=12.0,
        ip="ip:10.43.0.1",
        log_path=log_dir / "tof_camera_log.csv",
        raw_pixel_csv=False,
        csv_compressed=False,
    )
    tof_logger.start_sensor()

    # 3. RGB Logger/Sensor starten
    # print("Initialisiere RGB Kamera...")
    # rgb_logger = RgbCameraLogger(
    #     camera_index=0,
    #     file=Path("rgb_camera_log.csv"),
    #     processor=rgb_processor,
    #     live_view=False,
    # )
    # rgb_logger.start_sensor()

    # 4. App Instanziieren (Dependency Injection)
    app = DepthPoseClass()

    # 5. Logging Threads starten (notwendig damit die Processors Daten bekommen)
    logging_thread_tof = threading.Thread(target=tof_logger.start_logging, daemon=True)
    logging_thread_tof.start()
    #print("TOF LOGGING STARTED ========================================")

    # logging_thread_rgb = threading.Thread(target=rgb_logger.start_logging, daemon=True)
    # logging_thread_rgb.start()
    # print("RGB LOGGING STARTED ========================================")

    # Kurze Wartezeit, damit Kameras hochfahren können
    time.sleep(2)

    try:
        # App läuft im Main-Thread
        app.run()
    except KeyboardInterrupt:
        pass
        #print("Unterbrochen durch Benutzer.")
    finally:
        #print("Beende Logging...")
        tof_logger.stop_logging()
        logging_thread_tof.join()
        #print("Fertig.")
