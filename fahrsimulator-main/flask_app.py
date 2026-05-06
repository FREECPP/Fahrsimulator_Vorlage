from utils.app_logging_utils import printlog
from flask import Flask, Response, request, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import socket

import threading
import cv2
import base64
import configparser
import os
import numpy as np
import time
import math

from datetime import datetime
from multiprocessing import Queue
from typing import Optional
from queue import Empty
from flask_cors import CORS
from extensions import db

from controllers.projectController import verzeichnis_bp
from extensions import db
from dbModels.dashboardLayoutDB import dashboardLayout

# Optional / lazy imports (auskommentiert gelassen wie bei dir)
# from logger.log_manager import LogManager
# from logger.frame_processor import Processor, EyetrackerProcessor, SilabDataProcessor

# ==================================================================================
# Initialising Webapp Data
# ==================================================================================

# 1. Flask-Instanz erstellen
# __name__ sagt Flask, wo es nach Dateien (Statics/Templates) suchen soll.
app = Flask(__name__)

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True
)

# 2. Blueprints registrieren
# Blueprints erlauben es, Routen (URLs) in anderen Dateien zu definieren.
# url_prefix="/" sorgt dafür, dass die Routen direkt unter der Hauptdomain liegen.
# Beispiel: Ein Blueprint in 'verzeichnis_bp' könnte die Route für dein Dashboard sein.


app.register_blueprint(verzeichnis_bp, url_prefix="/")

# 3. SocketIO initialisieren
# Damit wird die Standard-HTTP-App um Echtzeit-Fähigkeiten (WebSockets) erweitert.
# cors_allowed_origins="*" erlaubt den Zugriff von beliebigen anderen Adressen (wichtig für Dev-Umgebungen).
socketio = SocketIO(app, cors_allowed_origins="*")

# 4. Netzwerk-Konfiguration
# Wir versuchen den Port aus einer Umgebungsvariable (z.B. vom Server) zu lesen.
# Falls keine gesetzt ist, nutzen wir 9999 als Standard-Port.
port = int(os.getenv('PORT', 9999))

# '0.0.0.0' bedeutet: Die App ist über alle Netzwerk-Schnittstellen erreichbar.
# Das ist nötig, wenn du z.B. vom Handy oder einem anderen PC im Netz auf die KI-Daten zugreifen willst.
host = "0.0.0.0"


# ==================================================================================
# Initialising Database
# ==================================================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
DB_PATH = "app.db"
dummyProject = "demo3"

# DB erstellen falls nicht vorhanden
if app.debug:
    with app.app_context():
        db.create_all()

# ==================================================================================
# Initialising Logger Data
# ==================================================================================
logging_manager = None
BASE_DIR = None
is_running = False
stream_thread = None
EMIT_INTERVAL = 0

# Alle Threads bekommen von dieser Variablen mit (Prinzipiell eine Flag die quasi auf True und auf False gesetzt werden kann)
# Jedoch erhalten alle Threads gleichzeitig diese Info
stream_stop_event = threading.Event()

# ==================================================================================
# Initialising Queue for Multiprocessing IPC
# ==================================================================================
data_queues = {
    "eyetracker": Queue(maxsize=1),
    "silab": Queue(maxsize=1),
    "tof": Queue(maxsize=1),
    "rgb": Queue(maxsize=1), 
    "pose_queue": Queue(maxsize=1), 
    "rgb2": Queue(maxsize=1),
    "rgb_frame2": Queue(maxsize=1),
    "tof_scelet": Queue(maxsize=1),
    "distraction_model_queue": Queue(maxsize=1),
    "scelet_dict": Queue(maxsize=1),
    "silab_model": Queue(maxsize=1),
    "shimmer": Queue(maxsize=1),
    "rasante_fahrweise_model": Queue(maxsize=1),
    "shimmer_hrv": Queue(maxsize=1),
    "gaze_distribution_model": Queue(maxsize=1),

}

