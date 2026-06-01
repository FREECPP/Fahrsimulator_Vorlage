import cv2
import mediapipe as mp
import numpy as np
import time

"""
Eye Aspect Ratio (EAR) Calibration Script

Dieses Skript dient zur Kalibrierung der Eye-Aspect-Ratio (EAR) für die
Blink- und Augen-Zustands-Erkennung mittels MediaPipe Face Mesh.

Die EAR beschreibt das Verhältnis zwischen vertikalen und horizontalen
Abständen ausgewählter Augen-Landmarks und wird verwendet, um zwischen
offenen und geschlossenen Augen zu unterscheiden.

Der hier ermittelte Schwellenwert (Threshold) wird in der Konfigurationsdatei
'config.ini' unter dem Abschnitt [Mediapipe] als 'EyeAspectRatio' eingetragen
und anschließend von Echtzeit-Systemen (z. B. Fahrerüberwachung,
Aufmerksamkeits- oder Müdigkeitserkennung) genutzt.

Ablauf der Kalibrierung:
1. Aufnahme mit normal geöffneten Augen
2. Aufnahme mit bewusstem Blinzeln / geschlossenen Augen
3. Berechnung eines empfohlenen EAR-Schwellenwerts als Mittelwert beider Phasen
"""
mp_face = mp.solutions.face_mesh

def eye_aspect_ratio(landmarks, eye_idx):
    p = [np.array([landmarks[i].x, landmarks[i].y]) for i in eye_idx]
    d1 = np.linalg.norm(p[1] - p[5])
    d2 = np.linalg.norm(p[2] - p[4])
    d3 = np.linalg.norm(p[0] - p[3])
    return (d1 + d2) / (2.0 * d3)

def calibrate_step(cap, face_mesh, duration, instruction_text, text_color):
    ear_values = []
    start = time.time()

    while time.time() - start < duration:
        ok, frame = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = face_mesh.process(rgb)
        if not res.multi_face_landmarks:
            cv2.putText(frame, "Gesicht nicht erkannt", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)
            cv2.imshow("Kalibrierung", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break
            continue

        lm = res.multi_face_landmarks[0].landmark

        left_idx = [33, 160, 158, 133, 153, 144]
        right_idx = [362, 385, 387, 263, 373, 380]

        ear_l = eye_aspect_ratio(lm, left_idx)
        ear_r = eye_aspect_ratio(lm, right_idx)
        ear_values.append((ear_l + ear_r) / 2)

        cv2.putText(frame, instruction_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2)

        cv2.imshow("Kalibrierung", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    return float(np.mean(ear_values)) if ear_values else None


def run_calibration():
    cap = cv2.VideoCapture(0)

    with mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True) as face_mesh:
        open_ear = calibrate_step(cap, face_mesh, 3, "Augen normal offen lassen", text_color=(0,255,0))
        time.sleep(1)
        closed_ear = calibrate_step(cap, face_mesh, 3, "Blinzle bewusst", text_color=(255,0,0))

    cap.release()
    cv2.destroyAllWindows()

    threshold = (open_ear + closed_ear) / 2 if open_ear and closed_ear else None
    return open_ear, closed_ear, threshold


if __name__ == "__main__":
    open_val, closed_val, threshold_val = run_calibration()
    print(f"Open EAR: {open_val:.3f}")
    print(f"Closed EAR: {closed_val:.3f}")
    print(f"Empfohlener Threshold: {threshold_val:.3f}")
