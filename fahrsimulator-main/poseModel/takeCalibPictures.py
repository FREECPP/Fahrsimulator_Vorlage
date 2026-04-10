import cv2
import numpy as np
import sys
import os
from pathlib import Path

# --- KONFIGURATION ---
CONF = {
    "SDK_PATH": r"C:\Analog Devices\TOF_Evaluation_ADTF3175D-Rel5.0.0\bin",
    "RGB_INDEX": 0,
    "TOF_IP": "ip:10.43.0.1",
    "TOF_CONFIG_FILE": "config_adsd3500_adsd3030.json",
    "TOF_MODE": "lr-qnative",
    # Speicherort relativ zum Skript
    "BASE_DIR": Path(__file__).parent / "bilder"
}

# --- SDK PFAD SETUP ---
if not Path(CONF["SDK_PATH"]).exists():
    print(f"KRITISCHER FEHLER: SDK-Pfad nicht gefunden: {CONF['SDK_PATH']}")
    sys.exit(1)

# Umgebungsvariablen setzen
os.environ["PATH"] = CONF["SDK_PATH"] + os.pathsep + os.environ.get("PATH", "")
sys.path.insert(0, CONF["SDK_PATH"])

try:
    import aditofpython as tof
except ImportError:
    print("FEHLER: 'aditofpython' konnte nicht geladen werden. Pfad prüfen!")
    sys.exit(1)


def connect_cameras():
    print("\n--- Initialisiere Kameras ---")

    # 1. RGB Kamera
    print(f"1. Verbinde RGB (Index {CONF['RGB_INDEX']})...")
    cam_rgb = cv2.VideoCapture(CONF["RGB_INDEX"], cv2.CAP_DSHOW)
    if not cam_rgb.isOpened():
        print("   FEHLER: RGB Kamera konnte nicht geöffnet werden.")
        cam_rgb = None
    else:
        cam_rgb.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam_rgb.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("   OK: RGB verbunden.")

    # 2. ToF Kamera
    print(f"2. Verbinde ToF ({CONF['TOF_IP']})...")
    cam_tof = None
    current_working_dir = os.getcwd()

    try:
        os.chdir(CONF["SDK_PATH"])

        system = tof.System()
        cameras = []
        status = system.getCameraList(cameras, CONF["TOF_IP"])

        if not status or not cameras:
            print(f"   FEHLER: Keine ToF Kamera unter {CONF['TOF_IP']} gefunden.")
        else:
            cam_tof = cameras[0]
            config_rel_path = "./config/" + CONF["TOF_CONFIG_FILE"]

            print(f"   Lade Config: {config_rel_path}")
            cam_tof.initialize(config_rel_path)

            cam_tof.setFrameType(CONF["TOF_MODE"])
            cam_tof.start()
            print("   OK: ToF Kamera gestartet.")

    except Exception as e:
        print(f"   EXCEPTION bei ToF Start: {e}")
        cam_tof = None
    finally:
        os.chdir(current_working_dir)

    return cam_rgb, cam_tof


def draw_text(img, text, pos=(20, 40), color=(0, 255, 0)):
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)


