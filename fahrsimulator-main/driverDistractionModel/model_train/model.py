"""
Features für ein Modell, welches Ablenkungen erkennt:
    - 3D SkelettPunkte (MediaPipe -> X,Y und TOF Tiefe) --> Linke, rechte Schulter; Linkes, rechtes Auge; Linkes, rechtes Ohr; Nase; Linkes, rechtes Handgelenk
    - Kopfdrehung (Yaw, Pitch, Roll) aus 3D Skelettpunkten
    - Kopfabstand zur Kamera (aus TOF Tiefe der Nasenpunktes oder d_mean)
    - Distanz linke, rechte Hand zum Lenkrad 

Bearbeitungsschritte: 
    1) Distanz Lenkrad und Radius -> Bereich bestimmen
    1) Daten holen (3D Skelettpunkte) -> aus Niklar Modell, vorerst in eine CSV packen 
    2) Features extrahieren (diese Datei) auch 
    3) 3s Segmente aufbauen und Labeln 
    4) Modell trainieren -> XGBoost --> Wichtig: TimeStamps entfernen
    5) Modell abspeichern und dann in Echtzeit laufen lassen 
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

class Model:
    # --- Lenkrad-Parameter (an dein Setup anpassen!) ---
    # Mittelpunkt des Lenkrads (im Bild, in Pixeln)
    WHEEL_CX = 416          # x
    WHEEL_CY = 473           # y
    WHEEL_R = 73.78        # Radius des Lenkrads (in Pixeln)
    WHEEL_DEPTH_MEAN = 701.00    # mittlere Tiefe des Lenkrads (in mm)
    WHEEL_DEPTH_TOL = 50.0       # erlaubte Abweichung in z
    WHEEL_RADIUS_TOL = 30.0


    # ### Aus den Kalibrierungen vom Tool:
    # WHEEL_CX = 416
    # WHEEL_CY = 473
    # WHEEL_R  = 73.78
    # WHEEL_DEPTH_MEAN = 701.00


    def __init__(self):
        # aktuell nichts zu tun
        pass

    @staticmethod
    def hand_on_wheel(x, y, z):
        """
        Gibt True zurück, wenn die Hand am Lenkradring liegt.
        Bedingungen:
        - Pixel-Position in der Nähe des Ringradius (Kreis um (WHEEL_CX, WHEEL_CY))
        - Tiefe in der Nähe von WHEEL_DEPTH_MEAN
        """
        if x is None or y is None or z is None:
            return False

        # 2D-Abstand der Hand zum Lenkrad-Mittelpunkt
        dx = x - Model.WHEEL_CX
        dy = y - Model.WHEEL_CY
        pixel_dist = np.sqrt(dx * dx + dy * dy)

        # 1. Liegt die Hand auf dem Ring? (Abstand zum Radius ist klein)
        near_ring = abs(pixel_dist - Model.WHEEL_R) <= Model.WHEEL_RADIUS_TOL

        # 2. Stimmt die Tiefe ungefähr mit der Lenkradtiefe überein?
        depth_ok = abs(z - Model.WHEEL_DEPTH_MEAN) <= Model.WHEEL_DEPTH_TOL

        # Nur wenn beides erfüllt ist, werten wir das als "Hand berührt Lenkrad"
        return near_ring and depth_ok

    @staticmethod
    def dist_hand_to_wheel_3d_like(hand_x, hand_y, hand_z):
        """
        Liefert eine kombinierte Distanz der Hand zum Lenkradring:
        - 2D-Abstand zum Ring (Pixel)
        - plus Abweichung in der Tiefe (z)
        Das ist kein echtes metrisches 3D, aber ein gutes Feature.
        """
        if hand_x is None or hand_y is None or hand_z is None:
            return None

        dx = hand_x - Model.WHEEL_CX
        dy = hand_y - Model.WHEEL_CY
        pixel_dist = np.sqrt(dx * dx + dy * dy)

        # Abstand zur idealen Ringlinie (Radius)
        dist_ring_px = abs(pixel_dist - Model.WHEEL_R)

        # Depth-Abweichung
        dz = abs(hand_z - Model.WHEEL_DEPTH_MEAN)

        # Gewichtung, damit Pixel- und Depth-Skala halbwegs passen
        ALPHA = 0.01  # ggf. empirisch anpassen
        return float(np.sqrt(dist_ring_px * dist_ring_px + ALPHA * dz * dz))

    def extract_features(self, ts: str, data_points: dict) -> dict:
        """
        Wichtig!!!: Timestamps schon im richtigen Format
        data_points: dict mit z.B.
            nose_x, nose_y, nose_z,
            left_eye_x, left_eye_y, left_eye_z,
            right_eye_x, right_eye_y, right_eye_z,
            left_ear_z, right_ear_z,
            left_wrist_x, left_wrist_y, left_wrist_z,
            right_wrist_x, right_wrist_y, right_wrist_z,
            ...

        Gibt ein Feature-Dict zurück, das direkt ins ML-Modell gehen kann.
        """
        features = {}

        features["timestamp"] = ts

        # -------------------------
        # Kopfabstand (Mean der Kopf-Tiefenpunkte)
        # -------------------------
        head_points = [
            data_points.get("nose_z"),
            data_points.get("left_eye_z"),
            data_points.get("right_eye_z"),
            data_points.get("left_ear_z"),
            data_points.get("right_ear_z"),
        ]
        head_points_valid = [p for p in head_points if p is not None]
        features["head_distance"] = float(np.mean(head_points_valid)) if head_points_valid else None

        # -------------------------
        # Kopf-Roll (Neigung) aus Augen
        # -------------------------
        lx, ly = data_points["left_eye_x"], data_points["left_eye_y"]
        rx, ry = data_points["right_eye_x"], data_points["right_eye_y"]

        dx = rx - lx
        dy = ry - ly
        if dx == 0:
            features["head_roll"] = 0.0
        else:
            features["head_roll"] = float(np.degrees(np.arctan2(dy, dx)))

        # -------------------------
        # Hand-Lenkrad-Features
        # -------------------------
        lw_x = data_points.get("left_wrist_x")
        lw_y = data_points.get("left_wrist_y")
        lw_z = data_points.get("left_wrist_z")

        rw_x = data_points.get("right_wrist_x")
        rw_y = data_points.get("right_wrist_y")
        rw_z = data_points.get("right_wrist_z")

        # Bool: Hand am Lenkrad?
        features["left_hand_on_wheel"] = Model.hand_on_wheel(lw_x, lw_y, lw_z)
        features["right_hand_on_wheel"] = Model.hand_on_wheel(rw_x, rw_y, rw_z)

        # Distanz zur Lenkrad-Region (Ring + Depth kombiniert)
        features["left_hand_wheel_dist"] = Model.dist_hand_to_wheel_3d_like(lw_x, lw_y, lw_z)
        features["right_hand_wheel_dist"] = Model.dist_hand_to_wheel_3d_like(rw_x, rw_y, rw_z)


        return features


    def raw_csv_feature_extraction(self, path_in: str, path_out: str):
        """
        Liest eine Roh-CSV mit 3D Skelettpunkten ein,
        extrahiert Features und speichert sie in eine neue CSV.
        """
        df_in = pd.read_csv(path_in)
        feature_rows = []

        for _, row in df_in.iterrows():
            data_points = row.to_dict()
            features = self.extract_features(data_points)
            # Falls timestamp gebraucht:
            features["ts"] = row["timestamp"]
            feature_rows.append(features)

        df_out = pd.DataFrame(feature_rows)
        df_out.to_csv(path_out, index=False)

        print(f"Gespeichert unter: {path_out}")


    def build_window_csv(path_frame_features: str, path_windows_out: str,
                        window_seconds: float = 3.0,
                        step_seconds: float = 0.5):
        """
        Liest Frame-Features ein und erzeugt 3-Sekunden-Fenster.

        sliding-window: alle step_seconds
        jedes Fenster dauert window_seconds
        """
        df = pd.read_csv(path_frame_features)
        window_rows = []

        t_current = df["ts"].iloc[0]
        t_end_limit = df["ts"].iloc[-1]

        while t_current + window_seconds <= t_end_limit:

            # Fensterende
            t_window_end = t_current + window_seconds

            # rows zwischen t_current & t_window_end
            window = df[
                (df["ts"] >= t_current) &
                (df["ts"] < t_window_end)
            ]

            if len(window) == 0:
                t_current += step_seconds
                continue

            w = {}
            w["t_start"] = float(t_current)
            w["t_end"] = float(t_window_end)

            # Aggregationen
            w["mean_head_distance"] = window["head_distance"].mean()
            w["std_head_roll"] = window["head_roll"].std()
            w["frac_left_hand_on_wheel"] = window["left_hand_on_wheel"].mean()
            w["frac_right_hand_on_wheel"] = window["right_hand_on_wheel"].mean()
            w["mean_left_hand_dist"] = window["left_hand_wheel_dist"].mean()
            w["max_right_hand_dist"] = window["right_hand_wheel_dist"].max()

            window_rows.append(w)

            # Verschieben des Fensterstarts (SLIDING)
            t_current += step_seconds

        df_window = pd.DataFrame(window_rows)
        df_window.to_csv(path_windows_out, index=False)

        print("Saved:", path_windows_out)

    def train(self, path_windows_labeled: str, model_out_path: str = "distraction_xgb.pkl"):
        """
        Trainiert ein XGBoost-Modell auf Fenster-Features.
        
        Erwartet eine CSV mit:
          - t_start, t_end
          - Feature-Spalten (z.B. mean_head_distance, ...)
          - label (0 = nicht abgelenkt, 1 = abgelenkt)
        """
        # 1. Daten laden
        df = pd.read_csv(path_windows_labeled)

        if "label" not in df.columns:
            raise ValueError("In der CSV fehlt die Spalte 'label'.")

        # 2. Features / Ziel trennen
        X = df.drop(columns=["label", "t_start", "t_end"])
        Y = df["label"]

        # 3. Train/Test-Split
        X_train, X_val, y_train, y_val = train_test_split(
            X, Y,
            test_size=0.2,
            stratify=Y,
            random_state=42,
        )

        # 4. XGBoost-Modell definieren
        clf = XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            n_jobs=-1,
        )

        # 5. Trainieren
        clf.fit(X_train, y_train)

        # 6. Evaluation auf Validation-Set
        y_pred = clf.predict(X_val)
        print("Validation Report:")
        print(classification_report(y_val, y_pred, digits=3))

        # 7. Modell in der Instanz speichern
        self.clf = clf

        # 8. Modell auf Platte speichern
        joblib.dump(clf, model_out_path)
        print(f"Modell gespeichert unter: {model_out_path}")

    


if __name__ == "__main__":
    # Einfacher Test
    data_points = {
        "nose_x": 310, "nose_y": 90, "nose_z": 540,
        "left_eye_x": 290, "left_eye_y": 80, "left_eye_z": 535,
        "right_eye_x": 330, "right_eye_y": 80, "right_eye_z": 538,
        "left_ear_x": 270, "left_ear_y": 85, "left_ear_z": 545,
        "right_ear_x": 350, "right_ear_y": 85, "right_ear_z": 550,
        "left_wrist_x": 250, "left_wrist_y": 150, "left_wrist_z": 530,
        "right_wrist_x": 360, "right_wrist_y": 160, "right_wrist_z": 540,
    }

    model = Model()

    features = model.extract_features(data_points)
    print(features)