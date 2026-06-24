import numpy as np
import matplotlib.pyplot as plt
import numpy as np
import yaml
from typing import List, Union
from typing import Dict
import numpy.typing as npt
import transform_coord as tc

def find_pixel_on_frame(frame: np.ndarray):
    """
    Öffnet ein interaktives Fenster. Erkennt automatisch, ob es sich um 
    ein Tiefenbild (2D) oder ein RGB-Bild (3D) handelt.
    """
    display_frame = frame.copy()
    
    # Prüfen, ob es ein RGB-Bild ist (3 Dimensionen: Höhe, Breite, Kanäle)
    is_rgb = (display_frame.ndim == 3 and display_frame.shape[2] == 3)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    if is_rgb:
        # --- LOGIK FÜR RGB-BILDER ---
        # Falls das RGB-Bild im Integer-Format (0-255) vorliegt, für imshow so belassen.
        # Wichtig: Keine Maskierung mit NaN und keine vmin/vmax Einschränkung!
        img = ax.imshow(display_frame)
        ax.set_title("RGB-Modus: Bewege die Maus über das Zielobjekt\nUnten rechts stehen (x, y) und [R, G, B]")
        
        # Bei RGB macht eine Tiefen-Farblegende keinen Sinn, deshalb lassen wir sie weg
    else:
        # --- LOGIK FÜR TIEFENBILDER (wie vorher) ---
        display_frame = display_frame.astype(np.float64)
        display_frame[np.isnan(display_frame)] = np.nan
        display_frame[display_frame <= 0.1] = np.nan
        
        img = ax.imshow(display_frame, cmap='jet', vmin=1.0, vmax=3.0)
        
        cbar = fig.colorbar(img, ax=ax)
        cbar.set_label('Tiefe in Metern', rotation=270, labelpad=15)
        
        ax.set_title("Tiefen-Modus: Bewege die Maus über das Zielobjekt\nUnten rechts stehen (x, y) und [Tiefe in m]")

    ax.set_xlabel("Pixel Spalte (u / x)")
    ax.set_ylabel("Pixel Zeile (v / y)")
    
    plt.show(block=True)

