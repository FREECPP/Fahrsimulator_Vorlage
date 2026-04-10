import polars as pl 
import ast
import numpy as np
"""
ToDo: 
     - Referenz, wann schaue ich geradeaus, bzw gebe die rotation für gerade ausschauen an 
     - Integration Eye Tracker Daten -> Schaue ich auf die Straße oder nicht, selbst wenn Kopf gedreht ist
     - Neues Feature, stark nach rechts lehnen oder links lehnen 
     - Neues Feature: Stark nach unten beugen

Features: 
    - Kopf Abstand (Mittel der Tiefenpunkte von Nase, Augen, Ohren)
    - Kopf Rotation (aus Augenpositionen)
    - Distanz rechter Daumen zum Lenkrad (Ellipse)
    - Distanz rechtes Handgelenk zum Lenkrad (Ellipse)
    - Distanz linker Daumen zum Lenkrad (Ellipse)
    - Distanz linkes Handgelenk zum Lenkrad (Ellipse)
    
    - Körper stark in eine Richtung lehnen (aus Hüfte und Schultern)
    - Kopf nach unten geneigt (aus Nase und Augen)
    - Blickrichtung (Eye Tracker)

Warum Decision Tree basiertes Modell? 
    - tabellarische Sensordaten 
    - nicht-lineare Zusammenhänge
    - geringe Datenmenge (im Vergleich zu DL Modellen)
    - Regelbasierte Entscheidungen interpretierbar -> Kopf gedreht oder nicht, Hand am Lenkrad oder nicht
    - Robust gegenüber Ausreißern und fehlenden Werten
    - Sehr effizient für Echtzeit-Anwendungen

Warum nicht alternative KI Modelle? 
    - Benötigen große Trainingsdatenmengen (z. B. neuronale Netze)
    - Geringe Interpretierbarkeit, Verständlichkeit der Entscheidungen und schwer erklärbare Entscheidungen
    - Kein zusätzlicher Nutzen bei bereits semantisch vorverarbeiteten Features
    - Deutlich Höherer Tuning-Aufwand

Warum XGBoost?
    - Keine Feature Normalisierung erforderlich
    - Effiziente Implementierung von Decision Trees -> Gradient Boosting -> neuer Baum lernt aus Fehlern vorheriger Bäume
    - Liefert Feature Importance Scores -> Wichtigkeit der Features für Entscheidungen

    Alternative Baum basierte Modelle:
    - Random Forest: Gut für einfache Aufgaben, kann keine nicht-linearen Zusammenhänge modellieren wie Boosting-Methoden.
    - Logistische Regression: Nur für binäre Klassifikationsaufgaben, nicht geeignet für komplexe nicht-lineare Zusammenhänge.


Features: 
    - head_pitch_deg: absolute Neigungswinkel des Kopfes relativ zum Oberkörper
    - head_pitch_rel: Abweichung vom persönlichen Normalzustand (Dieser wird anhand der ersten n Frames kalibriert)
    - head_pitch_rel_abs: Betrag der Pitch-Abweichung

    - head_distance: Absoluter Abstand des Kopfes (Mittel der Tiefenpunkte von Nase, Augen, Ohren)

    - right_thumb_dist_to_wheel: Distanz des rechten Daumens zur Lenkrad-Ellipse
    - right_thumb_on_wheel: Bool, ob rechter Daumen am Lenkrad ist (innerhalb Toleranz)
    - right_wrist_dist_to_wheel: Distanz des rechten Handgelenks zur Lenkrad-Ellipse
    - right_wrist_on_wheel: Bool, ob rechtes Handgelenk am Lenkrad ist (innerhalb Toleranz)

    - left_wrist_dist_to_wheel: Distanz des linken Handgelenks zur Lenkrad-Ellipse
    - left_wrist_on_wheel: Bool, ob linkes Handgelenk am Lenkrad ist (innerhalb Toleranz)
    - left_thumb_dist_to_wheel: Distanz des linken Daumens zur Lenkrad-Ellipse
    - left_thumb_on_wheel: Bool, ob linker Daumen am Lenkrad ist (innerhalb Toleranz)

    - yaw: Kopfrotation zu Beifahrer oder aus dem Fenster heraus 
    - yaw_abs: Betrag der Kopfrotation
"""

# Im Falle einer Neukalibrierung der Lenkradparameter müsssen die Outputparameter genau hier eingetragen werden 
ELL_CENTER = (359.26324462890625, 461.05926513671875)
ELL_AXES   = (47.21894454956055, 137.8275146484375)
ELL_ANGLE  = 66.99349212646484

