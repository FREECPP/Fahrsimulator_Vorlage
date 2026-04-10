import cv2
import numpy as np
import sys
from pathlib import Path

# --- KONFIGURATION ---
CONF = {
    "BASE_DIR": Path(__file__).parent / "bilder",
    "BOARD_SIZE": (9, 6)  # Innere Ecken (Breite, Höhe)
}


class CalibrationVisualizer:
    def __init__(self):
        self.base_dir = CONF["BASE_DIR"]
        self.board_size = CONF["BOARD_SIZE"]

        if not self.base_dir.exists():
            print(f"FEHLER: Basis-Ordner nicht gefunden: {self.base_dir}")
            sys.exit(1)

    def _convert_ir_to_8bit(self, ir_image_raw: np.ndarray) -> np.ndarray:
        """Konvertiert 16-bit oder Farbbild in 8-bit Graustufen"""
        if ir_image_raw.dtype == 'uint16':
            return cv2.convertScaleAbs(ir_image_raw, alpha=(255.0 / 65535.0))
        if len(ir_image_raw.shape) == 3:
            return cv2.cvtColor(ir_image_raw, cv2.COLOR_BGR2GRAY)
        return ir_image_raw

    def _find_and_draw(self, img, title_prefix=""):
        """Hilfsfunktion: Findet Ecken und zeichnet sie ein"""
        gray = self._convert_ir_to_8bit(img)

        # Ecken finden
        ret, corners = cv2.findChessboardCorners(gray, self.board_size, None)

        # Bild für Anzeige vorbereiten (in Farbe konvertieren, falls Graustufe)
        if len(img.shape) == 2:
            display_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            display_img = img.copy()

        # Zeichnen
        if ret:
            cv2.drawChessboardCorners(display_img, self.board_size, corners, ret)
            status_text = "OK"
            color = (0, 255, 0)  # Grün
        else:
            status_text = "NICHT GEFUNDEN"
            color = (0, 0, 255)  # Rot

        # Text Overlay
        cv2.putText(display_img, f"{title_prefix}: {status_text}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return display_img, ret

    def check_folder_mono(self, folder_name, file_pattern):
        """Prüft Einzelbild-Ordner (RGB oder Depth)"""
        target_dir = self.base_dir / folder_name
        files = sorted(target_dir.glob(file_pattern))

        print(f"\n--- Prüfe Ordner: {folder_name} ({len(files)} Bilder) ---")
        if not files:
            print("  (Keine Bilder gefunden)")
            return

        for f_path in files:
            print(f"  Prüfe: {f_path.name}")

            # Laden (IR als Unchanged laden wegen 16bit)
            img = cv2.imread(str(f_path), cv2.IMREAD_UNCHANGED)
            if img is None: continue

            # Zeichnen
            vis_img, found = self._find_and_draw(img, title_prefix=f_path.name)

            cv2.imshow("Ecken-Checker (Mono)", vis_img)

            key = cv2.waitKey(0)  # Warten auf Tastendruck
            if key == ord('q'):
                print("Abbruch durch Benutzer.")
                return

    def check_folder_stereo(self):
        """Prüft den Stereo-Ordner (Paare)"""
        target_dir = self.base_dir / "stereo"
        rgb_files = sorted(target_dir.glob("rgb_*.png"))
        ir_files = sorted(target_dir.glob("ir_*.png"))

        print(f"\n--- Prüfe Ordner: stereo ({len(rgb_files)} Paare) ---")

        if len(rgb_files) != len(ir_files):
            print("WARNUNG: Ungleiche Anzahl an RGB und IR Bildern!")

        for f_rgb, f_ir in zip(rgb_files, ir_files):
            print(f"  Prüfe Paar: {f_rgb.name} & {f_ir.name}")

            img_rgb = cv2.imread(str(f_rgb))
            img_ir = cv2.imread(str(f_ir), cv2.IMREAD_UNCHANGED)

            # Ecken suchen
            vis_rgb, found_rgb = self._find_and_draw(img_rgb, "RGB")
            vis_ir, found_ir = self._find_and_draw(img_ir, "Depth")

            # Skalierung für Side-by-Side
            h = vis_rgb.shape[0]  # Zielhöhe

            # IR skalieren auf RGB Höhe
            scale = h / vis_ir.shape[0]
            w_new = int(vis_ir.shape[1] * scale)
            vis_ir_resized = cv2.resize(vis_ir, (w_new, h))

            # Zusammenfügen
            combined = np.hstack((vis_ir_resized, vis_rgb))

            # Info Text global
            overall_status = "GUT" if (found_rgb and found_ir) else "SCHLECHT"
            col = (0, 255, 0) if (found_rgb and found_ir) else (0, 0, 255)
            cv2.putText(combined, f"Status: {overall_status}", (20, h - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, col, 2)

            cv2.imshow("Ecken-Checker (Stereo)", combined)

            key = cv2.waitKey(0)
            if key == ord('q'):
                return

    def run(self):
        print("Welchen Ordner möchtest du prüfen?")
        print(" 1 - RGB Intrinsics (rgb_intrinsics)")
        print(" 2 - Depth Intrinsics (depth_intrinsics)")
        print(" 3 - Stereo Paare (stereo)")
        print(" a - Alle nacheinander")

        choice = input("Auswahl: ").strip().lower()
        cv2.destroyAllWindows()

        if choice == '1' or choice == 'a':
            self.check_folder_mono("rgb_intrinsics", "rgb_*.png")

        if choice == '2' or choice == 'a':
            self.check_folder_mono("depth_intrinsics", "ir_*.png")  # Oder *.png falls anderes Format

        if choice == '3' or choice == 'a':
            self.check_folder_stereo()

        cv2.destroyAllWindows()
        print("Fertig.")


if __name__ == "__main__":
    viz = CalibrationVisualizer()
    viz.run()