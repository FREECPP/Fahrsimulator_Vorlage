import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from xgboost import XGBClassifier

"""
Model Train Prozess: 
- Daten erheben und als Dictionary speichern 
- process_data.py ausführen 
- build_segments.py ausführen auf den Output daten von process_data.py
- model_train.py ausführen auf den Output daten von build_segments.py

In der Live Anwendung: 
- Daten holen 
- Segmente aufbauen (build_segments.py Funktionalität) 
- Process Data auf einem Segment ausführen (process_data.py Funktionalität) 
- Modell laden und Vorhersage machen
"""

def train_distraction_model(
    csv_path: str,
    model_out_path: str = "xgb_distraction_model.json",
    target_col: str = "label",
    drop_cols: list[str] | None = None,
):
    """
    Trainiert ein XGBoost-Modell zur Ablenkungserkennung auf Basis einer Feature-CSV
    und speichert das Modell als JSON-Datei.

    Parameters: 
    csv_path : str
        Pfad zur Eingabe-CSV mit Features + Labelspalte.
    model_out_path : str
        Pfad, unter dem das trainierte Modell gespeichert wird.
    target_col : str
        Name der Zielspalte (Label).
    drop_cols : list[str] | None
        Spalten, die NICHT als Features verwendet werden sollen (z. B. IDs, Timestamps).
    """
    if drop_cols is None:
        drop_cols = []

    df = pd.read_csv(csv_path)
    if target_col not in df.columns:
        raise ValueError(f"Zielspalte '{target_col}' nicht in CSV gefunden.")

    y = df[target_col]
    X = df.drop(columns=[target_col] + [c for c in drop_cols if c in df.columns])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=42,
    )

    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    print("=== Confusion Matrix ===")
    print(confusion_matrix(y_test, pred))
    print("\n=== Classification Report ===")
    print(classification_report(y_test, pred, digits=4))

    fi = pd.Series(model.feature_importances_, index=X.columns).sort_values(ascending=False)
    print("\nTop Features:\n", fi.head(20))

    model.save_model(model_out_path)
    print(f"\nModell gespeichert unter: {model_out_path}")

    return model


if __name__ == "__main__":
    csv_path = r"driverDistractionModel/model_train/train_data/extracted_segments.csv"
    model_path = r"driverDistractionModel/model/xgb_distraction_model.json"

    train_distraction_model(
        csv_path=csv_path,
        model_out_path=model_path,
        target_col="label",
        drop_cols=["timestamp", "t_start", "t_end", "num_frames", "frac_label_1"],  
    )
