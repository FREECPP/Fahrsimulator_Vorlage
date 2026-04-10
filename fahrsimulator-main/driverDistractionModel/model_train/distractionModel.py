import polars as pl
from typing import Callable, Optional, Dict, Any, List
from xgboost import XGBClassifier
import time
from driverDistractionModel.model_train.process_dict import pre_process
from queue import Empty

from utils.queue_utils import put_latest

FEATURE_BASE_COLS = [
    "head_distance",
    "yaw",
    "yaw_abs",
    "head_pitch_deg",
    "right_wrist_on_wheel",
    "left_wrist_on_wheel",
    "right_thumb_on_wheel",
    "left_thumb_on_wheel",
]

def compute_segment_features_from_window(window_df: pl.DataFrame) -> pl.DataFrame:

    if window_df.height == 0:
        raise ValueError("window_df ist leer — keine Features berechenbar.")

    pl_feat = pre_process(window_df)

    missing = [c for c in FEATURE_BASE_COLS if c not in pl_feat.columns]
    if missing:
        raise ValueError(f"Fehlende Feature-Spalten nach pre_process(): {missing}")

    pl_feat = pl_feat.select(FEATURE_BASE_COLS)

    agg_exprs = []
    for col in FEATURE_BASE_COLS:
        agg_exprs.append(pl.col(col).mean().alias(f"{col}_mean"))

    pl_seg = pl_feat.select(agg_exprs)

    return pl_seg