if __name__ == "__main__":
    # =========================================================================
    # KONFIGURATION 
    # =========================================================================
    # Erlaubte Modi: "TOF" oder "RGB"
    MODUS = "RGB"
    
    # Pfad zur Kalibrierungsdatei
    yaml_pfad = r"C:\Users\SILAB.SILAB1\Documents\fahrsimulator_24-01-2026_1\utils\Koordinaten_Tranformation\master_extrinsics_to_global.yaml"
    
    if MODUS == "TOF":
        # Konfiguration für den Time-of-Flight Sensor
        bild_pfad = r"C:\Users\SILAB.SILAB1\Documents\fahrsimulator_24-01-2026_1\utils\Koordinaten_Tranformation\tof_frame_1782120911.1058943.npy"
        matrix_name = "tof"
        
        # Abgelesene Pixelkoordinaten aus dem ToF-Bild
        u_ziel = 254.3
        v_ziel = 352.7
        
    elif MODUS == "RGB":
        # Konfiguration für die RGB-Kamera
        bild_pfad = r"C:\Users\SILAB.SILAB1\Documents\fahrsimulator_24-01-2026_1\utils\Koordinaten_Tranformation\rgb_camera_0_frame_1782133141.080288.npy"
        matrix_name = "cam0"  # "cam0" für Front, "cam1" für Rechts (laut yaml)
        
        # Abgelesene Pixelkoordinaten aus dem RGB-Bild
        u_ziel = 290
        v_ziel = 217
        
        # Da RGB-Kameras keine echte Tiefe messen, definieren wir hier 
        # die konstante Test-Entfernung in Metern für das Zielobjekt
        KUENSTLICHE_TIEFE_M = 0.76
        
    # =========================================================================
    # AUTOMATISCHER ABLAUF (Ab hier musst du nichts mehr ändern)
    # =========================================================================
    print(f"=== STARTE VALIDIERUNG IM MODUS: {MODUS} (Matrix: '{matrix_name}') ===")
    
    # 1. Matrizen und Bild-Array laden
    all_matrices = tc.lade_sensor_matrizen(yaml_pfad)
    test_array: np.ndarray = np.load(bild_pfad)
    height, width = test_array.shape[:2]
    
    # Kaufmännisch runden für den späteren Array-Zugriff
    u_idx = int(round(u_ziel))
    v_idx = int(round(v_ziel))
    
    # 2. Visuelle Inspektion (Fenster öffnen)
    if MODUS == "TOF":
        # ToF-Rohwerte in Meter skalieren für die korrekte Anzeige im GUI
        test_array_m = tc.scale_raw_depth_to_meters(test_array, max_raw_value=65535.0, range_width_m=3.0, start_offset_m=1.0)
        print("Öffne ToF-Tiefenbild... (Werte im Fenster entsprechen echten Metern)")
        find_pixel_on_frame(test_array_m)
    else:
        # RGB-Bild direkt anzeigen (keine Skalierung nötig)
        print("Öffne RGB-Bild...")
        find_pixel_on_frame(test_array)
        
    print("\nFenster geschlossen. Starte 3D-Transformation...")

    # 3. Tiefenkarte für die Transformation vorbereiten
    if MODUS == "TOF":
        # Für TOF nutzen wir das echt gemessene und skalierte Tiefenbild
        tiefen_frame_fuer_trans = test_array_m
        
        # Exakte Tiefe an dem gewünschten Pixel aus dem skalierten Array auslesen
        z_m = test_array_m[v_idx, u_idx]
        print(f"Gemessene Sensor-Tiefe an Pixel ({u_ziel}, {v_ziel}): {z_m:.4f} m")
        
        if np.isnan(z_m) or z_m <= 0.1:
            print("[WARNUNG] Der gewählte Pixel liefert keinen gültigen Tiefenwert (NaN/0)!")
    else:
        # Für RGB erzeugen wir die künstliche, flache Tiefenebene
        tiefen_frame_fuer_trans = tc.create_constant_depth_frame(test_array, constant_depth_m=KUENSTLICHE_TIEFE_M)
        z_m = KUENSTLICHE_TIEFE_M
        print(f"Verwende künstlich gesetzte Objekt-Tiefe: {z_m:.4f} m")

    # 4. In den globalen Raum transformieren
    punkte_3d_global = tc.transform_depth_frame_to_global_space_keep_structure(
        depth_frame=tiefen_frame_fuer_trans,
        matrix_name=matrix_name,
        matrix_dict=all_matrices
    )
    
    # 5. Struktur wieder an die Bildkoordinaten anpassen
    globale_punkt_matrix = punkte_3d_global.reshape(height, width, 3)
    
    # 6. Sicherheitscheck und finale Ausgabe der globalen Weltkoordinaten
    if 0 <= v_idx < height and 0 <= u_idx < width:
        globale_koordinate = globale_punkt_matrix[v_idx, u_idx]
        
        print(f"\n[ERGEBNIS] Globale Koordinate für Pixel ({u_ziel}, {v_ziel}):")
        print(f" -> Genutzte Sensor-Tiefe (Z_lokal)  : {z_m:.4f} m")
        print(f" -> Globale X-Koordinate (links)      : {globale_koordinate[0]:.4f} m")
        print(f" -> Globale Y-Koordinate (nach vorne) : {globale_koordinate[1]:.4f} m")
        print(f" -> Globale Z-Koordinate (Höhe)       : {globale_koordinate[2]:.4f} m")
        print(f" -> Vollständiger Vektor [X, Y, Z]    : {globale_koordinate}")
    else:
        print(f"\n[FEHLER] Der Pixel ({u_idx}, {v_idx}) liegt außerhalb der Bildgrenzen!")
        print(f"Für diesen Sensor ({width}x{height}) sind nur Indizes bis u={width-1} und v={height-1} erlaubt.") 