"""
Führt alle Sensor-CSV-Logs einer Aufnahme-Session zu einem gemeinsamen Log zusammen.

Hintergrund:
    Während einer Aufnahme schreibt jeder Sensor seinen eigenen CSV-Log mit
    unterschiedlichen Sample-Raten (z.B. Silab 100 Hz, Shimmer 51 Hz, RGB-Kamera 20 Hz).
    Dieses Skript fügt alle Logs anhand des gemeinsamen Zeitstempels 'log_time' zusammen,
    sodass am Ende eine einzige CSV mit allen Sensordaten vorliegt.

Vorgehen:
    1. Alle bekannten Sensor-CSVs im Session-Verzeichnis einlesen
    2. Jede CSV bekommt eine 'sensor'-Spalte (z.B. "silab", "shimmer") damit die
       Herkunft jeder Zeile nachvollziehbar bleibt
    3. Alle Zeilen untereinander stapeln (concat) und chronologisch nach log_time sortieren
    4. Forward-Fill: Da die Sensoren zu unterschiedlichen Zeitpunkten messen, sind
       in jeder Zeile die meisten Spalten leer. ffill() trägt den jeweils letzten
       bekannten Wert eines Sensors weiter bis ein neuer Wert kommt
    5. Anfangszeilen entfernen bei denen noch nicht alle Sensoren mindestens einmal
       geliefert haben (sonst stehen dort NaN-Werte)
    6. Ergebnis als combined_log.csv im Session-Verzeichnis speichern

Aufruf (manuell, alternativ zur automatischen Ausführung über LogManager):
    python utils/merge_logs.py --session-dir logfiles/2024-01-01_12-00-00
    python utils/merge_logs.py --session-dir logfiles/2024-01-01_12-00-00 --keep-incomplete
"""

import argparse
import pandas as pd
from pathlib import Path


# Zuordnung: CSV-Dateiname → kurzes Sensor-Label das in der 'sensor'-Spalte erscheint
LOG_FILES = {
    "silab_log.csv":       "silab",
    "shimmer_log.csv":     "shimmer",
    "eyetracker_log.csv":  "eyetracker",
    "tof_camera_log.csv":  "tof",
    "rgb_camera1.csv":     "rgb_camera1",
    "rgb_camera2.csv":     "rgb_camera2",
}

# Name der Zeitstempel-Spalte — muss in allen Sensor-CSVs vorhanden sein
TIMESTAMP_COL = "log_time"


def load_sensor_logs(session_dir: Path) -> list[pd.DataFrame]:
    """
    Liest alle bekannten Sensor-CSVs aus dem Session-Verzeichnis ein.

    Dateien die nicht existieren oder keine 'log_time'-Spalte haben werden
    übersprungen und nicht in das Ergebnis aufgenommen.

    Args:
        session_dir: Pfad zum Session-Verzeichnis mit den Sensor-CSV-Dateien

    Returns:
        Liste von DataFrames, einer pro gefundener Sensor-CSV
    """
    frames = []
    for filename, sensor_label in LOG_FILES.items():
        path = session_dir / filename

        # Datei existiert nicht — Sensor war in dieser Session nicht aktiv
        if not path.exists():
            print(f"  [übersprungen] {filename} nicht gefunden")
            continue

        df = pd.read_csv(path)

        # Zeitstempel-Spalte fehlt — CSV kann nicht zeitlich eingeordnet werden
        if TIMESTAMP_COL not in df.columns:
            print(f"  [übersprungen] {filename} hat keine '{TIMESTAMP_COL}'-Spalte")
            continue

        # Zeitstempel in numerisches Format umwandeln, ungültige Werte (z.B. Leerstrings)
        # werden zu NaN und anschließend entfernt
        df[TIMESTAMP_COL] = pd.to_numeric(df[TIMESTAMP_COL], errors="coerce")
        df.dropna(subset=[TIMESTAMP_COL], inplace=True)

        # Alle Datenspalten mit dem Sensor-Label prefixen (außer log_time) damit
        # Spalten verschiedener Sensoren eindeutig identifizierbar sind.
        # z.B. mean_red → rgb_camera1_mean_red / rgb_camera2_mean_red
        rename_map = {c: f"{sensor_label}_{c}" for c in df.columns if c != TIMESTAMP_COL}
        df = df.rename(columns=rename_map)

        # Sensor-Label hinzufügen damit im kombinierten Log erkennbar ist
        # woher jede Zeile stammt
        df["sensor"] = sensor_label
        frames.append(df)
        print(f"  [geladen] {filename}: {len(df)} Zeilen")

    return frames


