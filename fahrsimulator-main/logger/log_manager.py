from pathlib import Path

from multiprocessing import (
    Process,
    Event,
    Queue
)

from logger import (
    EyetrackerLogger,
    SilabLogger,
    TiefenCamLogger
)

from logger.ShimmerLogger import ShimmerLogger
from logger.rgb_camera_logger import RgbCameraLogger

from models.rasante_fahrweise.rasante_fahrweise_prediction_model import (
    RasanteFahrweisePredictionModel
)

from poseModel.merged_skelettDirekt_neuSegmentierung import (
    DepthPoseClass
)

from driverDistractionModel.model_train.distractionModel import (
    distractionModel
)

from utils.tof_csv_writer import FileWriter
from utils.merge_logs import merge_logs

import time

global are_sensors_started
are_sensors_started = False

# ===== Log Manager =====
class LogManager:

    UDP_IP_SILAB = "127.0.0.1"

    UDP_PORT_SILAB = 6666

    SILAB_RECORDING_TIMEOUT = 2.0

    distraction_model_path = (
        Path(__file__).resolve().parents[1]
        / "driverDistractionModel"
        / "model"
        / "xgb_distraction_model.json"
    )

    def __init__(
        self,
        tof_video: bool = False,
        data_queues: dict[str, Queue] | None = None,
        directory: str | None = None,
        participant_name: str | None = None,
        project_name: str | None = None,
        timestamp=None
    ):

        participant_name = (
            participant_name
            or "unknown_participant"
        )

        project_name = (
            project_name
            or "unknown_participant"
        )

        self.run_log_dir = (
            Path(directory)
            / project_name
            / participant_name
            / "logfiles"
            / timestamp
        )

        self.run_log_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self._process: list[Process] = []

        self.stop_event = Event()

        self.data_queues = data_queues

        self.tof_video = tof_video

        # ===== Logger =====
        self.loggers = [

            (
                EyetrackerLogger,

                dict(
                    file=self.run_log_dir / "eyetracker_log.csv",
                    device_index=0,
                    as_dictionary=True,
                ),

                {
                    "eyetracker":
                        self.data_queues["eyetracker"],
                }
            ),

            (
                SilabLogger,

                dict(
                    file=self.run_log_dir / "silab_log.csv",
                    udp_ip=self.UDP_IP_SILAB,
                    udp_port=self.UDP_PORT_SILAB,
                    timeout=self.SILAB_RECORDING_TIMEOUT
                ),

                {
                    "silab":
                        self.data_queues["silab"],

                    "silab_model":
                        self.data_queues["silab_model"],
                }
            ),

            (
                ShimmerLogger,

                dict(
                    file=self.run_log_dir / "shimmer_log.csv",
                ),

                {
                    "shimmer":
                        self.data_queues["shimmer"],
                }
            ),

            (
                TiefenCamLogger,

                dict(
                    config="config_adsd3500_adsd3030.json",
                    mode="lr-qnative",
                    output_dir=self.run_log_dir,
                    fps=30.0,
                    ip="ip:10.43.0.1",
                    log_path=self.run_log_dir / "tof_camera_log.csv",
                    raw_pixel_csv=False,
                    csv_compressed=False,
                ),

                {
                    "tof":
                        self.data_queues["tof"],

                    "pose_queue":
                        self.data_queues["pose_queue"]
                }
            ),

            (
                RgbCameraLogger,

                dict(
                    camera_index=0,
                    file=self.run_log_dir / "rgb_camera1.csv",
                    directory=self.run_log_dir,
                    live_view=False,
                    back_camera=False,
                ),

                {
                    "rgb_frame":
                        self.data_queues["rgb"],
                }
            ),

            (
                RgbCameraLogger,

                dict(
                    camera_index=1,
                    file=self.run_log_dir / "rgb_camera2.csv",
                    directory=self.run_log_dir,
                    live_view=False,
                    back_camera=True,
                ),

                {
                    "rgb_frame2":
                        self.data_queues["rgb2"],
                }
            )
        ]

        # ===== Models =====
        self.models = [

            (
                DepthPoseClass,

                dict(),

                {
                    "pose_queue":
                        self.data_queues["pose_queue"],

                    "tof_scelet":
                        self.data_queues["tof_scelet"],

                    "scelet_dict":
                        self.data_queues["scelet_dict"],
                }
            ),

            (
                distractionModel,

                dict(
                    model_path=str(
                        self.distraction_model_path
                    ),

                    window_s=3.0,
                    min_frames=3,
                    timestamp_col="timestamp",
                ),

                {
                    "scelet_dict":
                        self.data_queues["scelet_dict"],

                    "distraction_model_queue":
                        self.data_queues[
                            "distraction_model_queue"
                        ],
                }
            ),

            (
                RasanteFahrweisePredictionModel,

                dict(),

                {
                    "silab_model":
                        self.data_queues["silab_model"],

                    "rasante_fahrweise_model":
                        self.data_queues[
                            "rasante_fahrweise_model"
                        ],
                }
            ),

            # (
            #     RealTimeGaze3D,
            #     dict(),
            #     {
            #         "eyetracker":
            #             self.data_queues["eyetracker"],
            #
            #         "rgb_frame2":
            #             self.data_queues["rgb2"],
            #
            #         "gaze_distribution_model":
            #             self.data_queues[
            #                 "gaze_distribution_model"
            #             ],
            #     }
            # )
        ]

        # ===== Writer =====
        self.file_writer = [

            (
                FileWriter,

                dict(
                    outdir=str(self.run_log_dir),
                    filename="tof_frame_data.npy",
                ),

                {
                    "tof":
                        self.data_queues["tof"],
                }
            ),
        ]

    # ===== Start Sensors =====
    def start_sensors(self) -> None:

        print("Starting sensors...")

        for logger in self.loggers:

            print(
                f"Starting "
                f"{logger.__class__.__name__}..."
            )

            try:
                logger.start_sensor()

            except Exception as e:

                print(
                    f"Error starting "
                    f"{logger.__class__.__name__}: {e}"
                )

        print("Sensors started.")

        return None

    # ===== Start Models =====
    def start_models(self) -> None:

        print("Starting models...")

        for model in self.models:

            print(
                f"Starting "
                f"{model.__class__.__name__})..."
            )

            try:
                model.run()

            except Exception as e:

                print(
                    f"Error starting "
                    f"{model.__class__.__name__}: {e}"
                )

        print("Models started.")

        return None

    # ===== Start Logging =====
    def start_logging_async(self):

        print(f"Log directory: {self.run_log_dir}")

        is_running = self._start_logger_processes()

        return is_running

    def _start_logger_processes(self) -> bool:

        print("\nStarting logger processes...")

        self.stop_event = Event()

        self._process = []

        for writer_cls, kwargs, queues in self.file_writer:

            p = Process(
                target=run_writer_process,

                args=(
                    writer_cls,
                    kwargs,
                    self.stop_event,
                    queues
                )
            )

            p.start()

            self._process.append(p)

            print(
                f"{writer_cls.__name__} "
                f"process started"
            )

        for logger_cls, kwargs, queues in self.loggers:

            p = Process(
                target=run_logger_process,

                args=(
                    logger_cls,
                    kwargs,
                    self.stop_event,
                    queues
                )
            )

            p.start()

            self._process.append(p)

            print(
                f"{logger_cls.__name__} "
                f"process started"
            )

        for model_cls, kwargs, queues in self.models:

            p = Process(
                target=run_model_process,

                args=(
                    model_cls,
                    kwargs,
                    self.stop_event,
                    queues
                )
            )

            p.start()

            self._process.append(p)

            print(
                f"{model_cls.__name__} "
                f"process started"
            )

        return True

    def start_sepperat_logging_async(self):
        self.log_event.set()
        #is_running = self._start_sepperat_logger_processes()
        #return is_running
        return True

    def _start_sepperat_logger_processes(self) -> bool:

        self.stop_event = Event()
        self._process = []
        for writer_cls, kwargs, queues in self.file_writer:
            p = Process(target=run_writer_process, args=(writer_cls, kwargs, self.stop_event, queues))
            p.start()
            self._process.append(p)
            print(f"{writer_cls.__name__} process started")

        for logger_cls, kwargs, queues in self.loggers:
            p = Process(target=run_logger_sepperat_process, args=(logger_cls, kwargs, self.stop_event, queues))
            p.start()
            self._process.append(p)
            print(f"{logger_cls.__name__} process started")

        for model_cls, kwargs, queues in self.models:
            p = Process(target=run_model_process, args=(model_cls, kwargs, self.stop_event, queues))
            p.start()
            self._process.append(p)
            print(f"{model_cls.__name__} process started")

        return True

    def start_sensors_async(self):
        are_sensors_connected = self._sensor_start_processes()
        return are_sensors_connected

    def _sensor_start_processes(self) -> bool:
        self.stop_event = Event()
        self.log_event = Event()
        self._process = []

        for writer_cls, kwargs, queues in self.file_writer:
            p = Process(target=run_writer_process, args=(writer_cls, kwargs, self.stop_event, queues))
            p.start()
            self._process.append(p)
            print(f"{writer_cls.__name__} process started")

        for logger_cls, kwargs, queues in self.loggers:
            p = Process(target=run_sensor_start_process, args=(logger_cls, kwargs,self.stop_event, self.log_event, queues))
            p.start()
            self._process.append(p)
            print(f"{logger_cls.__name__} sensor-start-process started")

        for model_cls, kwargs, queues in self.models:
            p = Process(target=run_model_process, args=(model_cls, kwargs, self.stop_event, queues))
            p.start()
            self._process.append(p)
            print(f"{model_cls.__name__} process started")

        return True

    # ===== Stop Logging =====
    def _stop_logger_processes(self) -> None:

        print("\nStopping logger processes...")

        self.stop_event.set()

        for p in self._process:

            p.join(timeout=10)

            if p.is_alive():

                print(
                    f"Prozess {p.name} "
                    f"hat nicht rechtzeitig beendet "
                    f"– wird zwangsbeendet."
                )

                p.terminate()

                p.join(timeout=3)

        self._process.clear()

        print("\nAll loggers stopped.")

        try:

            print("\nFühre Sensor-Logs zusammen...")

            combined = merge_logs(
                self.run_log_dir
            )

            output_path = (
                self.run_log_dir
                / "combined_log.csv"
            )

            combined.to_csv(
                output_path,
                index=False
            )

            print(
                f"Combined log gespeichert: "
                f"{output_path}"
            )

        except Exception as e:

            print(
                f"Fehler beim Zusammenführen "
                f"der Logs: {e}"
            )

