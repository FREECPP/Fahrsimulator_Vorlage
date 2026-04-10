import numpy as np
import time
import cv2


class DistractionAnalyzer:
    def __init__(self, road_polygon, mirror_polygon, eor_threshold_s=1.5):
        self.road_poly = np.array(road_polygon, dtype=np.int32)
        self.mirror_poly = np.array(mirror_polygon, dtype=np.int32)
        self.eor_threshold_s = eor_threshold_s

        self.eor_start_time = None
        self.is_distracted = False

    def update(self, x, y):
        pt = (int(x), int(y))
        now = time.time()

        # AOI Erkennung
        if cv2.pointPolygonTest(self.road_poly, pt, False) >= 0:
            current_aoi = "Road_Ahead"
        elif cv2.pointPolygonTest(self.mirror_poly, pt, False) >= 0:
            current_aoi = "Mirror"
        else:
            current_aoi = "Internal_Distraction"

        # Logik für Ablenkung
        if current_aoi == "Road_Ahead":
            self.eor_start_time = None
            self.is_distracted = False
        else:
            if self.eor_start_time is None:
                self.eor_start_time = now

            duration = now - self.eor_start_time
            # Spiegel-Blick darf doppelt so lang sein
            limit = self.eor_threshold_s * 2 if current_aoi == "Mirror" else self.eor_threshold_s

            if duration > limit:
                self.is_distracted = True

        return self.is_distracted, current_aoi