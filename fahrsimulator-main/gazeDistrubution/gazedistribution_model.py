import cv2
import numpy as np
import time
from collections import deque
from queue import Empty
import queue as _queue
from gazeDistrubution.distraction_analyzer import DistractionAnalyzer

def safe_array(a, dtype=float):
    if a is None: return None
    arr = np.asarray(a, dtype=dtype)
    return arr.reshape(3) if arr.size == 3 and not np.any(np.isnan(arr)) else None

def normalize(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n != 0 and not np.isnan(n) else None

def ray_plane_intersection(ray_o, ray_d, plane_pt, plane_n):
    denom = np.dot(ray_d, plane_n)
    if abs(denom) < 1e-9: return None, None
    t = np.dot(plane_pt - ray_o, plane_n) / denom
    return (ray_o + t * ray_d, t) if t > 0 else (None, None)

def calibrate_camera_position(corners, img_pts, intr):
    obj_pts = np.array(corners, dtype=np.float32)
    img_pts = np.array(img_pts, dtype=np.float32)
    _, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, intr, np.zeros((4, 1)))
    R, _ = cv2.Rodrigues(rvec)
    return R, tvec.flatten()


class RealTimeGaze3D:
    HEATMAP_SEC = 5.0

    def __init__(
            self,
            queues=None,
            **kwargs
    ):
        """
        Initialisierung für Multiprocessing.
        Daten kommen ausschließlich über self.queues.
        """
        self.queues = queues or {}

        # Kamera- & Screen-Setup
        self.cam_intr = np.array([[1.0, 0.0, 320.0], [0.0, 1.0, 240.0], [0.0, 0.0, 1.0]])
        self.screen_corners = [
            np.array([-430.0, 450.0, -100.0]), np.array([430.0, 450.0, -100.0]),
            np.array([-430.0, -10.0, -170.0]), np.array([430.0, -10.0, -170.0])
        ]
        cam_img_pts = [(565, 455), (120, 433), (540, 207), (120, 202)]

        self.cam_R, self.cam_t = calibrate_camera_position(self.screen_corners, cam_img_pts, self.cam_intr)

        # Geometrie
        scale = 0.001
        s_tl, s_tr, s_bl = self.screen_corners[0] * scale, self.screen_corners[1] * scale, self.screen_corners[
            2] * scale
        self.plane_origin = s_tl
        self.plane_x, self.plane_y = s_tr - s_tl, s_bl - s_tl
        self.plane_normal = normalize(np.cross(self.plane_x, self.plane_y))

        self.heatmap_points = deque()

        # Analyzer anpassen: Wir übergeben die Polygone hier zentral
        self.analyzer = DistractionAnalyzer(
            road_polygon=[[565, 455], [120, 433], [540, 207], [160, 202]],
            mirror_polygon=[[260, 440], [260, 400], [410, 400], [410, 440]],
            eor_threshold_s=1.5
        )


    def run(self, stop_event):
        self._run_loop(stop_event)

    def _run_loop(self, stop_event):
        print("[INFO] RealTimeGaze3D (Multiprocessing) gestartet.")

        while not stop_event.is_set():
            try:
                gaze = None
                frame = None

                gaze_queue = self.queues.get("eyetracker")
                frame_queue = self.queues.get("rgb_frame2")

                if gaze_queue and not gaze_queue.empty():
                    try:
                        gaze = gaze_queue.get_nowait()
                    except Empty:
                        gaze = None

                if frame_queue and not frame_queue.empty():
                    try:
                        frame = frame_queue.get_nowait()
                    except Empty:
                        frame = None


                heat_col = self.generate_heatmap_img(frame.shape)
                blended = cv2.addWeighted(frame, 0.4, heat_col, 0.6, 0)

                if gaze:
                    cp = self.get_camera_pixel(gaze)
                    if cp:
                        self.append_heatpoint(cp)
                        distracted, aoi = self.analyzer.update(cp[0], cp[1])

                        # Visualisierung
                        cv2.circle(blended, cp, 15, (255, 0, 255), -1)
                        color = (0, 255, 0) if not distracted else (0, 0, 255)
                        cv2.putText(blended, f"AOI: {aoi}", (10, 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)


                try:

                    gaze_distribution_model = self.queues.get("gaze_distribution_model")
                    if gaze_distribution_model is not None:
                        put_latest(gaze_distribution_model, blended)

                    time.sleep(0.05)
                except Empty:
                    pass

                # Not needed after GUI implementation
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set()

            except Exception as e:
                continue

        cv2.destroyAllWindows()

    def get_camera_pixel(self, gaze):
        Qs = []
        for eye in ('left', 'right'):
            o_raw = safe_array(gaze.get(f"{eye}_gaze_origin_in_user_coordinate_system"))
            p_raw = safe_array(gaze.get(f"{eye}_gaze_point_in_user_coordinate_system"))
            if o_raw is not None and p_raw is not None:
                o, p = o_raw * 0.001, p_raw * 0.001
                Q, t = ray_plane_intersection(o, normalize(p - o), self.plane_origin, self.plane_normal)
                if Q is not None: Qs.append(Q)
        if not Qs: return None
        P = np.mean(Qs, axis=0)
        rel = P - self.plane_origin
        u = np.dot(rel, self.plane_x) / np.dot(self.plane_x, self.plane_x)
        v = np.dot(rel, self.plane_y) / np.dot(self.plane_y, self.plane_y)
        P3 = self.plane_origin + u * self.plane_x + v * self.plane_y
        Pc = (self.cam_R @ P3) + self.cam_t
        if Pc[2] <= 1e-8: return None
        proj = self.cam_intr @ (Pc / Pc[2])
        return int(round(proj[0])), int(round(proj[1]))

    def append_heatpoint(self, cp):
        now = time.time()
        self.heatmap_points.append((now, cp[0], cp[1]))
        while self.heatmap_points and self.heatmap_points[0][0] < now - self.HEATMAP_SEC:
            self.heatmap_points.popleft()

    def generate_heatmap_img(self, shape):
        h, w = shape[:2]
        heat = np.zeros((h, w), dtype=np.float32)
        for _, x, y in self.heatmap_points:
            if 0 <= x < w and 0 <= y < h: heat[y, x] += 1.0
        heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=30, sigmaY=30)
        if heat.max() > 0:
            return cv2.applyColorMap((heat / heat.max() * 255).astype(np.uint8), cv2.COLORMAP_JET)
        return np.zeros((h, w, 3), dtype=np.uint8)