def merge_logs(session_dir: Path, keep_incomplete: bool = False) -> pd.DataFrame:
    """
    Führt alle Sensor-Logs eines Session-Verzeichnisses zusammen.

    Die Logs werden untereinander gestapelt und chronologisch sortiert.
    Fehlende Werte werden per Forward-Fill aufgefüllt: Jeder Sensor trägt
    seinen letzten bekannten Wert weiter bis er einen neuen Messwert liefert.

    Args:
        session_dir:      Pfad zum Session-Verzeichnis mit den Sensor-CSV-Dateien
        keep_incomplete:  Falls True, bleiben Anfangszeilen mit NaN-Werten erhalten.
                          Falls False (Standard), werden diese Zeilen entfernt.

    Returns:
        Zusammengeführter DataFrame mit allen Sensordaten

    Raises:
        FileNotFoundError: Falls keine gültigen Sensor-Logs gefunden wurden
    """
    print(f"\nLese Sensor-Logs aus: {session_dir}")
    frames = load_sensor_logs(session_dir)

    if not frames:
        raise FileNotFoundError(f"Keine gültigen Sensor-Logs in {session_dir} gefunden.")

    # Alle Sensor-DataFrames untereinander stapeln (jede Zeile = ein Messwert eines Sensors)
    # und chronologisch nach dem Aufnahmezeitpunkt sortieren
    combined = pd.concat(frames, ignore_index=True).sort_values(TIMESTAMP_COL).reset_index(drop=True)
    combined.insert(1, "sensor", combined.pop("sensor"))
    print(f"\nGesamt vor Merge: {len(combined)} Zeilen, {len(combined.columns)} Spalten")

    # Spalten bestimmen die per Forward-Fill aufgefüllt werden sollen.
    # 'log_time' und 'sensor' werden ausgeschlossen:
    #   - log_time ist der originale Messzeitpunkt und soll nicht überschrieben werden
    #   - sensor gibt die Herkunft der Zeile an und soll nicht von anderen Sensoren geerbt werden
    fill_cols = [c for c in combined.columns if c not in (TIMESTAMP_COL, "sensor")]

    # Forward-Fill: Jede leere Zelle bekommt den zuletzt gemessenen Wert des jeweiligen
    # Sensors. Dadurch ist nach dem Fill in jeder Zeile der aktuellste bekannte Wert
    # aller Sensoren verfügbar — auch wenn dieser Sensor in dieser Zeile nicht gemessen hat.
    combined[fill_cols] = combined[fill_cols].ffill()

    # Für jeden Sensor eine Altersspalte berechnen: Wie viele Sekunden ist der aktuell
    # eingetragene Wert dieses Sensors bereits alt?
    # Vorgehen:
    #   1. Hilfsspalte '{sensor}_last_ts' anlegen — enthält log_time nur in den Zeilen
    #      in denen dieser Sensor tatsächlich gemessen hat, sonst NaN
    #   2. Hilfsspalte per Forward-Fill auffüllen — jede Zeile kennt damit den
    #      Zeitpunkt der letzten echten Messung dieses Sensors
    #   3. Altersspalte berechnen: log_time - letzte_messzeit
    #   4. Hilfsspalte wieder entfernen
    for sensor_label in LOG_FILES.values():
        last_ts_col = f"{sensor_label}_last_ts"
        age_col = f"{sensor_label}_value_age"

        # log_time nur dort eintragen wo diese Zeile vom Sensor selbst stammt
        combined[last_ts_col] = combined.loc[combined["sensor"] == sensor_label, TIMESTAMP_COL]

        # Letzten bekannten Messzeitpunkt in alle nachfolgenden Zeilen weitertragen
        combined[last_ts_col] = combined[last_ts_col].ffill()

        # Alter = aktueller Zeitpunkt - letzter Messzeitpunkt dieses Sensors (in Sekunden)
        combined[age_col] = combined[TIMESTAMP_COL] - combined[last_ts_col]

        # Hilfsspalte wird nicht mehr benötigt
        combined.drop(columns=[last_ts_col], inplace=True)

    if not keep_incomplete:
        # Am Anfang der Aufnahme haben noch nicht alle Sensoren ihren ersten Wert geliefert.
        # Diese Zeilen haben nach dem Forward-Fill immer noch NaN-Werte und werden entfernt,
        # da sie kein vollständiges Bild aller aktiven Sensoren darstellen.
        # Wichtig: Nur Spalten von Sensoren prüfen die tatsächlich Daten geliefert haben.
        # Sensoren mit 0 Zeilen haben überall NaN — würden sonst alle Zeilen löschen.
        active_check_cols = [c for c in fill_cols if combined[c].notna().any()]
        rows_before = len(combined)
        combined.dropna(subset=active_check_cols, inplace=True)
        combined.reset_index(drop=True, inplace=True)
        dropped = rows_before - len(combined)
        if dropped:
            print(f"Entfernt: {dropped} unvollständige Anfangszeilen (--keep-incomplete um das zu ändern)")

    print(f"Ergebnis: {len(combined)} Zeilen, {len(combined.columns)} Spalten")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Sensor-Logs zu einem gemeinsamen Log zusammenführen")
    parser.add_argument(
        "--session-dir",
        required=True,
        help="Pfad zum Session-Verzeichnis mit den Sensor-CSV-Dateien",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Ausgabedatei (Standard: <session-dir>/combined_log.csv)",
    )
    parser.add_argument(
        "--keep-incomplete",
        action="store_true",
        help="Anfangszeilen mit fehlenden Werten behalten (kein dropna)",
    )
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"Fehler: Verzeichnis nicht gefunden: {session_dir}")
        return

    combined = merge_logs(session_dir, keep_incomplete=args.keep_incomplete)

    output_path = Path(args.output) if args.output else session_dir / "combined_log.csv"
    combined.to_csv(output_path, index=False)
    print(f"\nGespeichert: {output_path}")


if __name__ == "__main__":
    main()
