from utils.app_logging_utils import printlog
from flask import Flask, Response, request, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS

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

socketio = SocketIO(app, cors_allowed_origins="*")

port = int(os.getenv('PORT', 9999))
host = "0.0.0.0"

# ===== Database =====
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

DB_PATH = "app.db"
if app.debug:
    with app.app_context():
        db.create_all()

# ===== Runtime =====
logging_manager = None
BASE_DIR = None
is_running = False

stream_thread = None
stream_stop_event = threading.Event()

current_participant_id = None

# ===== Queues =====
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

# ===== Config =====
def load_config():
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.ini not found: {config_path}")

    config.read(config_path)

    global port, host

    try:
        host = str(config.get('General', 'HOST'))

    except Exception as e:
        printlog(
            f"Data from 'config.ini' couldn't be read. {e}",
            "error"
        )

    try:
        base_dir = config.get('General', 'BASE_DIR')
        os.makedirs(base_dir, exist_ok=True)

    except Exception as e:
        printlog(f"BASE_DIR invalid: {e}", "error")

# ===== Routes =====
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def show_dashboard():
    return render_template("dashboard.html")

# ===== Socket =====
@socketio.on('connect')
def handle_connect():
    server_ip = get_server_ip()
    printlog(f"Client connected to server {server_ip}:{port}")


def get_server_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]

    except OSError:
        ip = "127.0.0.1"

    finally:
        s.close()

    return ip

# ===== Start Recording =====
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

    printlog(
        message="Starte Log-Manager",
        debug_lvl="info",
        std_print=True
    )

    from controllers.projectController import project_path

    printlog(
        message=str(project_path),
        debug_lvl="info",
        std_print=True
    )

    try:
        from logger.log_manager import LogManager

        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        logging_manager = LogManager(
            directory=project_path,
            data_queues=data_queues,
            timestamp=now,
            participant_name=participant["name"],
        )

        is_running = logging_manager.start_logging_async()

        socketio.emit('is_running', is_running)

        stream_stop_event.clear()

        stream_thread = threading.Thread(
            target=read_queue,
            args=(logging_manager, stream_stop_event),
            daemon=True
        )

        stream_thread.start()

    except Exception as e:
        logging_manager = None
        is_running = True

        printlog(
            f"Fallback to mock sensor stream: {e}",
            "warning"
        )

        socketio.emit('is_running', True)

        stream_stop_event.clear()

        stream_thread = threading.Thread(
            target=mock_sensor_stream,
            args=(stream_stop_event,),
            daemon=True
        )

        stream_thread.start()

# ===== Stop Recording =====
@socketio.on('stop_recording')
def handle_stop_recording():
    global logging_manager
    global is_running
    global stream_thread
    global current_participant_id

    stream_stop_event.set()

    if stream_thread and stream_thread.is_alive():
        stream_thread.join(timeout=1.0)

    stream_thread = None

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
        logging_manager = None

    is_running = False

    socketio.emit('is_running', is_running)

# ===== Other Events =====
@socketio.on('start_sensor')
def handle_start_sensor():
    pass


@socketio.on('start_logging')
def handle_start_logging():
    pass


@socketio.on('start_simulation')
def handle_start_simulation():
    start_silab_prozess()


@socketio.on('start_pc')
def handle_start_pc():
    wake_on_lan("BC:0F:F3:C4:C4:70")

# ===== Image Helpers =====
def encode_depth_to_jpg(depth: np.ndarray) -> Optional[str]:
    if depth is None:
        return None

    depth = np.nan_to_num(depth)

    ok, buffer = cv2.imencode(".jpg", depth)

    if not ok:
        return None

    return base64.b64encode(buffer).decode()


def encode_rgb_stream_frame(rgb_frame) -> Optional[str]:
    if rgb_frame is None:
        return None

    if isinstance(rgb_frame, str):
        return rgb_frame

    if isinstance(rgb_frame, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(rgb_frame)).decode()

    ok, buffer = cv2.imencode(".jpg", rgb_frame)

    if not ok:
        return None

    return base64.b64encode(buffer.tobytes()).decode()

# ===== Sensor Stream =====
def read_queue(logging_manager, stop_event):
    tof_queue = logging_manager.data_queues.get("tof")
    rgb2_queue = logging_manager.data_queues.get("rgb2")
    rgb_queue = logging_manager.data_queues.get("rgb")

    latest_sensor_data = {
        "rgb_frame": None,
        "tof_frame": None,
    }

    last_emit_time = 0.0

    while not stop_event.is_set():
        has_update = False

        if rgb_queue is not None:
            try:
                rgb_frame = rgb_queue.get_nowait()

                encoded = encode_rgb_stream_frame(rgb_frame)

                if encoded is not None:
                    latest_sensor_data["rgb_frame"] = encoded
                    has_update = True

            except Empty:
                pass

            except Exception as e:
                printlog(f"RGB encode error: {e}", "debug")

        now = time.monotonic()

        if has_update or (now - last_emit_time) >= 0.25:
            socketio.emit("sensor_update", latest_sensor_data)
            last_emit_time = now

        time.sleep(0.01)

# ===== Mock Stream =====
def _mock_image_b64(
    label: str,
    t: float,
    width: int = 640,
    height: int = 360
) -> str:
    frame = np.zeros((height, width, 3), dtype=np.uint8)

    frame[:] = (25, 28, 34)

    bar_x = int(
        ((math.sin(t * 1.8) + 1) * 0.5)
        * (width - 120)
    )

    cv2.rectangle(
        frame,
        (bar_x, height - 40),
        (bar_x + 100, height - 20),
        (60, 180, 220),
        -1
    )

    cv2.putText(
        frame,
        f"{label} MOCK",
        (20, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2
    )

    ok, buffer = cv2.imencode(".jpg", frame)

    if not ok:
        return ""

    return base64.b64encode(buffer.tobytes()).decode()


def mock_sensor_stream(stop_event):
    start_t = time.time()

    while (
        not stop_event.is_set()
        and is_running
        and logging_manager is None
    ):
        t = time.time() - start_t

        sensor_data = {
            "rgb_frame": _mock_image_b64("RGB Front", t),
            "tof_frame": None,
        }

        socketio.emit("sensor_update", sensor_data)

        time.sleep(0.1)

# ===== Main =====
if __name__ == '__main__':
    load_config()

    socketio.run(
        app,
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )
