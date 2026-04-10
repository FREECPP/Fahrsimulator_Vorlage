from pandas import DataFrame
import joblib
from rasante_fahrweise_data_processor import get_raw_dataframe, process_dataframe
from collections import Counter


def load_model_and_scaler():
    model_path = "rasante_fahrweise_model.pkl"
    scaler_path = "rasante_fahrweise_scaler.pkl"

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    return model, scaler


def load_data(file: str) -> DataFrame:

    raw_df = get_raw_dataframe(file)
    processed_df = process_dataframe(raw_df)

    print(f"Loaded {file}")

    return processed_df


def predict_driving_style(data: DataFrame):
    x = data.drop('driving_style', axis=1)

    model, scaler = load_model_and_scaler()

    x_scaled = scaler.transform(x)

    print("Making predictions...")

    predictions = model.predict(x_scaled)
    prediction_probabilities = model.predict_proba(x_scaled)

    results = []
    for i, (prediction, probabilities) in enumerate(zip(predictions, prediction_probabilities)):
        result = {
            'group_index': i,
            'prediction': prediction,
            'confidence': max(probabilities),
            'probabilities': dict(zip(model.classes_, probabilities))
        }
        results.append(result)

    print()
    print("=" * 50)
    print("PREDICTION RESULTS")
    print("=" * 50)

    prediction_counts = Counter(predictions)

    print(f"Total groups analyzed: {len(predictions)}")
    print()
    print("Predictions distribution:")
    for style, count in prediction_counts.items():
        percentage = (count / len(predictions)) * 100
        print(f"  {style}: {count} groups ({percentage:.1f}%)")
    print()

    avg_confidence = sum(r['confidence'] for r in results) / len(results)
    print(f"Average prediction confidence: {avg_confidence:.2%}")
    print()

    return results

def main():
    file = "./test_data/silab_log_louis.csv"

    data = load_data(file)
    predict_driving_style(data)

if __name__ == "__main__":
    main()