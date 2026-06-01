from pathlib import Path
from queue import Empty
from typing import Optional, Dict
from pathlib import Path

from joblib.externals.loky.backend.queues import Queue
import pandas as pd
import joblib

from models.rasante_fahrweise.rasante_fahrweise_data_processor import process_dataframe


class RasanteFahrweisePredictionModel:

    def __init__(
        self,
        queues: Dict[str, Queue],
        model_path: Optional[str] = None,
        scaler_path: Optional[str] = None,
    ):
        self._queues = queues or {}
        self._load_model_and_scaler(model_path, scaler_path)
        self.silab_queue = self._queues.get("silab_model")
        self._output_queue = self._queues.get("rasante_fahrweise_model")
        self._data_buffer: list[Dict] = []

    def _load_model_and_scaler(self, model_path: Optional[str] = None, scaler_path: Optional[str] = None):

        current_dir = Path(__file__).parent

        model_abs_path = current_dir / (model_path if model_path else "rasante_fahrweise_model.pkl")
        scaler_abs_path = current_dir / (scaler_path if scaler_path else "rasante_fahrweise_scaler.pkl")


        self.model = joblib.load(model_abs_path)
        self.scaler = joblib.load(scaler_abs_path)


    def _update_data(self, data: Dict):
        self._data_buffer.append(data)
        self._data_buffer = self._data_buffer[-10000:] # Only keep the last 10000 values


    def run(self, stop_event):
        try:
            while not stop_event.is_set():
                if self.silab_queue:
                    try:
                        data = self.silab_queue.get_nowait()
                        self._update_data(data)
                    except Empty:
                        pass

                self.predict_driving_style()
        except KeyboardInterrupt:
            print("\n[RasanteFahrweisePredictionModel] KeyboardInterrupt – run() wird beendet.")
        finally:
            print("[RasanteFahrweisePredictionModel] run() gestoppt.")


    def predict_driving_style(self):
        data = process_dataframe(pd.DataFrame(self._data_buffer))
        if data is None:
            return
        try:
            x = data.drop('driving_style', axis=1)
        except KeyError:
            x = data

        if len(x) == 0:
            return

        x_scaled = self.scaler.transform(x)

        predictions = self.model.predict(x_scaled)
        prediction_probabilities = self.model.predict_proba(x_scaled)
        last_prediction, last_probabilities = list(zip(predictions, prediction_probabilities))[-1]

        result = {
            'group_index': 0,
            'prediction': last_prediction,
            'confidence': max(last_probabilities),
            'probabilities': dict(zip(self.model.classes_, last_probabilities))
        }
        self._output_queue.put(result)