def extract_tuple(df): 
    df = df.rename({
        "0": "nose",
        "1": "left_eye_inner",
        "2": "left_eye",
        "3": "left_eye_outer",
        "4": "right_eye_inner",
        "5": "right_eye",
        "6": "right_eye_outer",
        "7": "left_ear",
        "8": "right_ear",
        "9": "mouth_left",
        "10": "mouth_right",
        "11": "left_shoulder",
        "12": "right_shoulder",
        "13": "left_elbow",
        "14": "right_elbow",
        "15": "left_wrist",
        "16": "right_wrist",
        "17": "left_pinky",
        "18": "right_pinky",
        "19": "left_index",
        "20": "right_index",
        "21": "left_thumb",
        "22": "right_thumb",
        "23": "left_hip",
        "24": "right_hip",
        "25": "left_knee",
        "26": "right_knee",
        "27": "left_ankle",
        "28": "right_ankle",
        "29": "left_heel",
        "30": "right_heel",
        "31": "left_foot_index",
        "32": "right_foot_index",
    })

    cols = ["nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_wrist", "right_wrist", "left_thumb", "right_thumb", "timestamp"]
    df = df.select(cols)
    for col in cols:
        if col != "label" and col != "timestamp":  # "label" und "timestamp" bleiben unverändert
            df = df.with_columns([
                pl.col(col)
                .str.replace_all(r"[()]", "")  # Entferne Klammern
                .str.split(",")  # Trenne die Werte durch das Komma
                .alias(col)
            ])
            df = df.with_columns([
                pl.col(col)
                .list.eval(               
                    pl.element()
                        .str.strip_chars()  
                )
                .alias(col)
            
            ])

            # Wertekonvertierung in x, y, d und Leerzeichen entfernen
            df = df.with_columns([
                pl.col(col).list.get(0).str.strip_chars().cast(pl.Int64).alias(f"{col}_x"),   # x-Wert
                pl.col(col).list.get(1).str.strip_chars().cast(pl.Int64).alias(f"{col}_y"),   # y-Wert
                pl.col(col).list.get(2).str.strip_chars().cast(pl.Float64).alias(f"{col}_d"), # d-Wert
            ])
            df = df.drop(col)
    return df

def point_to_ellipse_distance_newton(x: float, y: float, a: float, b: float, iters: int = 15) -> float:
    """
    Kürzeste euklidische Distanz von Punkt (x,y) zur Ellipse x^2/a^2 + y^2/b^2 = 1.
    Ellipse ist achsengerade (nicht rotiert), Mittelpunkt im Ursprung.
    """
    x = abs(float(x))
    y = abs(float(y))

    if x == 0.0 and y == 0.0:
        return min(a, b)  # Distanz vom Ursprung zur Ellipse
    if a <= 0.0 or b <= 0.0:
        return np.nan

    t = np.arctan2(y * a, x * b)

    for _ in range(iters):
        ct = np.cos(t)
        st = np.sin(t)

        ex = a * ct
        ey = b * st

        f  = (ex - x) * (-a * st) + (ey - y) * (b * ct)
        fp = (a*st)**2 + (b*ct)**2 + (ex - x) * (-a * ct) + (ey - y) * (-b * st)

        if fp == 0.0:
            break

        t_new = t - f / fp
        if abs(t_new - t) < 1e-12:
            t = t_new
            break
        t = t_new

    ex = a * np.cos(t)
    ey = b * np.sin(t)

    return float(np.hypot(ex - x, ey - y))

def add_ellipse_distance_exact(
    df: pl.DataFrame,
    x_col: str,
    y_col: str,
    z_col: str | None = None,
    out_col: str = "dist_to_wheel_ellipse",
    out_col_bool: str = "hand_on_wheel",
    tol_xy: float =40.0,                 # <-- Toleranz in Pixeln
) -> pl.DataFrame:
    cx, cy = ELL_CENTER

    a = float(ELL_AXES[0])
    b = float(ELL_AXES[1])

    theta = np.deg2rad(float(ELL_ANGLE))
    cos_t = float(np.cos(theta))
    sin_t = float(np.sin(theta))

    def _dist(s) -> float | None:
        x = s["x"]
        y = s["y"]
        z = s["z"] if "z" in s else None

        if x is None or y is None:
            return None

        dx = float(x) - cx
        dy = float(y) - cy

        x_p =  cos_t * dx + sin_t * dy
        y_p = -sin_t * dx + cos_t * dy

        return point_to_ellipse_distance_newton(x_p, y_p, a, b)

    struct_cols = [pl.col(x_col).alias("x"), pl.col(y_col).alias("y")]
    if z_col is not None:
        struct_cols.append(pl.col(z_col).alias("z"))

    df = df.with_columns(
        pl.struct(struct_cols)
          .map_elements(_dist, return_dtype=pl.Float64)
          .alias(out_col)
    )

    df = df.with_columns(
        (
            (pl.col(out_col).is_not_null()) &
            (pl.col(out_col) <= tol_xy)
        ).alias(out_col_bool)
    )

    return df


