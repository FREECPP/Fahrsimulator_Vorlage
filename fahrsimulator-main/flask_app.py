import os
import logging

# Google glog / ADI ToF SDK
os.environ["GLOG_minloglevel"] = "2"
os.environ["GLOG_logtostderr"] = "0"

# TensorFlow / MediaPipe / TFLite
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# libwebsocket (falls unterstützt)
os.environ["LWS_LOG_LEVEL"] = "0"

# Flask / Werkzeug logs reduzieren
logging.getLogger('werkzeug').setLevel(logging.ERROR)

from utils.app_logging_utils import printlog
from flask import Flask, Response, request, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

import logging

from datetime import datetime
from multiprocessing import Queue
from typing import Optional
from queue import Empty

# Imports für Starten der Simulation und des externen Rechners
from utils.WakeOnLan import wake_on_lan
from utils.sim_start import start_silab_prozess

# from flask_blueprints.verzeichnis import verzeichnis_bp
from controllers.projectController import verzeichnis_bp
from controllers.layoutController import layout_bp
from extensions import db
from dbModels.dashboardLayoutDB import dashboardLayout
from dbModels.projectAndParticipantsDB import Participant
from extensions import db

import socket
import threading
import cv2
import base64
import configparser
import os
import numpy as np
import time
import math

# ===== App =====
app = Flask(__name__)

CORS(app, supports_credentials=True)

app.register_blueprint(verzeichnis_bp, url_prefix="/")
app.register_blueprint(layout_bp)

socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False)

port = int(os.getenv('PORT', 9999))
host = "0.0.0.0"

# ==================================================================================
# Initialising Database
# ==================================================================================

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
DB_PATH = "app.db"

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
are_sensors_running = False
stream_thread = None
stream_stop_event = threading.Event()
EMIT_INTERVAL = 0.05

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
    "gaze_distribution_model": Queue(maxsize=1),

}

# ==================================================================================
# Helper function for loading 'config.ini' Data
# ==================================================================================
def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found: {config_path}")
    config.read(config_path)
    global port, host
    try:
        # port = config.get('General', 'PORT')
        host = str(config.get('General', 'HOST'))
    except Exception as e:
        printlog(
            f"Data from 'config.ini' couldn't be read. Versichern Sie sich, dass PORT und HOST unter [General] existieren. {e}",
            "error")

    try:
        base_dir = config.get('General', 'BASE_DIR')
        os.makedirs(base_dir, exist_ok=True)
    except Exception as e:
        printlog(f"Be sure 'config.ini', BASE_DIR under [General] exists and the path is valid. {e}", "error")


# ==================================================================================
# Index.html
# ==================================================================================
@app.route("/")
def index():
    return render_template("index.html")


# Nicht mehr vorhanden
@app.route("/stop_logging", methods=["POST"])
def stop_logging():
    print("logging stopped")
    return render_template("index.html")



@app.route("/dashboard")
def show_dashboard():
    return render_template("dashboard.html")


# ==================================================================================
# Dashboard.html
# ==================================================================================
@socketio.on('connect')
def handle_connect():
    server_ip = get_server_ip()
    #printlog(f"Client connected to server {server_ip}:{port}")


def get_server_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # keine echte Verbindung nötig
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# Start-Button handling on 'dashboard.html'
@socketio.on('start_recording')
def handle_start_recording(data):
    global logging_manager
    global is_running
    global stream_thread
    global current_participant_id

    participant = data.get("participant")
    project = data.get("project")

    if not participant:
        printlog("Kein Participant erhalten", "error")
        return

    participant_id = participant.get("id")
    participant_name = participant.get("name")
    current_participant_id = participant_id
    participant_db = db.session.get(Participant, participant_id)

    now = datetime.utcnow()

    participant_db.run_started_at = now
    participant_db.run_ended_at = None
    participant_db.run_duration_seconds = None

    db.session.commit()

    if is_running:
        socketio.emit('is_running', True)
        return

    #printlog(message="Starte Log-Manager", debug_lvl="info", std_print=True)
    from controllers.projectController import project_path
    printlog(message=str(project_path), debug_lvl="info", std_print=True)

    try:
        from logger.log_manager import LogManager  # Lazy-import to support preview mode without sensors
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging_manager = LogManager(directory=project_path, data_queues=data_queues, timestamp=now, participant_name = participant_name, project_name = project)
        is_running = logging_manager.start_logging_async()
        socketio.emit('is_running', is_running)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=read_queue, args=(logging_manager, stream_stop_event), daemon=True)
        stream_thread.start()
    except Exception as e:
        # If hardware/SDK dependencies are unavailable, run mock stream for UI preview.
        logging_manager = None
        is_running = True
        printlog(f"Fallback to mock sensor stream: {e}", "warning")
        socketio.emit('is_running', True)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=mock_sensor_stream, args=(stream_stop_event,), daemon=True)
        stream_thread.start()


