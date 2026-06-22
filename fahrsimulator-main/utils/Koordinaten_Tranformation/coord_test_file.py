import numpy as np
import matplotlib.pyplot as plt
import numpy as np
import yaml
from typing import List, Union
from typing import Dict
import numpy.typing as npt
import transform_coord as tc

def find_pixel_on_depth_frame(depth_frame_meters: np.ndarray):
    """
    Öffnet ein interaktives Fenster des bereits in Metern skalierten Tiefenbildes.
    """
    display_frame = depth_frame_meters.copy()
    
    # Da das Array bereits in Metern übergeben wird, maskieren wir nur noch ungültige Werte
    display_frame[np.isnan(display_frame)] = np.nan
    display_frame[display_frame <= 0.1] = np.nan
    
    fig, ax = plt.subplots(figsize=(10, 8))
    img = ax.imshow(display_frame, cmap='jet', vmin=1.0, vmax=3.0) # Farbskala fest auf 1-3m fixiert
    
    cbar = fig.colorbar(img, ax=ax)
    cbar.set_label('Tiefe in Metern', rotation=270, labelpad=15)
    
    ax.set_title("Bewege die Maus über dein Zielobjekt\nUnten rechts stehen die Pixelkoordinaten (x, y)")
    ax.set_xlabel("Pixel Spalte (u / x)")
    ax.set_ylabel("Pixel Zeile (v / y)")
    
    plt.show(block=True) 

if __name__ == "__main__":
        all_matrices = tc.lade_sensor_matrizen("fahrsimulator-main/utils/Koordinaten_Tranformation/master_extrinsics_to_global.yaml")
        test_array: npt.NDArray = np.load("fahrsimulator-main/utils/Koordinaten_Tranformation/tof_frame_1782120911.1058943.npy")
        test_array_m = tc.scale_raw_depth_to_meters(test_array, max_raw_value=65535.0, range_width_m=3.0, start_offset_m=1.0)
        find_pixel_on_depth_frame(test_array_m)

        # -------------------------------------------------------------------------
        # NACH DEM SCHLIESSEN DES FENSTERS:
        # -------------------------------------------------------------------------
    
        # Trage hier die Koordinaten ein, die du im Fenster abgelesen hast:
        u_gelesen = 254.3
        v_gelesen = 352.7
    
        # Wir runden die Koordinaten, um den exakten Wert aus dem berechneten Meter-Array zu ziehen
        u_idx = int(round(u_gelesen))
        v_idx = int(round(v_gelesen))
    
        # Tiefe direkt aus dem konvertierten Array auslesen
        z_m = test_array_m[v_idx, u_idx]
    
        print(f"\n--- VALIDIERUNG FÜR PIXEL ({u_gelesen}, {v_gelesen}) ---")
        print(f"Ausgelesene Tiefe an diesem Pixel: {z_m:.4f} Meter")
    
        if np.isnan(z_m) or z_m <= 0.1:
            print("Fehler: Du hast einen ungültigen Pixel (Wert 0 / NaN) ausgewählt!")
        else:
            # 4. Lokale 3D-Koordinaten berechnen
            coords_local = tc.calc_local_coordinates_from_pixels([u_gelesen, v_gelesen, z_m])
            print(f"Lokale 3D-Koordinate (Kamerasystem) [X, Y, Z]:\n {coords_local}")
        
            # 5. Globale 3D-Koordinaten berechnen
            coords_global = tc.transform_lokal_coordinate_in_global_space(coords_local, "tof", all_matrices)
            print(f"Globale 3D-Koordinate (Weltsystem) [X, Y, Z]:\n {coords_global}")