def add_head_pitch_from_ears(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns([
        ((pl.col("left_ear_y") + pl.col("right_ear_y")) / 2).alias("_ear_mid_y"),
        ((pl.col("left_ear_d") + pl.col("right_ear_d")) / 2).alias("_ear_mid_d"),
    ])

    df = df.with_columns([
        (pl.col("nose_y") - pl.col("_ear_mid_y")).alias("_dy"),
        (pl.col("nose_d") - pl.col("_ear_mid_d")).alias("_dz"),
    ])

    df = df.with_columns(
        pl.struct(["_dy","_dz"]).map_elements(
            lambda s: None if (s["_dy"] is None or s["_dz"] is None)
            else float(np.degrees(np.arctan2(float(s["_dy"]), float(s["_dz"])))),
            return_dtype=pl.Float64
        ).alias("head_pitch_deg")
    )

    return df.drop(["_ear_mid_y","_ear_mid_d","_dy","_dz"])

def extract_features(df): 
    head_depth_cols = [
        "nose_d",
        "left_eye_d",
        "right_eye_d",
        "left_ear_d",
        "right_ear_d",
    ]

    df = df.with_columns(
        pl.mean_horizontal([pl.col(c) for c in head_depth_cols])
        .alias("head_distance")
    )

    df = df.with_columns(
        (pl.col("right_ear_d") - pl.col("left_ear_d"))
        .alias("yaw_depth")
    )
    df = df.with_columns(
        (
            pl.col("nose_x") -
            ((pl.col("left_ear_x") + pl.col("right_ear_x")) / 2)
        ).alias("yaw_pixel")
    )
    
    df = df.with_columns(
        (
            pl.col("yaw_pixel") * 0.7 +
            pl.col("yaw_depth") * 0.3
        ).alias("yaw")
    )
    df = df.with_columns(
        pl.col("yaw").abs().alias("yaw_abs")
    )

    df = df.with_columns(
        pl.col("yaw").abs().alias("head_rotation")
    )
    df = df.drop(["yaw_pixel", "yaw_depth"])

    pl.Config.set_tbl_rows(300)
    

    df = add_ellipse_distance_exact(
        df,
        x_col="right_thumb_x",
        y_col="right_thumb_y",
        z_col="right_thumb_d",
        out_col="right_thumb_dist_to_wheel",
        out_col_bool="right_thumb_on_wheel",
    )
    df = add_ellipse_distance_exact(
        df,
        x_col="right_wrist_x",
        y_col="right_wrist_y",
        z_col="right_wrist_d",
        out_col="right_wrist_dist_to_wheel",
        out_col_bool="right_wrist_on_wheel",
    )
    df = add_ellipse_distance_exact(
        df,
        x_col="left_wrist_x",
        y_col="left_wrist_y",
        z_col="left_wrist_d",
        out_col="left_wrist_dist_to_wheel",
        out_col_bool="left_wrist_on_wheel",
    )

    df = add_ellipse_distance_exact(
        df,
        x_col="left_thumb_x",
        y_col="left_thumb_y",
        z_col="left_thumb_d",
        out_col="left_thumb_dist_to_wheel",
        out_col_bool="left_thumb_on_wheel",
    )
    return df

def pre_process(df): 
    df = extract_tuple(df)
    df = extract_features(df)
    df = add_head_pitch_from_ears(df)
    return df


if __name__ == "__main__":
    df = pl.read_csv("driverDistractionModel/model_train/train_data/train_data.csv")
    df = pre_process(df)
    cols = [
        "head_pitch_deg",
        "head_pitch_rel",
        "head_pitch_rel_abs",
        "head_distance",
        "right_thumb_dist_to_wheel",
        "right_thumb_on_wheel",
        "right_wrist_dist_to_wheel",
        "right_wrist_on_wheel",
        "left_wrist_dist_to_wheel",
        "left_wrist_on_wheel",
        "left_thumb_dist_to_wheel",
        "left_thumb_on_wheel",
        "yaw",
        "yaw_abs", 
        #"yaw_abs_smooth",
    ]
    df = df.select(cols + ["timestamp", "label"])
    df.write_csv("driverDistractionModel/model_train/train_data/extracted_features.csv")
    
