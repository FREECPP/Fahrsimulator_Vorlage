import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List

# --- SETUP ---
CHESSBOARD_SIZE = (9, 6)
CHESSBOARD_SQUARE_SIZE_MM = 40
BASE_DIR = Path(__file__).parent / "bilder"


class AdvancedCalibrator:

    def __init__(self):
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        # 3D Punkte des Schachbretts (immer gleich)
        self.objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
        self.objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
        self.objp = self.objp * CHESSBOARD_SQUARE_SIZE_MM

    def find_corners(self, img_path):
        """Hilfsfunktion: Findet Ecken in einem Bild"""
        img = cv2.imread(str(img_path))
        if img is None: return None, None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

        if ret:
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), self.criteria)
            return corners, gray.shape[::-1]  # return shape (w, h)
        return None, None

    def calibrate_single_lens(self, folder_name: str, label: str):
        """Kalibriert eine einzelne Kamera (Intrinsics)"""
        folder = BASE_DIR / folder_name
        images = sorted(folder.glob("*.png"))

        if not images:
            print(f"WARNUNG: Keine Bilder in {folder_name} gefunden!")
            return None, None, None

        print(f"\n--- Kalibriere {label} ({len(images)} Bilder) ---")

        objpoints = []
        imgpoints = []
        image_shape = None

        valid_count = 0
        for fname in images:
            corners, shape = self.find_corners(fname)
            if corners is not None:
                objpoints.append(self.objp)
                imgpoints.append(corners)
                image_shape = shape
                valid_count += 1
                print(f".", end="")
            else:
                print("x", end="")

        print(f"\n{valid_count} von {len(images)} Bildern nutzbar.")

        if valid_count < 5:
            raise ValueError(f"Zu wenig gute Bilder für {label}!")

        # Intrinsische Kalibrierung
        err, K, D, rvecs, tvecs = cv2.calibrateCamera(
            objpoints, imgpoints, image_shape, None, None
        )
        print(f"Reprojection Error {label}: {err:.4f}")
        return K, D, image_shape

    def calibrate_stereo(self, K_depth, D_depth, K_rgb, D_rgb, shape_depth):
        """
        Kalibriert Stereo:
        Kamera 1 = Depth (ToF)
        Kamera 2 = RGB
        """
        folder = BASE_DIR / "stereo"
        rgb_files = sorted(folder.glob("rgb_*.png"))
        depth_files = sorted(folder.glob("ir_*.png"))

        print(f"\n--- Kalibriere Stereo ({len(rgb_files)} Paare) ---")
        print("   (Depth ist Kamera 1, RGB ist Kamera 2)")

        objpoints = []
        imgpoints_depth = []  # Kamera 1
        imgpoints_rgb = []  # Kamera 2

        valid_count = 0
        for f_rgb, f_depth in zip(rgb_files, depth_files):
            c_rgb, s_rgb = self.find_corners(f_rgb)
            c_depth, s_depth = self.find_corners(f_depth)

            if c_rgb is not None and c_depth is not None:
                objpoints.append(self.objp)
                imgpoints_depth.append(c_depth)  # Zuerst Depth!
                imgpoints_rgb.append(c_rgb)  # Dann RGB!
                valid_count += 1
                print(".", end="")
            else:
                print("x", end="")

        print(f"\n{valid_count} Paare nutzbar.")

        flags = cv2.CALIB_FIX_INTRINSIC

        # WICHTIG: Hier alles tauschen!
        # imageSize muss shape_depth sein (weil Depth = Cam 1)
        err, K1, D1, K2, D2, R, T, E, F = cv2.stereoCalibrate(
            objpoints,
            imgpoints_depth, imgpoints_rgb,  # Punkte getauscht
            K_depth, D_depth,  # Matrix 1 (Depth)
            K_rgb, D_rgb,  # Matrix 2 (RGB)
            shape_depth,  # <--- GRÖSSE VON KAMERA 1
            criteria=self.criteria,
            flags=flags
        )

        print(f"Stereo Reprojection Error: {err:.4f}")
        return R, T

    def run(self):
        # 1. RGB Linsen-Kalibrierung
        K_rgb, D_rgb, shape_rgb = self.calibrate_single_lens("rgb_intrinsics", "RGB")

        # 2. ToF Linsen-Kalibrierung
        K_depth, D_depth, shape_depth = self.calibrate_single_lens("depth_intrinsics", "Depth")

        # 3. Stereo Kalibrierung
        # Wir übergeben Depth zuerst und AUCH die shape_depth als Referenzgröße
        R, T = self.calibrate_stereo(K_depth, D_depth, K_rgb, D_rgb, shape_depth)

        # 4. Rektifizierung berechnen
        print("\nBerechne Rektifizierungs-Matrizen...")

        # ACHTUNG: Auch hier Depth an erster Stelle!
        # imageSize = shape_depth (Input Größe Cam 1)
        # newImageSize = shape_depth (Gewünschte Output Größe)
        R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
            K_depth, D_depth,  # Cam 1
            K_rgb, D_rgb,  # Cam 2
            shape_depth,  # Größe Cam 1
            R, T,  # Rotation Depth -> RGB
            alpha=0,  # 0 = Zoom / Keine schwarzen Ränder
            newImageSize=shape_depth  # Output Zielgröße
        )

        # 5. Speichern
        # WICHTIG: P1 ist jetzt Depth, P2 ist jetzt RGB!
        out_file = Path(__file__).parent / 'calibration_data.npz'
        np.savez(
            str(out_file),
            K_rgb=K_rgb, D_rgb=D_rgb,
            K_depth=K_depth, D_depth=D_depth,
            R=R, T=T,
            R1=R1, R2=R2,
            P1=P1,  # Gehört jetzt zu Depth!
            P2=P2,  # Gehört jetzt zu RGB!
            Q=Q,
            rgb_shape=shape_rgb, depth_shape=shape_depth
        )
        print(f"Fertig! Daten gespeichert in: {out_file.name}")
        print("HINWEIS FÜR SPÄTER: P1/R1 gehören jetzt zur Tiefenkamera, P2/R2 zur RGB-Kamera!")


if __name__ == '__main__':
    calib = AdvancedCalibrator()
    calib.run()