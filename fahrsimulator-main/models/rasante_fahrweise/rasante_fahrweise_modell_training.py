import pandas as pd
from pandas import DataFrame
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

from models.rasante_fahrweise.rasante_fahrweise_data_processor import process_raw_data


def get_processed_data(load_data: bool = False) -> DataFrame:
    processed_data = None

    if load_data:
        print("Loading processed data...")
        try:
            processed_data = pd.read_csv("rasante_fahrweise_processed_data.csv")
            print("Loaded processed data from rasante_fahrweise_processed_data.csv")
            print()
            print("Using loaded data")
        except FileNotFoundError as e:
            print(f"Failed to load processed data. Processing data. {e}")

    if processed_data is None:
        print("Processing data...")
        processed_data = process_raw_data()
        processed_data.to_csv("rasante_fahrweise_processed_data.csv", index=False)
        print()
        print("Processed data saved to rasante_fahrweise_processed_data.csv")
        print()
        print("Using processed data")

    return processed_data


def main(
    load_data: bool = False
):
    processed_data = get_processed_data(load_data)

    print(f"Dataset shape: {processed_data.shape}")
    print(f"Driving style distribution:\n{processed_data['driving_style'].value_counts()}")
    print()

    x = processed_data.drop('driving_style', axis=1)
    y = processed_data['driving_style']

    print(f"Features shape: {x.shape}")
    print(f"Target shape: {y.shape}")
    print()

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"Training set size: {x_train.shape[0]}")
    print(f"Testing set size: {x_test.shape[0]}")
    print()

    print("Scaling features...")
    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_test_scaled = scaler.transform(x_test)
    print("Feature scaling complete!")
    print()

    print("Training Random Forest classifier...")
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    model.fit(x_train_scaled, y_train)
    print("Model training complete!")
    print()

    y_pred = model.predict(x_test_scaled)

    # Evaluate model
    print("=" * 50)
    print("MODEL EVALUATION")
    print("=" * 50)
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print()

    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print()

    print("Classification Report:")
    print(classification_report(y_test, y_pred))
    print()

    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': x.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    print("Top 10 Most Important Features:")
    print(feature_importance.head(10).to_string(index=False))
    print()

    model_filename = "rasante_fahrweise_model.pkl"
    scaler_filename = "rasante_fahrweise_scaler.pkl"

    joblib.dump(model, model_filename)
    joblib.dump(scaler, scaler_filename)

    print(f"Model saved to {model_filename}")
    print(f"Scaler saved to {scaler_filename}")
    print()

    return model, scaler


if __name__ == "__main__":
    main()