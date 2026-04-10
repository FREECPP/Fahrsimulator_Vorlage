import cv2
import numpy as np
from pathlib import Path
from get_calib_depth_image import get_snap

def draw_eclipse(): 
    """
    Interactively calibrates the position of a steering wheel using depth data.

    This function loads a depth image, visualizes it, and allows the user to interactively select the center
    and points on the ring of a steering wheel. The calibration values (center, radius, and ellipse parameters)
    are calculated and saved to a file. The annotated image is also saved.

    Steps:
    1. Load the depth image from a .npy file.
    2. Visualize the depth image with optional color mapping.
    3. Allow the user to click on the center and ring points of the steering wheel.
    4. Calculate calibration values and save them to a file.
    5. Save the annotated image with the calibration points and ellipse.
    """
    BASE = Path(__file__).resolve().parents[2]   
    output_path = BASE / "driverDistractionModel/model_calibration/params/depth_calib_frame.npy"
    
    depth = np.load(output_path) 
        
    h_d, w_d = depth.shape
    print("Depth shape:", depth.shape)

    MAX_DIST = 2000.0 

    depth_clip = np.clip(depth.astype(np.float32), 0, MAX_DIST)
    depth_u8 = (depth_clip / MAX_DIST * 255).astype(np.uint8)   
    depth_vis = cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO)
    depth_vis = cv2.rotate(depth_vis, cv2.ROTATE_180)

    center = None
    points_on_ring = []

    def on_mouse(event, x, y):
        """
        Mouse callback function for selecting the center and ring points of the steering wheel.

        Args:
            event: The mouse event (e.g., left button click).
            x (int): The x-coordinate of the mouse click.
            y (int): The y-coordinate of the mouse click.
        """
        nonlocal center, points_on_ring

        if event == cv2.EVENT_LBUTTONDOWN:
            if not (0 <= x < w_d and 0 <= y < h_d):
                print(f"Klick außerhalb des Depth-Bildes: ({x},{y})")
                return

            d_val = depth[y, x]

            if center is None:
                center = (x, y)
                print(f"Center gesetzt bei: {center}, depth={d_val}")
            else:
                points_on_ring.append((x, y))
                print(f"Ringpunkt: {(x, y)}, depth={d_val}")

    cv2.namedWindow("depth_calib")
    cv2.setMouseCallback("depth_calib", on_mouse)

    print("Anleitung:")
    print("- 1x auf die Mitte des Lenkrads klicken (grüner Punkt).")
    print("- Mehrfach auf den Ring klicken (rote Punkte).")
    print("- Mit 'q' beenden, dann werden die Kalibrierwerte berechnet.\n")

    while True:
        vis = depth_vis.copy()

        if center is not None:
            cv2.circle(vis, center, 5, (0, 255, 0), -1)

        for p in points_on_ring:
            cv2.circle(vis, p, 3, (0, 0, 255), -1)

        cv2.imshow("depth_calib", vis)
        BASE = Path(__file__).resolve().parents[2]  
        output_path = BASE / "driverDistractionModel/model_calibration/params/depth_calib_points.jpg"
    

        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.imwrite(str(output_path), vis)
            print("Bild mit eingezeichneten Punkten gespeichert: depth_calib_points.jpg")
            break

    cv2.destroyAllWindows()

    if center is not None and points_on_ring:
        cx, cy = center

        rs = [np.sqrt((x - cx)**2 + (y - cy)**2) for (x, y) in points_on_ring]
        r_mean = float(np.mean(rs))

        depth_center = float(depth[cy, cx])

        print("\n==== KALIBRIERTE WERTE AUS DEPTH ====")
        print(f"WHEEL_CX = {cx}")
        print(f"WHEEL_CY = {cy}")
        print(f"WHEEL_R  = {r_mean:.2f}")
        print(f"WHEEL_DEPTH_MEAN = {depth_center:.2f}")

        if len(points_on_ring) >= 5:
            pts = np.array(points_on_ring, dtype=np.int32)
            ellipse = cv2.fitEllipse(pts)  

            vis_final = depth_vis.copy()

            cv2.circle(vis_final, (cx, cy), 5, (0, 255, 0), -1)

            cv2.circle(vis_final, (cx, cy), int(r_mean), (255, 255, 255), 1)

            cv2.ellipse(vis_final, ellipse, (255, 255, 0), 2)

            print("\nEllipse-Parameter (fitEllipse):")
            print(f" center = {ellipse[0]}")
            print(f" axes   = {ellipse[1]}  # (major, minor)")
            print(f" angle  = {ellipse[2]}  # Grad")

            valid_depths = [depth[y, x] for (x, y) in points_on_ring if depth[y, x] > 0]
            if valid_depths:
                mean_depth_ellipse = float(np.mean(valid_depths))
            else:
                mean_depth_ellipse = 0.0

            output_path = BASE / "driverDistractionModel/model_calibration/params/calibration_params.txt"

            with open(str(output_path), "w") as f:
                f.write("==== KALIBRIERTE WERTE AUS DEPTH ====\n")
                f.write(f"WHEEL_CX = {cx}\n")
                f.write(f"WHEEL_CY = {cy}\n")
                f.write(f"WHEEL_R  = {r_mean:.2f}\n")
                f.write(f"WHEEL_DEPTH_MEAN = {depth_center:.2f}\n")
                

                if len(points_on_ring) >= 5:
                    f.write("\nEllipse-Parameter (fitEllipse):\n")
                    f.write(f" center = {ellipse[0]}\n")
                    f.write(f" axes   = {ellipse[1]}  # (major, minor)\n")
                    f.write(f" angle  = {ellipse[2]}  # Grad\n")
                
                f.write(f"\nMEAN_DEPTH_ELLIPSE = {mean_depth_ellipse:.2f}\n")

            print("Kalibrierwerte in calibration_params.txt gespeichert.")

            cv2.imshow("depth_calib_result", vis_final)
            output_path = BASE / "driverDistractionModel/model_calibration/params/depth_calib_ellipse.jpg"
    
            cv2.imwrite(str(output_path), vis_final)
            print("Ergebnisfenster 'depth_calib_result' geöffnet. Beliebige Taste zum Schließen.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        else:
            print("Zu wenige Ringpunkte für Ellipse (min. 5 benötigt).")
    else:
        print("Nicht genug Punkte: Center oder Ringpunkte fehlen.")


if __name__ == "__main__":
    status = get_snap()
    if status: 
        draw_eclipse()
