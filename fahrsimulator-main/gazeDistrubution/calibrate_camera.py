import numpy as np
import cv2
import os
from pathlib import Path


CHECKERBOARD = (9, 6)
# real size of chessboard squares
SQUARE_SIZE_MM = 40
# resolution of picture
CALIBRATION_WIDTH = 640
CALIBRATION_HEIGHT = 480
# minimal calibration pictures
MIN_CALIBRATION_PHOTOS = 5
# safe location
CALIBRATION_FOLDER = Path(__file__).parent/'Bilder_Eyetracker_Visualisierung'


def calibrate_camera():

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
    objp = objp * SQUARE_SIZE_MM

    objpoints = []
    imgpoints = []

    image_paths = [os.path.join(CALIBRATION_FOLDER, f)
                   for f in os.listdir(CALIBRATION_FOLDER)
                   if f.endswith(('.png', '.jpg'))]

    if not image_paths:
        print(f"[FEHLER] Es wurden keine Bilder im Ordner '{CALIBRATION_FOLDER}' gefunden.")
        print("Bitte zuerst Bilder mit dem 'capture'-Modus aufnehmen.")
        return

    print(f"Verarbeite {len(image_paths)} Bilder...")

    # frame size in k-matrix
    frame_size = (0, 0)

    for fname in image_paths:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        frame_size = gray.shape[::-1]

        ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)

        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

            img = cv2.drawChessboardCorners(img, CHECKERBOARD, corners2, ret)

        cv2.imshow('Ecken gefunden', img)
        cv2.waitKey(100)

    cv2.destroyAllWindows()

    if len(objpoints) < MIN_CALIBRATION_PHOTOS:
        print(f"[FEHLER] Es wurden nur {len(objpoints)} Schachbrettmuster erkannt. Benötigt: {MIN_CALIBRATION_PHOTOS}.")
        return

    print("\n--- Kalibrierung startet ---")
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, frame_size, None, None
    )

    print(f"Erfolgreich kalibriert: {ret}")
    print(f"Reprojektionsfehler: {ret:.4f} (Werte unter 1.0 sind gut)")

    print("\nIntrinsics (K-Matrix):")
    print(mtx)

    print("\nVerzerrungskoeffizienten (Distortion Coefficients):")
    print(dist)

    np.savez('calib_results_640x480.npz', mtx=mtx, dist=dist)
    print("\nErgebnisse gespeichert unter 'calib_results_640x480.npz'")

    return mtx, dist


def capture_images():

    os.makedirs(CALIBRATION_FOLDER, exist_ok=True)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[FEHLER] Kamera konnte nicht geöffnet werden.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CALIBRATION_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CALIBRATION_HEIGHT)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Kameraauflösung: {w}x{h}. Bitte das Schachbrett in verschiedenen Winkeln zeigen.")

    img_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_flipped = cv2.flip(frame, 1)

        status_text = f"Bilder: {img_count}/{MIN_CALIBRATION_PHOTOS}. [S]peichern, [C]alibrieren, [Q]uit."
        cv2.putText(frame_flipped, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow('Kameraansicht', frame_flipped)

        key = cv2.waitKey(1) & 0xFF

        if key == ord('s'):
            file_name = os.path.join(CALIBRATION_FOLDER, f"calib_img_{img_count:02d}.png")
            cv2.imwrite(file_name, frame)
            img_count += 1
            print(f"Bild gespeichert: {file_name}")

        elif key == ord('c'):
            # start calibration
            cap.release()
            cv2.destroyAllWindows()
            if img_count < MIN_CALIBRATION_PHOTOS:
                print(f"[WARN] Nicht genug Bilder ({img_count}). Benötigt: {MIN_CALIBRATION_PHOTOS}.")
                break
            else:
                calibrate_camera()
                break

        elif key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    print("--- Start der Kamerakalibrierung ---")
    print(f"Bitte erstellen Sie ein {CHECKERBOARD[0]}x{CHECKERBOARD[1]} (innere Ecken) Schachbrettmuster!")
    capture_images()