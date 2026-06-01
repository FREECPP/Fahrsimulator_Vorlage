import cv2
import numpy as np
import sys
import os
import time
from pathlib import Path
import mediapipe as mp
from scipy.spatial import cKDTree

# 1. SDK-SETUP (Analog Devices ToF)
try:
    SDK_BIN_PATH = r"C:\Analog Devices\TOF_Evaluation_ADTF3175D-Rel5.0.0\bin"
    if not Path(SDK_BIN_PATH).exists():
        print(f"FATAL: SDK Pfad nicht gefunden: {SDK_BIN_PATH}")
        sys.exit(1)

    os.environ["PATH"] = SDK_BIN_PATH + os.pathsep + os.environ.get("PATH", "")
    sys.path.insert(0, SDK_BIN_PATH)
    import aditofpython as tof
except ImportError:
    print("FEHLER: Konnte 'aditofpython' nicht laden.")
    sys.exit(1)

# 2. CONFIG
RGB_CAMERA_INDEX = 0
TOF_CAMERA_IP = "ip:10.43.0.1"
TOF_CONFIG = "config_adsd3500_adsd3030.json"
TOF_MODE = "lr-qnative"  # qnative = 512x512, native = 1024x1024
TOF_CONFIG_PATH = str(Path(SDK_BIN_PATH) / "config" / TOF_CONFIG)

#performance, nicht jeden Pixel beachten
CLOUD_SAMPLING_STEP = 4


# 3. MAPPER KLASSE

class SparseDepthMapper:

    """
    Punktwolke erzeugen: Tiefenbild in organisierte Punktwolke wandeln.
    Transformation: Punkte mittels $R$ und $T$ ins RGB-Koordinatensystem übertragen.
    Projektion: 3D-Punkte auf die RGB-Bildebene mappen.
    Mapping: Lookup-Map (Depth $\rightarrow$ RGB) erstellen.
    Keypoint-Suche: Nächstgelegenen Tiefenpixel zum MediaPipe-Keypoint (RGB) ermitteln.
    Visualisierung: Punkt im originalen Tiefenbild einzeichnen.
    """
    def __init__(self, calibration_file):
        if not Path(calibration_file).exists():
            raise FileNotFoundError(f"Kalibrierung nicht gefunden: {calibration_file}")

        print(f"Lade Kalibrierung: {calibration_file}")
        calib = np.load(str(calibration_file))

        self.K_rgb = calib['K_rgb']
        self.D_rgb = calib['D_rgb']
        self.K_depth = calib['K_depth']

        # Extrinsics: Rotation und Translation von Depth zu RGB
        self.R = calib['R']
        self.T = calib['T']

        # Umwandlung für cv2.projectPoints (Braucht Rodrigues Vektor statt Matrix)
        self.rvec, _ = cv2.Rodrigues(self.R)
        self.tvec = self.T

        # Intrinsics der Tiefenkamera für 3D-Berechnung vorbereiten
        self.fx_d = self.K_depth[0, 0]
        self.fy_d = self.K_depth[1, 1]
        self.cx_d = self.K_depth[0, 2]
        self.cy_d = self.K_depth[1, 2]

        # Gecachte Grids (werden beim ersten Frame initialisiert)
        self.u_grid = None
        self.v_grid = None
        self.tree = None
        self.valid_indices = None

    def update_map(self, depth_img):
        """
        Erstellt für den aktuellen Frame das Mapping:
        RGB-Pixel-Koordinate -> Tiefen-Pixel-Koordinate
        """
        h, w = depth_img.shape

        # 1. Grid initialisieren (nur einmal)
        if self.u_grid is None:
            self.u_grid, self.v_grid = np.meshgrid(np.arange(w), np.arange(h))
            self.u_flat = self.u_grid.flatten()
            self.v_flat = self.v_grid.flatten()

        # 2. Daten flachklopfen und filtern (nur gültige Tiefen > 0)
        z_flat = depth_img.flatten()

        # Performance Maske: Nur valide Pixel UND Subsampling
        mask = (z_flat > 0)
        if CLOUD_SAMPLING_STEP > 1:
            subset_mask = np.zeros_like(mask, dtype=bool)
            subset_mask[::CLOUD_SAMPLING_STEP] = True
            mask = mask & subset_mask

        z_valid = z_flat[mask]
        u_valid = self.u_flat[mask]
        v_valid = self.v_flat[mask]

        if len(z_valid) == 0:
            self.tree = None
            return

        # 3. De-Projektion: 2D Depth -> 3D Depth
        # X = Z * (u - cx) / fx
        x_3d = z_valid * (u_valid - self.cx_d) / self.fx_d
        y_3d = z_valid * (v_valid - self.cy_d) / self.fy_d

        # Shape (N, 3)
        points_3d = np.stack((x_3d, y_3d, z_valid), axis=-1)

        # 4. Projektion: 3D Depth Space -> 2D RGB Image Plane
        points_2d_rgb, _ = cv2.projectPoints(
            points_3d,
            self.rvec, self.tvec,
            self.K_rgb, self.D_rgb
        )

        points_2d_rgb = points_2d_rgb.reshape(-1, 2)

        # 5. KD-Tree bauen für schnelle Suche
        self.tree = cKDTree(points_2d_rgb)

        # speichern der Ursprungs-Koordinaten passend zum Tree-Index
        self.mapped_u = u_valid
        self.mapped_v = v_valid
        self.mapped_z = z_valid

    def query(self, rgb_x, rgb_y):
        """
        Sucht für einen Punkt im RGB Bild den korrespondierenden Punkt im Tiefenbild.
        """
        if self.tree is None: return None

        # Suche nächsten Nachbarn
        dist, index = self.tree.query([rgb_x, rgb_y], k=1)

        # Wenn der nächste projizierte Tiefenpunkt zu weit weg ist (> 15 Pixel), ignorieren
        if dist > 15.0:
            return None

        return (
            int(self.mapped_u[index]),
            int(self.mapped_v[index]),
            self.mapped_z[index]
        )