def deleteAndRecreateDB():
    with app.app_context():
        # Alte DB löschen (falls vorhanden)
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print("🗑️ Alte DB gelöscht")

        # Neue DB erstellen
        db.create_all()
        print("✅ Neue DB erstellt")



# ==================================================================================
# Helper function for loading 'config.ini' Data
# ==================================================================================
def load_config():
    """
    Lädt die Anwendungskonfiguration aus einer externen INI-Datei.

    Die Funktion liest Netzwerk-Einstellungen (HOST, PORT) und Verzeichnispfade 
    aus der 'config.ini'. Zudem wird das Basis-Verzeichnis (BASE_DIR) 
    automatisch erstellt, falls es noch nicht existiert.
    """

    # 1. Initialisierung des Parsers für .ini-Dateien
    config = configparser.ConfigParser()

    # 2. Pfad-Ermittlung
    # os.path.dirname(__file__) ermittelt den Ordner, in dem dieses Skript liegt.
    # So wird die config.ini immer relativ zum Skript gefunden, egal von wo es gestartet wird.
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    # 3. Sicherheitscheck: Existiert die Datei überhaupt?
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found: {config_path}")
    
    # Datei einlesen
    config.read(config_path)

    # 4. Globale Variablen definieren
    # Das erlaubt es, die Werte für port und host überall im Programm zu nutzen.
    global port, host
    try:
        # Versucht, die Netzwerk-Einstellungen aus der Sektion [General] zu lesen.
        #port = config.get('General', 'PORT')
        host = str(config.get('General', 'HOST'))
    except Exception as e:

        # Fehlermeldung, falls die Sektion oder die Schlüssel fehlen.
        printlog(f"Data from 'config.ini' couldn't be read. Versichern Sie sich, dass PORT und HOST unter [General] existieren. {e}", "error")

    try:
        # 5. Basis-Verzeichnis für Daten laden/erstellen
        # Liest den Pfad aus der Config (z.B. für Logs oder Sensor-Dumps).
        base_dir = config.get('General', 'BASE_DIR')

        # Erstellt das Verzeichnis automatisch, falls es noch nicht existiert.
        # 'exist_ok=True' verhindert einen Fehler, falls der Ordner schon da ist.
        os.makedirs(base_dir, exist_ok=True)
    except Exception as e:
        printlog(f"Be sure 'config.ini', BASE_DIR under [General] exists and the path is valid. {e}", "error")

