from utils.app_logging_utils import printlog
from flask import Flask, Response, request, render_template, jsonify
from flask_socketio import SocketIO
import threading
import cv2
import base64
from logger.log_manager import LogManager
#from logger.frame_processor import Processor, EyetrackerProcessor, SilabDataProcessor
from flask_blueprints.verzeichnis import verzeichnis_bp
import configparser
import os
from datetime import datetime
from multiprocessing import Queue
import numpy as np
import time
from queue import Empty

# ==================================================================================
# Initialising Webapp Data
# ==================================================================================
app = Flask(__name__)
app.register_blueprint(verzeichnis_bp, url_prefix="/")
socketio = SocketIO(app, cors_allowed_origins="*")
port = int(os.getenv('PORT', 9999))
host = "0.0.0.0"

# ==================================================================================
# Initialising Logger Data
# ==================================================================================
logging_manager = None
BASE_DIR = None
is_running = False

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
    "rasante_fahrweise_model": Queue(maxsize=1),
    "shimmer_hrv": Queue(maxsize=1),
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
        #port = config.get('General', 'PORT')
        host = str(config.get('General', 'HOST'))
    except Exception as e:
        printlog(f"Data from 'config.ini' couldn't be read. Versichern Sie sich, dass PORT und HOST unter [General] existieren. {e}", "error")

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
    print("stopped")
    return render_template("index.html")


@app.route("/dashboard")
def show_dashboard():
    return render_template("dashboard.html")

# ==================================================================================
# Dashboard.html
# ==================================================================================
@socketio.on('connect')
def handle_connect():
    printlog("Client connected")

# Start-Button handling on 'dashboard.html'
@socketio.on('start_recording')
def handle_start_recording():
    printlog(message="Starte Log-Manager", debug_lvl="info", std_print=True)
    from flask_blueprints.verzeichnis import project_path
    printlog(message=str(project_path), debug_lvl="info", std_print=True)
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    global logging_manager
    logging_manager = LogManager(directory=project_path, data_queues=data_queues, timestamp=now)
    
    global is_running
    is_running = logging_manager.start_logging_async()

    socketio.emit('is_running', is_running)
    #threading.Thread(target=stream_all_sensors, daemon=True).start()
    threading.Thread(target=read_queue, args=(logging_manager, ), daemon=True).start()

# Stop-Button handling on 'dashboard.html'
@socketio.on('stop_recording')
def handle_stop_recording():
    global logging_manager
    if logging_manager:
        logging_manager._stop_logger_processes()
        #logging_manager.stop_logging()
        logging_manager = None
    is_running = False
    socketio.emit('is_running', is_running)


# Helper function to encode depth-data to jpeg for live preview
def encode_depth_to_jpg(depth: np.ndarray) -> str | None:
    if depth is None:
        return None
    depth = np.nan_to_num(depth)

    #depth_norm = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    #depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)

    ok, buffer = cv2.imencode(".jpg", depth)
    if not ok:
        return None
    return base64.b64encode(buffer).decode()

# Main function to send data per 'socket.emit()' to the dashboard.html
def read_queue(logging_manager):
    tof_queue = logging_manager.data_queues.get("tof")
    rgb2_queue = logging_manager.data_queues.get("rgb2")
    rgb_queue = logging_manager.data_queues.get("rgb")
    tof_scelet_queue = logging_manager.data_queues.get("tof_scelet")
    distraction_queue = logging_manager.data_queues.get("distraction_model_queue")
    eyetracker_queue = logging_manager.data_queues.get("eyetracker")
    silab_queue = logging_manager.data_queues.get("silab")
    rasante_fahrweise_model_queue = logging_manager.data_queues.get("rasante_fahrweise_model")
    shimmer_queue = logging_manager.data_queues.get("shimmer_hrv")
    gaze_queue = logging_manager.data_queues.get("gaze_distribution_model")

    while logging_manager:
        sensor_data = {
            "rgb_frame": None,
            "tof_frame": None,
            "pose_frame": None,   # optional debug
            "eyetracker": None,
            "silab": None, 
            "rgb_frame2": None,  # optional second RGB
            "tof_scelet": None,
            "distraction": None,
            "shimmer": None,
            "gaze": None,
            "fahrweise": None,
        }

        # RGB Data-Queue
        if rgb_queue is not None:
            try:
                rgb_frame = rgb_queue.get_nowait()
                ok, buffer = cv2.imencode(".jpg", rgb_frame)
                if ok:
                    sensor_data["rgb_frame"] = base64.b64encode(buffer.tobytes()).decode()
            except Empty:
                pass
            except Exception as e:
                printlog(f"RGB encode error: {e}", "debug")

        # SILAB Data-Queue
        if silab_queue is not None:
            try:
                silab = silab_queue.get_nowait()
                if silab is not None:
                    sensor_data["silab"] = silab
                    #print(sensor_data["silab"])
            except Empty:
                pass
            except Exception as e:
                printlog(f"Reading Silab-Queue error: {e}", "debug")

        # Rasante-Fahrweise-Model Data-Queue
        if rasante_fahrweise_model_queue is not None:
            try:
                fahrweise = rasante_fahrweise_model_queue.get_nowait()
                if fahrweise is not None:
                    sensor_data["fahrweise"] = fahrweise
                    #print(f"fahrweise: {sensor_data['fahrweise']}")
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
                sensor_data["tof_scelet"] = encode_depth_to_jpg(depth)
            except Empty:
                pass
            except Exception as e:
                printlog(f"TOF queue error: {e}", "debug")

        # RGB2 - Data-Queue + pose_queue (optional)
        if rgb2_queue is not None:
            try:
                rgb_frame2 = rgb2_queue.get_nowait()
                ok, buffer2 = cv2.imencode(".jpg", rgb_frame2)
                # sensor_data["rgb_frame2"] = encode_depth_to_jpg(pose_depth)
                sensor_data["rgb_frame2"] = base64.b64encode(buffer2.tobytes()).decode()
            except Empty:
                pass
            except Exception as e:
                printlog(f"Pose queue error: {e}", "debug")

        # Distraction-Model Data-Queue
        if distraction_queue is not None:
            try:
                d = distraction_queue.get_nowait()
                sensor_data["distraction"] = d
            except Empty:
                pass
            except Exception as e:
                printlog(f"distraction queue error: {e}", "debug")

        # Shimmer Data-Queue
        if shimmer_queue is not None:
            try:
                data = shimmer_queue.get_nowait()
                sensor_data["shimmer"] = data
            except Empty:
                pass
            except Exception as e:
                printlog(f"HRV queue error: {e}", "debug")

        # Gaze-Distribution Data-Queue
        if gaze_queue is not None:
            try:
                gaze_frame = gaze_queue.get_nowait()
                ok, buffer2 = cv2.imencode(".jpg", gaze_frame)
                sensor_data["gaze"] = base64.b64encode(buffer2.tobytes()).decode()
            except Empty:
                pass
            except Exception as e:
                printlog(f"gaze queue error: {e}", "debug")

        socketio.emit("sensor_update", sensor_data)
        time.sleep(0.02)  # ~50 Hz updates

# Main entry-point for application
if __name__ == '__main__':
    load_config()
    socketio.run(app, port=port, debug=False, allow_unsafe_werkzeug=True)