def main():
    base_dir = CONF["BASE_DIR"]
    dirs = {
        "rgb": base_dir / "rgb_intrinsics",
        "depth": base_dir / "depth_intrinsics",
        "stereo": base_dir / "stereo"
    }

    # Ordner erstellen
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    cam_rgb, cam_tof = connect_cameras()

    if cam_rgb is None and cam_tof is None:
        print("ABBRUCH: Keine Kameras verbunden.")
        return

    # ToF Frame Objekt
    tof_frame = tof.Frame()

    # Phasen-Steuerung
    phases = ["rgb", "depth", "stereo"]
    phase_idx = 0
    img_counters = {"rgb": 0, "depth": 0, "stereo": 0}

    print("\n--- STEUERUNG ---")
    print(" [s] Bild speichern")
    print(" [n] Nächste Phase (RGB -> Depth -> Stereo)")
    print(" [q] Beenden")

    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)

    try:
        while True:
            current_phase = phases[phase_idx]

            rgb_img = None
            if cam_rgb:
                ret, frame = cam_rgb.read()
                if ret:
                    rgb_img = cv2.rotate(frame, cv2.ROTATE_180)

            if rgb_img is None:
                rgb_img = dummy_img.copy()
                draw_text(rgb_img, "RGB FEHLER", (20, 200), (0, 0, 255))

            #  ToF Frame holen
            ir_img = None
            if cam_tof:
                try:
                    # Request Frame mit Timeout Schutz
                    status_tof = cam_tof.requestFrame(tof_frame)
                    if status_tof:
                        depth_data = np.array(tof_frame.getData("ab"), copy=False)
                        # Normalisieren für Anzeige
                        ir_img = cv2.normalize(depth_data, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                        ir_img = cv2.rotate(ir_img, cv2.ROTATE_180)
                    else:
                        print("Warnung: ToF Frame leer (Status False)")
                except Exception as e:
                    print(f"Fehler beim Frame-Abruf: {e}")

            if ir_img is None:
                ir_img = np.zeros((512, 512), dtype=np.uint8)
                cv2.putText(ir_img, "TOF FEHLER", (50, 256), cv2.FONT_HERSHEY_SIMPLEX, 1, (255), 2)

            # Anzeige Logik
            preview = None
            msg = ""
            sub_msg = ""

            if current_phase == "rgb":
                preview = rgb_img.copy()
                msg = f"PHASE 1: NUR RGB ({img_counters['rgb']} gesp.)"
                sub_msg = "Schachbrett in alle Ecken bewegen!"

            elif current_phase == "depth":
                preview = cv2.cvtColor(ir_img, cv2.COLOR_GRAY2BGR)
                msg = f"PHASE 2: NUR TIEFE ({img_counters['depth']} gesp.)"
                sub_msg = "Nah ran gehen! Ecken fuellen."

            elif current_phase == "stereo":
                # Bilder auf gleiche Höhe skalieren für Side-by-Side
                h = 512
                # RGB skalieren
                scale_rgb = h / rgb_img.shape[0]
                w_rgb = int(rgb_img.shape[1] * scale_rgb)
                rgb_small = cv2.resize(rgb_img, (w_rgb, h))

                # IR skalieren
                scale_ir = h / ir_img.shape[0]
                w_ir = int(ir_img.shape[1] * scale_ir)
                ir_small = cv2.resize(ir_img, (w_ir, h))

                # Zusammenfügen
                ir_color = cv2.cvtColor(ir_small, cv2.COLOR_GRAY2BGR)
                preview = np.hstack((ir_color, rgb_small))

                msg = f"PHASE 3: STEREO ({img_counters['stereo']} gesp.)"
                sub_msg = "Abstand halten. Beide muessen es sehen."

            draw_text(preview, msg, (20, 40), (0, 255, 0))
            draw_text(preview, sub_msg, (20, 80), (0, 255, 255))

            cv2.imshow("Kalibrierungs-Aufnahme", preview)

            #Tastensteuerung
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break

            elif key == ord('n'):
                phase_idx = (phase_idx + 1) % len(phases)
                print(f"\n---> Wechsle zu Phase: {phases[phase_idx].upper()}")

            elif key == ord('s'):
                c = img_counters[current_phase]
                save_path = dirs[current_phase]

                # Nur speichern wenn Bilder gültig (nicht schwarz/fehler)
                valid_rgb = np.any(rgb_img)
                valid_ir = np.any(ir_img)

                if current_phase == "rgb" and valid_rgb:
                    fname = save_path / f"rgb_{c:02d}.png"
                    cv2.imwrite(str(fname), rgb_img)
                    print(f"Gespeichert: {fname.name}")
                    img_counters[current_phase] += 1

                elif current_phase == "depth" and valid_ir:
                    fname = save_path / f"ir_{c:02d}.png"

                    cv2.imwrite(str(fname), ir_img)
                    print(f"Gespeichert: {fname.name}")
                    img_counters[current_phase] += 1

                elif current_phase == "stereo" and valid_rgb and valid_ir:
                    fname_rgb = save_path / f"rgb_{c:02d}.png"
                    fname_ir = save_path / f"ir_{c:02d}.png"
                    cv2.imwrite(str(fname_rgb), rgb_img)
                    cv2.imwrite(str(fname_ir), ir_img)
                    print(f"Gespeichert: Paar {c}")
                    img_counters[current_phase] += 1
                else:
                    print("FEHLER: Kann Bild nicht speichern (Kamera-Fehler?)")

    except KeyboardInterrupt:
        print("Abbruch durch Nutzer.")
    finally:
        print("Beende Kameras...")
        if cam_rgb: cam_rgb.release()
        if cam_tof: cam_tof.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()