# Stop-Button handling on 'dashboard.html'
@socketio.on('stop_recording')
def handle_stop_recording():
    global logging_manager
    global is_running
    global stream_thread
    global current_participant_id

    if current_participant_id:
        participant_db = db.session.get(
            Participant,
            current_participant_id
        )

        if participant_db and participant_db.run_started_at:
            participant_db.run_ended_at = datetime.utcnow()

            duration = (
                participant_db.run_ended_at
                - participant_db.run_started_at
            )

            participant_db.run_duration_seconds = int(
                duration.total_seconds()
            )

            db.session.commit()

    if logging_manager:
        logging_manager._stop_logger_processes()
        # logging_manager.stop_logging()

    stream_stop_event.set()
    if stream_thread and stream_thread.is_alive():
        stream_thread.join(timeout=1.0)
    stream_thread = None
    logging_manager = None
    is_running = False
    socketio.emit('is_running', is_running)

@socketio.on('start_sensor')
def handle_start_sensor(data):
    global logging_manager, are_sensors_running
    global current_participant_id

    participant = data.get("participant")
    project = data.get("project")

    if not participant:
        printlog("Kein Participant erhalten", "error")
        return

    participant_id = participant.get("id")
    participant_name = participant.get("name")
    current_participant_id = participant_id
    participant_db = db.session.get(Participant, participant_id)

    now = datetime.utcnow()

    participant_db.run_started_at = now
    participant_db.run_ended_at = None
    participant_db.run_duration_seconds = None

    db.session.commit()

    if are_sensors_running:
        print("Sensors already running")
        return

    print("Starte Sensoren sepperat")
    from controllers.projectController import project_path
    try:
        from logger.log_manager import LogManager  # Lazy-import to support preview mode without sensors
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging_manager = LogManager(directory=project_path, data_queues=data_queues, timestamp=now, participant_name = participant_name, project_name = project)
        print("Logging Manager wurde erstellt")
        are_sensors_running = logging_manager.start_sensors_async()
        socketio.emit('is_running', are_sensors_running)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=read_queue, args=(logging_manager, stream_stop_event), daemon=True)
        stream_thread.start()

        if are_sensors_running == True:
            print("Sensoren wurden sepperat gestartet")
        else:
            print("Sensoren wurden nicht sepperat gestartet - are_sensors_running = False")

    except Exception as e:
        # If hardware/SDK dependencies are unavailable, run mock stream for UI preview.
        printlog(f"Sensoren könnten nicht gestartet werden: {e}", "warning")


@socketio.on('start_logging')
def handle_start_logging(data):
    global logging_manager, is_running, stream_thread
    if logging_manager is None:
        print("Fehler: logging manager ist noch None daher kann start_sepperat_logging_async nicht angewendet werden")
    try:
        logging_manager.start_sepperat_logging_async()
    except Exception as e:
        print(f"Fehler beim Starten des sepperaten Loggings: {e}")
    """
    global current_participant_id

    participant = data.get("participant")
    project = data.get("project")

    if not participant:
        printlog("Kein Participant erhalten", "error")
        return

    participant_id = participant.get("id")
    participant_name = participant.get("name")
    current_participant_id = participant_id
    participant_db = db.session.get(Participant, participant_id)

    now = datetime.utcnow()

    participant_db.run_started_at = now
    participant_db.run_ended_at = None
    participant_db.run_duration_seconds = None

    db.session.commit()

    if is_running:
        socketio.emit('is_running', True)
        return

    print("Starte Logging sepperat")
    from controllers.projectController import project_path

    try:
        from logger.log_manager import LogManager  # Lazy-import to support preview mode without sensors
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logging_manager = LogManager(directory=project_path, data_queues=data_queues, timestamp=now,
                                     participant_name=participant_name, project_name=project)
        is_running = logging_manager.start_sepperat_logging_async()
        if is_running and are_sensors_running:
            socketio.emit('is_running', is_running)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=read_queue, args=(logging_manager, stream_stop_event), daemon=True)
        stream_thread.start()
    except Exception as e:
        # If hardware/SDK dependencies are unavailable, run mock stream for UI preview.
        logging_manager = None
        is_running = True
        printlog(f"Fallback to mock sensor stream: {e}", "warning")
        socketio.emit('is_running', True)

        stream_stop_event.clear()
        stream_thread = threading.Thread(target=mock_sensor_stream, args=(stream_stop_event,), daemon=True)
        stream_thread.start()
        """

@socketio.on('start_simulation')
def handle_start_simulation():
    start_silab_prozess()

@socketio.on('start_pc')
def handle_start_pc():
    wake_on_lan("BC:0F:F3:C4:C4:70")


# Helper function to encode depth-data to jpeg for live preview
def encode_depth_to_jpg(depth: np.ndarray) -> Optional[bytes]:
    if depth is None:
        return None
    depth = np.nan_to_num(depth)

    # depth_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    # depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

    ok, buffer = cv2.imencode(".jpg", depth)
    if not ok:
        return None
    return buffer.tobytes()


def encode_rgb_stream_frame(rgb_frame) -> Optional[bytes]:
    if rgb_frame is None:
        return None

    if isinstance(rgb_frame, str):
        return base64.b64decode(rgb_frame)

    if isinstance(rgb_frame, (bytes, bytearray, memoryview)):
        return bytes(rgb_frame)

    ok, buffer = cv2.imencode(".jpg", rgb_frame)
    if not ok:
        return None
    return buffer.tobytes()


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
    shimmer_queue = logging_manager.data_queues.get("shimmer")
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
    }

    last_emit_time = 0.0

    # Heartbeat: letzter Zeitpunkt mit Daten pro Sensor (monotonic)
    last_seen = {}
    HEARTBEAT_TIMEOUT = 2.0  # Sek. ohne Daten -> Sensor gilt als "tot"

    while not stop_event.is_set():
        tick = time.monotonic()

        # RGB Data-Queue
        if rgb_queue is not None:
            try:
                rgb_frame = rgb_queue.get_nowait()
                encoded = encode_rgb_stream_frame(rgb_frame)
                if encoded is not None:
                    latest_sensor_data["rgb_frame"] = encoded
                    last_seen["rgb_frame"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"RGB encode error: {e}", "debug")

        # SILAB Data-Queue
        if silab_queue is not None:
            try:
                silab = silab_queue.get_nowait()
                if silab is not None:
                    latest_sensor_data["silab"] = silab
                    last_seen["silab"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading Silab-Queue error: {e}", "debug")

        # Eyetracker Data-Queue
        if eyetracker_queue is not None:
            try:
                eyetracker = eyetracker_queue.get_nowait()
                if eyetracker is not None:
                    latest_sensor_data["eyetracker"] = eyetracker
                    last_seen["eyetracker"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading Eyetracker-Queue error: {e}", "debug")

        # Rasante-Fahrweise-Model Data-Queue
        if rasante_fahrweise_model_queue is not None:
            try:
                fahrweise = rasante_fahrweise_model_queue.get_nowait()
                if fahrweise is not None:
                    latest_sensor_data["fahrweise"] = fahrweise
                    last_seen["fahrweise"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading fahrweise-Queue error: {e}", "debug")

        # TOF depth
        # if tof_queue is not None:
        #     try:
        #         depth = tof_queue.get_nowait()
        #         sensor_data["tof_frame"] = encode_depth_to_jpg(depth)
        #     except Empty:
        #         pass
        #     except Exception as e:
        #         printlog(f"TOF queue error: {e}", "debug")

        # TOF - Data-Queue
        if tof_scelet_queue is not None:
            try:
                depth = tof_scelet_queue.get_nowait()
                encoded = encode_depth_to_jpg(depth)
                if encoded is not None:
                    latest_sensor_data["tof_scelet"] = encoded
                    last_seen["tof_scelet"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"TOF queue error: {e}", "debug")

        # RGB2 - Data-Queue + pose_queue (optional)
        if rgb2_queue is not None:
            try:
                rgb_frame2 = rgb2_queue.get_nowait()
                encoded = encode_rgb_stream_frame(rgb_frame2)
                if encoded is not None:
                    latest_sensor_data["rgb_frame2"] = encoded
                    last_seen["rgb_frame2"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"Pose queue error: {e}", "debug")

        # Distraction-Model Data-Queue
        if distraction_queue is not None:
            try:
                d = distraction_queue.get_nowait()
                if d is not None:
                    latest_sensor_data["distraction"] = d
                    last_seen["distraction"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"distraction queue error: {e}", "debug")

        # Shimmer Data-Queue
        if shimmer_queue is not None:
            try:
                data = shimmer_queue.get_nowait()
                if data is not None:
                    latest_sensor_data["shimmer"] = data
                    last_seen["shimmer"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"Shimmer queue error: {e}", "debug")

        # Gaze-Distribution Data-Queue
        if gaze_queue is not None:
            try:
                gaze_frame = gaze_queue.get_nowait()
                ok, buffer2 = cv2.imencode(".jpg", gaze_frame)
                if ok:
                    latest_sensor_data["gaze"] = base64.b64encode(buffer2.tobytes()).decode()
                    last_seen["gaze"] = tick
            except Empty:
                pass
            except Exception as e:
                printlog(f"gaze queue error: {e}", "debug")

        now = time.monotonic()
        if (now - last_emit_time) >= EMIT_INTERVAL:
            latest_sensor_data["heartbeat"] = {
                key: (now - ts) < HEARTBEAT_TIMEOUT
                for key, ts in last_seen.items()
            }
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
        rmssd = float(32 + 9 * math.sin(t * 0.5 + 0.5))
        sdnn = float(45 + 10 * math.sin(t * 0.35))
        skin_resistance = float(max(800.0, 180000.0 + 25000.0 * math.sin(t * 0.28)))

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
                "heart_rate": bpm,
                "sdnn": sdnn,
                "rmssd": rmssd,
                "skin_resistance": skin_resistance,
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

    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    socketio.run(app, port=port, debug=False, allow_unsafe_werkzeug=True)