# ===== Logger Process =====
def run_logger_process(
    logger_cls,
    kwargs,
    stop_event,
    queues
):

    if isinstance(queues, dict):
        qdict = queues

    else:
        qdict = {"default": queues}

    logger = logger_cls(
        **kwargs,
        queues=qdict
    )

    logger.start_sensor()

    logger.start_logging(stop_event)

    logger.stop_logging()


def run_sensor_start_process(logger_cls, kwargs, stop_event, log_event, queues):
    if isinstance(queues, dict):
        qdict = queues
    else:
        qdict = {"default": queues}

    logger = logger_cls(**kwargs, queues=qdict)
    logger.start_sensor(stop_event, log_event)
    logger.start_logging(stop_event, log_event)
    logger.stop_logging()

def run_logger_sepperat_process(logger_cls, kwargs,stop_event, queues):
    if isinstance(queues, dict):
        qdict = queues
    else:
        qdict = {"default": queues}

    logger = logger_cls(**kwargs, queues=qdict)

    logger.start_logging(stop_event)

    logger.stop_logging()
# ===== Model Process =====
def run_model_process(
    model_cls,
    kwargs,
    stop_event,
    queues
):

    if isinstance(queues, dict):
        qdict = queues

    else:
        qdict = {"default": queues}

    model = model_cls(
        **kwargs,
        queues=qdict
    )

    model.run(stop_event)
    model.run(stop_event)

# ===== Writer Process =====
def run_writer_process(
    writer_cls,
    kwargs,
    stop_event,
    queues
):

    if isinstance(queues, dict):
        qdict = queues

    else:
        qdict = {"default": queues}

    writer = writer_cls(
        **kwargs,
        queues=qdict
    )

    writer.run(stop_event)