# 4. APP KLASSE
class PoseToDepthApp:
    def __init__(self):
        # Initialisiere Mapper
        calib_path = Path(__file__).parent / 'calibration_data.npz'
        self.mapper = SparseDepthMapper(calib_path)

        # MediaPipe
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # ToF Buffer
        self.frame_tof = tof.Frame()

        # FPS
        self.prev_time = 0

    def run(self):
        # 1. Kameras verbinden
        cam_rgb = cv2.VideoCapture(RGB_CAMERA_INDEX)
        cam_rgb.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam_rgb.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # ToF Init
        system = tof.System()
        cameras = []
        cwd = os.getcwd()
        os.chdir(SDK_BIN_PATH)
        if not system.getCameraList(cameras, TOF_CAMERA_IP):
            print("ToF Kamera nicht gefunden!")
            return
        cam_tof = cameras[0]
        cam_tof.initialize(TOF_CONFIG_PATH)
        cam_tof.setFrameType(TOF_MODE)
        cam_tof.start()
        os.chdir(cwd)  # Zurück

        print("Starte Loop... (Beenden mit 'q')")

        try:
            while True:
                # A. Frames holen
                ret, img_rgb = cam_rgb.read()
                img_rgb = cv2.rotate(img_rgb, cv2.ROTATE_180)
                if not ret: continue

                cam_tof.requestFrame(self.frame_tof)
                img_depth = np.array(self.frame_tof.getData("depth"), copy=False, dtype=np.float32)
                img_depth = cv2.rotate(img_depth, cv2.ROTATE_180)

                # B. Mapper Update
                self.mapper.update_map(img_depth)

                # C. Pose Detection auf RGB
                img_rgb_input = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2RGB)
                results = self.pose.process(img_rgb_input)

                # D. Visualisierung vorbereiten
                depth_vis = np.clip(img_depth, 0, 2000)
                depth_vis = cv2.normalize(depth_vis, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_TURBO)

                # E. Mapping und Zeichnen
                if results.pose_landmarks:
                    h_rgb, w_rgb, _ = img_rgb.shape

                    # 1. Alle Punkte mappen und speichern
                    mapped_points = {}  # Key: Index, Value: (u, v, dist)

                    for idx, lm in enumerate(results.pose_landmarks.landmark):
                        cx_rgb = int(lm.x * w_rgb)
                        cy_rgb = int(lm.y * h_rgb)

                        if 0 <= cx_rgb < w_rgb and 0 <= cy_rgb < h_rgb:
                            match = self.mapper.query(cx_rgb, cy_rgb)
                            if match:
                                mapped_points[idx] = match

                    # 2. Verbindungen zeichnen (Skelett)
                    for connection in self.mp_pose.POSE_CONNECTIONS:
                        start_idx = connection[0]
                        end_idx = connection[1]

                        # Nur zeichnen, wenn BEIDE Punkte im Tiefenbild gefunden wurden
                        if start_idx in mapped_points and end_idx in mapped_points:
                            pt1 = (mapped_points[start_idx][0], mapped_points[start_idx][1])
                            pt2 = (mapped_points[end_idx][0], mapped_points[end_idx][1])

                            # Linie zeichnen (Weiß, dünn)
                            cv2.line(depth_color, pt1, pt2, (255, 255, 255), 2)

                    # 3. Punkte und Text zeichnen
                    for idx, (u, v, dist_mm) in mapped_points.items():
                        # Kreis (Cyan)
                        cv2.circle(depth_color, (u, v), 4, (255, 255, 0), -1)

                        # Text (Distanz in Meter)
                        dist_m = dist_mm / 1000.0
                        text = f"{dist_m:.2f}m"

                        # Text klein und fein, damit es lesbar bleibt
                        cv2.putText(depth_color, text, (u + 6, v - 6),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

                    # Debug: Auch auf RGB anzeigen
                    self.mp_drawing.draw_landmarks(
                        img_rgb, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS)

                # FPS Calculation
                curr_time = time.time()
                fps = 1 / (curr_time - self.prev_time)
                self.prev_time = curr_time
                cv2.putText(depth_color, f"FPS: {int(fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)


                cv2.imshow("Depth View (Mapped Skeleton)", depth_color)
                cv2.imshow("RGB View (Source)", img_rgb)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            cam_tof.stop()
            cam_rgb.release()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    app = PoseToDepthApp()
    app.run()