@app.route("/api/layout/<project_name>", methods=["GET", "POST", "DELETE"])
def handle_layout(project_name):

    if request.method == "POST":
        data = request.get_json()

        layout_data = data.get("layout", [])
        widgets = data.get("widgets", [])

        try:
            existing = dashboardLayout.query.filter_by(project_name=project_name).first()

            if existing:
                existing.layout = layout_data
                existing.widgets = widgets
            else:
                new_layout = dashboardLayout(
                    project_name=project_name,
                    layout=layout_data,
                    widgets=widgets
                )
                db.session.add(new_layout)

            db.session.commit()

            return jsonify({"status": "saved"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "GET":
        layout = dashboardLayout.query.filter_by(project_name=project_name).first()

        if not layout:
            return jsonify({"layout": [], "widgets": []})

        return jsonify({
            "layout": layout.layout,
            "widgets": layout.widgets
        })

    if request.method == "DELETE":
        try:
            existing = dashboardLayout.query.filter_by(project_name=project_name).first()
            if not existing:
                return jsonify({"status": "not_found"}), 404

            db.session.delete(existing)
            db.session.commit()
            return jsonify({"status": "deleted"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/layouts", methods=["GET"])
def get_all_layouts():
    layouts = dashboardLayout.query.all()

    result = []
    for l in layouts:
        result.append({
            "project_name": l.project_name
        })

    return jsonify(result)

# ==================================================================================
# Index.html
# ==================================================================================
        
# Pfad zur index.html
@app.route("/")
def index():
    return render_template("index.html")

# Nicht mehr vorhanden
@app.route("/stop_logging", methods=["POST"])
def stop_logging():
    print("stopped")
    return render_template("index.html")

# Pfad zum Dashboard
@app.route("/dashboard")
def show_dashboard():
    return render_template("dashboard.html")

# ==================================================================================
# Dashboard.html
# ==================================================================================
@socketio.on('connect')
def handle_connect():
    server_ip = get_server_ip()
    printlog(f"Client connected to server {server_ip}:{port}")

def get_server_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # keine echte Verbindung nötig
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip
# Start-Button handling on 'dashboard.html'
# Funktion handle_start_recording() wird ausgeführt, wenn der Start-Button im Dashboard betätigt wird
@socketio.on('start_recording')
def handle_start_recording():
    global logging_manager, is_running, stream_thread

    # Hier wird überprüft ob der Logmanager nicht bereits gestartet wurde, falls ja, soll die Funktion beendet werden
    if is_running:
        socketio.emit('is_running', True)
        return

    # Eigene Print Funktion um den Start des Log-Managers im Terminal erkenntlich zu machen
    printlog(message="Starte Log-Manager", debug_lvl="info", std_print=True)
    from controllers.projectController import project_path
    printlog(message=str(project_path), debug_lvl="info", std_print=True)

    try:
        # Log-manager Klasse wird importiert und ein Objetk wird angelegt
        # Als Data-Queues werden die oben instanzierten Queues mit der Länge von 1 genutzt
        from logger.log_manager import LogManager  # Lazy-import to support preview mode without sensors
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging_manager = LogManager(directory=project_path, data_queues=data_queues, timestamp=now)

        # Startet alle Logging Funktionen der einzelnen Sensoren - return value wird verwendet um festzustellen ob die 
        # logging Funktionen bereits gestartet wurden
        is_running = logging_manager.start_logging_async()

        # Sendet ans Dashboard das Applikation läuft 
        socketio.emit('is_running', is_running)

        # Allen Threads wird gleichzeitig bescheid gegeben, dass diese Flag zurückgesetzt wurde
        stream_stop_event.clear()

        # Erstellt und startet einen neuen Thread, der die Funktion read_queue ausführen soll 
        stream_thread = threading.Thread(target=read_queue, args=(logging_manager, stream_stop_event), daemon=True)
        stream_thread.start()

    except Exception as e:
        # Falls die Hardware/SDK Depencies nicht verfügbar sind, soll in einem neuen Thread die Funktion
        # mock_sensor_stream gestartet werden um eine Preview des UI's zu ermöglichen
        logging_manager = None
        is_running = True
        printlog(f"Fallback to mock sensor stream: {e}", "warning")
        socketio.emit('is_running', True)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=mock_sensor_stream, args=(stream_stop_event,), daemon=True)
        stream_thread.start()

# Stop-Button handling on 'dashboard.html'
# Funktion handle_stop_recording wird ausgeführt, wenn der Stop-Button betätigt wird
@socketio.on('stop_recording')
def handle_stop_recording():
    global logging_manager, is_running, stream_thread

    # Thread-übergreifende Flag wird gesetzt 
    stream_stop_event.set()
    
    # Prüfen, ob überhaupt ein Thread existiert und ob dieser noch aktiv ist
    if stream_thread and stream_thread.is_alive():

        # Warte maximal 1 Sekunde darauf, dass der Thread sich beendet.
        # Dies geschieht meistens, nachdem 'stream_stop_event.set()' aufgerufen wurde.
        stream_thread.join(timeout=1.0)
    
    # Die Referenz löschen, damit die Variable für einen Neustart bereit ist 
    # und der Garbage Collector den Speicher freigeben kann.
    stream_thread = None

    if logging_manager:

        # Falls ein logging_manager existiert, werden nun alle Prozesse beendet
        logging_manager._stop_logger_processes()

        # logging_manager variable wird deinitialisiert
        logging_manager = None
    
    # is_running wird auf False gesetzt und ans Dashboard gesendet
    is_running = False
    socketio.emit('is_running', is_running)


# Hilfsfunktion, um Tiefendaten (Distanzwerte) für die Live-Vorschau in ein JPEG umzuwandeln
def encode_depth_to_jpg(depth: np.ndarray) -> Optional[str]:

    # 1. Sicherheitscheck: Wenn keine Daten da sind, brich ab
    if depth is None:
        return None
    
    # 2. Datenbereinigung: Ersetzt ungültige Werte (NaN - Not a Number) durch 0
    # Das ist wichtig, da KI-Tiefenkameras oft Messfehler haben, die OpenCV zum Absturz bringen könnten.
    depth = np.nan_to_num(depth)

    # Hinweis: Die auskommentierten Zeilen unten würden die Tiefendaten (oft 16-Bit Grau) 
    # in ein farbiges Bild (Heatmap) umwandeln, damit man sie mit dem menschlichen Auge besser versteht.
    #depth_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    #depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

    # 3. Kompression: Wandelt das NumPy-Array in das JPEG-Format um
    # 'ok' ist ein Boolean (Erfolg?), 'buffer' enthält die binären Bilddaten.
    ok, buffer = cv2.imencode(".jpg", depth)
    if not ok:
        return None
    
    # 4. Übertragungsformat: Wandelt die binären Daten in einen Base64-String um
    # Das ist nötig, damit das Bild als Text über JSON/WebSockets verschickt werden kann.
    return base64.b64encode(buffer).decode()


def encode_rgb_stream_frame(rgb_frame) -> Optional[str]:

    # 1. Check auf Existenz
    if rgb_frame is None:
        return None

    # 2. Flexibilitäts-Check: Ist das Bild bereits ein Base64-String?
    if isinstance(rgb_frame, str):
        return rgb_frame

    # 3. Falls das Bild bereits binär vorliegt (z.B. direkt vom Sensor-Buffer)
    if isinstance(rgb_frame, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(rgb_frame)).decode()

    # 4. Standardfall: Das Bild liegt als OpenCV/NumPy-Array vor
    # Wir komprimieren es zu JPEG, um Bandbreite zu sparen.
    ok, buffer = cv2.imencode(".jpg", rgb_frame)
    if not ok:
        return None
    
    # 5. Umwandlung in Text-Format (Base64) für den Versand
    return base64.b64encode(buffer.tobytes()).decode()

# Main function to send data per 'socket.emit()' to the dashboard.html
def read_queue(logging_manager, stop_event):
    tof_queue = logging_manager.data_queues.get("tof")
    rgb2_queue = logging_manager.data_queues.get("rgb2")
    rgb_queue = logging_manager.data_queues.get("rgb")
    tof_scelet_queue = logging_manager.data_queues.get("tof_scelet")
    distraction_queue = logging_manager.data_queues.get("distraction_model_queue")
    eyetracker_queue = logging_manager.data_queues.get("eyetracker")
    silab_queue = logging_manager.data_queues.get("silab")
    rasante_fahrweise_model_queue = logging_manager.data_queues.get("rasante_fahrweise_model")
    shimmer_raw_queue = logging_manager.data_queues.get("shimmer")
    shimmer_hrv_queue = logging_manager.data_queues.get("shimmer_hrv")
    gaze_queue = logging_manager.data_queues.get("gaze_distribution_model")

    latest_sensor_data = {
        "rgb_frame": None,
        "tof_frame": None,
        "pose_frame": None,
        "eyetracker": None,
        "silab": None,
        "rgb_frame2": None,
        "tof_scelet": None,
        "distraction": None,
        "shimmer": None,
        "gaze": None,
        "fahrweise": None,
        "shimmer_raw": None
    }

    last_emit_time = 0.0

    while not stop_event.is_set():
        has_update = False

        # RGB Data-Queue
        if rgb_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                rgb_frame = rgb_queue.get_nowait()
                encoded = encode_rgb_stream_frame(rgb_frame)
                if encoded is not None:
                    latest_sensor_data["rgb_frame"] = encoded
            except Empty:
                pass
            except Exception as e:
                printlog(f"RGB encode error: {e}", "debug")

        # SILAB Data-Queue
        if silab_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                silab = silab_queue.get_nowait()
                if silab is not None:
                    latest_sensor_data["silab"] = silab
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading Silab-Queue error: {e}", "debug")

        # Rasante-Fahrweise-Model Data-Queue
        if rasante_fahrweise_model_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                fahrweise = rasante_fahrweise_model_queue.get_nowait()
                if fahrweise is not None:
                    latest_sensor_data["fahrweise"] = fahrweise
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading fahrweise-Queue error: {e}", "debug")

        # TOF depth
        # if tof_queue is not None:
        #     try:
                  # Holt den tatsächlichen Eintrag aus der Queue
        #         depth = tof_queue.get_nowait()
        #         sensor_data["tof_frame"] = encode_depth_to_jpg(depth)
        #     except Empty:
        #         pass
        #     except Exception as e:
        #         printlog(f"TOF queue error: {e}", "debug")

        # TOF - Data-Queue
        if tof_scelet_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                depth = tof_scelet_queue.get_nowait()
                encoded = encode_depth_to_jpg(depth)
                if encoded is not None:
                    latest_sensor_data["tof_scelet"] = encoded
            except Empty:
                pass
            except Exception as e:
                printlog(f"TOF queue error: {e}", "debug")

        # RGB2 - Data-Queue + pose_queue (optional)
        if rgb2_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                rgb_frame2 = rgb2_queue.get_nowait()
                encoded = encode_rgb_stream_frame(rgb_frame2)
                if encoded is not None:
                    latest_sensor_data["rgb_frame2"] = encoded
            except Empty:
                pass
            except Exception as e:
                printlog(f"Pose queue error: {e}", "debug")

        # Distraction-Model Data-Queue
        if distraction_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                d = distraction_queue.get_nowait()
                if d is not None:
                    latest_sensor_data["distraction"] = d
            except Empty:
                pass
            except Exception as e:
                printlog(f"distraction queue error: {e}", "debug")

        # Shimmer raw packet data
        if shimmer_raw_queue is not None:
            try:
                raw_data = shimmer_raw_queue.get_nowait()
                if raw_data is not None:
                    latest_sensor_data["shimmer_raw"] = raw_data
                    has_update = True
            except Empty:
                pass
            except Exception as e:
                printlog(f"Shimmer raw queue error: {e}", "debug")

        # Shimmer Data-Queue
        if shimmer_hrv_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                data = shimmer_hrv_queue.get_nowait()
                if data is not None:
                    latest_sensor_data["shimmer"] = data
            except Empty:
                pass
            except Exception as e:
                printlog(f"HRV queue error: {e}", "debug")

        # Gaze-Distribution Data-Queue
        if gaze_queue is not None:
            try:
                # Holt den tatsächlichen Eintrag aus der Queue
                gaze_frame = gaze_queue.get_nowait()
                ok, buffer2 = cv2.imencode(".jpg", gaze_frame)
                if ok:
                    latest_sensor_data["gaze"] = base64.b64encode(buffer2.tobytes()).decode()
            except Empty:
                pass
            except Exception as e:
                printlog(f"gaze queue error: {e}", "debug")

        now = time.monotonic()
        if (now - last_emit_time) >= EMIT_INTERVAL:
            socketio.emit("sensor_update", latest_sensor_data)
            last_emit_time = now

        time.sleep(0.01)


def _mock_image_b64(label: str, t: float, width: int = 640, height: int = 360) -> str:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (25, 28, 34)

    # Animated status bar for visual feedback that the stream is live.
    bar_x = int(((math.sin(t * 1.8) + 1) * 0.5) * (width - 120))
    cv2.rectangle(frame, (bar_x, height - 40), (bar_x + 100, height - 20), (60, 180, 220), -1)

    cv2.putText(frame, f"{label} MOCK", (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (20, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 220, 255), 2)

    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        return ""
    return base64.b64encode(buffer.tobytes()).decode()


def mock_sensor_stream(stop_event):
    start_t = time.time()
    while not stop_event.is_set() and is_running and logging_manager is None:
        t = time.time() - start_t
        speed_ms = max(0.0, 18.0 + 8.0 * math.sin(t * 0.6))
        bpm = float(74 + 7 * math.sin(t * 0.42))
        ibi = float(60000.0 / max(bpm, 1.0))
        rmssd = float(32 + 9 * math.sin(t * 0.5 + 0.5))
        sdnn = float(45 + 10 * math.sin(t * 0.35))
        sdsd = float(max(5.0, rmssd * 0.78 + 2.5 * math.sin(t * 0.33)))
        pnn20 = float(max(0.0, min(1.0, 0.34 + 0.16 * math.sin(t * 0.27))))
        pnn50 = float(max(0.0, min(1.0, 0.18 + 0.11 * math.sin(t * 0.21 + 0.3))))
        hr_mad = float(max(10.0, 45 + 16 * math.sin(t * 0.29 + 0.4)))
        sd1 = float(max(1.0, rmssd / math.sqrt(2.0)))
        sd2 = float(max(sd1 + 1.0, sdnn * 1.18))
        sd1_sd2 = float(sd1 / max(sd2, 1e-6))
        s_val = float(math.pi * sd1 * sd2)
        breathing_rate = float(max(0.08, min(0.45, 0.22 + 0.05 * math.sin(t * 0.18))))
        
        sensor_data = {
            "rgb_frame": _mock_image_b64("RGB Front", t),
            "tof_frame": None,
            "pose_frame": None,
            "eyetracker": {
                "x": float(0.5 + 0.18 * math.sin(t * 0.85)),
                "y": float(0.5 + 0.16 * math.sin(t * 1.1 + 0.45)),
                "pupil_left": float(3.2 + 0.35 * math.sin(t * 0.52)),
                "pupil_right": float(3.15 + 0.32 * math.sin(t * 0.56 + 0.2)),
            },
            "silab": {
                "speed": float(speed_ms),
                "steering": float(6.5 * math.sin(t * 0.9)),
                "acc_pedal": float(max(0.0, 0.6 + 0.35 * math.sin(t * 1.1))),
                "brake_pedal": float(max(0.0, 0.3 * math.sin(t * 1.7 - 1.0))),
            },
            "rgb_frame2": _mock_image_b64("RGB Back", t + 1.0),
            "tof_scelet": _mock_image_b64("TOF", t + 2.0),
            "distraction": {
                "label": int((math.sin(t * 0.7) > 0.35)),
                "prob_distracted": float((math.sin(t * 0.7) + 1.0) * 0.5),
                "n_frames": int(30 + 20 * abs(math.sin(t * 0.4))),
            },
            "shimmer": {
                "bpm": bpm,
                "heart_rate": bpm,
                "ibi": ibi,
                "sdnn": sdnn,
                "sdsd": sdsd,
                "rmssd": rmssd,
                "pnn20": pnn20,
                "pnn50": pnn50,
                "hr_mad": hr_mad,
                "sd1": sd1,
                "sd2": sd2,
                "s": s_val,
                "sd1/sd2": sd1_sd2,
                "breathingrate": breathing_rate,
                "sdnn": float(45 + 10 * math.sin(t * 0.35)),
                "rmssd": float(32 + 9 * math.sin(t * 0.5 + 0.5)),
            },
            "gaze": None,
            "fahrweise": {
                "prediction": "fast" if speed_ms > 21 else "normal",
                "confidence": float(0.65 + 0.25 * abs(math.sin(t * 0.8))),
            },
        }
        socketio.emit("sensor_update", sensor_data)
        time.sleep(0.1)

# Main entry-point for application
if __name__ == '__main__':
    load_config()
    socketio.run(app, port=port, debug=False, allow_unsafe_werkzeug=True)