class distractionModel:
    """
    Echtzeit-Modell für Fahrerablenkung.

    - Lädt ein XGBoost-Modell aus einer JSON-Datei
    - Nimmt fortlaufend Frames als Dict entgegen
    - Hält intern ein 3s-Zeitfenster
    - Aggregiert das Fenster zu Segment-Features (mithilfe von Funktion: feature_fn)
    - Gibt bei jedem Schritt (wenn genug Frames vorhanden sind) eine Vorhersage zurück:
        - label: 0 = aufmerksam, 1 = abgelenkt
        - prob_distracted: Wahrscheinlichkeit für Ablenkung
        - ampel: "🟢" oder "🔴"
    """

    def __init__(
        self,
        model_path: str,
        feature_fn: Callable[[pl.DataFrame], pl.DataFrame] = compute_segment_features_from_window,
        window_s: float = 3.0,
        min_frames: int = 3,
        timestamp_col: str = "timestamp",
        queues = None,
    ):
        """
        model_path : str
            Pfad zur gespeicherten XGBoost-JSON-Datei.
        feature_fn : callable
            Funktion, die aus einem Fenster-DataFrame (mehrere Frames)
            eine 1-zeilige Feature-DataFrame fürs Modell baut.
            Signatur: feature_fn(window_df: pd.DataFrame) -> pd.DataFrame
        window_s : float
            Länge des Zeitfensters in Sekunden (z.B. 2.0).
        min_frames : int
            Mindestanzahl an Frames, die im Fenster vorhanden sein müssen,
            damit eine Vorhersage berechnet wird.
        timestamp_col : str
            Key im Frame-Dict für den Zeitstempel (time.time()).
        """
        self.window_s = window_s
        self.min_frames = min_frames
        self.timestamp_col = timestamp_col
        self.feature_fn = feature_fn

        # Modell laden
        self.model = XGBClassifier()
        self.model.load_model(model_path)

        self._buffer: List[Dict[str, Any]] = []
        self._feature_columns: Optional[List[str]] = None
        self._stop = False

        self.queues = queues or {}

    def reset(self) -> None:
        """Buffer leeren (z.B. bei neuer Fahrt)."""
        self._buffer.clear()

    def stop(self) -> None:
        """run()-Loop sauber beenden."""
        self._stop = True

    def _update_buffer(self, frame: Dict[str, Any]) -> None:
        """
        Neuen Frame in den Buffer hängen und alte Frames
        außerhalb des window_s-Fensters entfernen.
        """
        ts = float(frame[98])
        f = dict(frame)  
        f[self.timestamp_col] = ts

        self._buffer.append(f)
        t_min = ts - self.window_s
 
        self._buffer = [fr for fr in self._buffer if float(fr[self.timestamp_col]) >= t_min]

    def _make_window_df(self) -> pl.DataFrame:
        """Aktuelles Fenster als DataFrame zurückgeben."""
        if not self._buffer:
            return pl.DataFrame()
        fixed_rows = []
        for row in self._buffer:
            out = {}
            for k, v in row.items():
                key = str(k)
                if isinstance(v, tuple):
                    x, y, z = v
                    out[key] = f"({int(x)},{int(y)},{float(z)})"
                else:
                    out[key] = v

            fixed_rows.append(out)

        return pl.from_dicts(fixed_rows)

    def add_frame(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        returns. 
            result : dict oder None
                Wenn genug Frames im Fenster:
                    {
                        "label": 0 oder 1,
                        "prob_distracted": float,
                        "ampel": "🟢" oder "🔴",
                        "n_frames": int,
                    }
        """
        self._update_buffer(frame)
        if len(self._buffer) < self.min_frames:
            return None

        window_df = self._make_window_df()

        time_span = (
            window_df.select(pl.col(self.timestamp_col).max()).item()
            - window_df.select(pl.col(self.timestamp_col).min()).item()
        )

        if time_span < self.window_s * 0.8:  
            return None

        feat_df = self.feature_fn(window_df)

        if feat_df.height != 1:
            raise ValueError("feature_fn muss einen DataFrame mit genau einer Zeile zurückgeben.")

        if self._feature_columns is None:
            self._feature_columns = feat_df.columns
        else:
            missing = [c for c in self._feature_columns if c not in feat_df.columns]
            if missing:
                raise ValueError(f"Fehlende Feature-Spalten in feat_df: {missing}")

            feat_df = feat_df.select(self._feature_columns)
        
        feat_np = feat_df.to_numpy()

        #Modellvorhersage
        pred_label = int(self.model.predict(feat_np)[0])
        prob = float(self.model.predict_proba(feat_np)[0, 1])  # Wahrscheinlichkeit für Klasse 1

        ampel = "🔴" if pred_label == 1 else "🟢"

        return {
            "label": pred_label,
            "prob_distracted": prob,
            "ampel": ampel,
            "n_frames": len(self._buffer),
        }

    def run(self, stop_event) -> None:
        """
        Parameters: 
        sleep_s : float
            Optionales Sleep zwischen Iterationen (z.B. 0.0 oder 0.01).
        """
        time.sleep(8)
        sleep_s = float(0.1)

        print("[distractionModel] run() gestartet – Strg+C zum Stoppen.")
        scelet_dict_queue = self.queues.get("scelet_dict")
        distraction_dict_queue = self.queues.get("distraction_model_queue")
        try:
            while not stop_event.is_set():
                frame = None
                if scelet_dict_queue and not scelet_dict_queue.empty():
                        try: 
                            frame = scelet_dict_queue.get_nowait()
                        except Empty:
                            frame = None

                if frame is None:   
                    if sleep_s > 0:
                        time.sleep(sleep_s)
                    continue

                result = self.add_frame(frame)

                if result is None:
                    if sleep_s > 0:
                        time.sleep(sleep_s)
                    continue

                prob = result["prob_distracted"]
                label = result["label"]
                n_frames = result["n_frames"]

                distraction_dict = {
                    "label": label,
                    "prob_distracted": prob,
                    "n_frames": n_frames,
                }
                if distraction_dict_queue:
                    put_latest(distraction_dict_queue, distraction_dict)

                if sleep_s > 0:
                    time.sleep(sleep_s)

        except KeyboardInterrupt:
            print("\n[distractionModel] KeyboardInterrupt – run() wird beendet.")
        finally:
            self._stop = True
            print("[distractionModel] run() gestoppt.")
