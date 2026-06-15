import numpy as np
import yaml
from typing import List, Union



def lade_sensor_matrizen(yaml_pfad):
    """
    Liest die Extrinsik-YAML-Datei ein und speichert die Transformationsmatrizen
    (T_global_from_sensor) der Sensoren in einem Dictionary.
    """
    matrizen_dict = {}
    
    try:
        with open(yaml_pfad, 'r') as file:
            # YAML-Datei parsen
            daten = yaml.safe_load(file)
            
        # Überprüfen, ob die Sektion 'sensors' existiert
        if 'sensors' in daten:
            for sensor_name, sensor_info in daten['sensors'].items():
                # Die 4x4 Matrix herausholen
                matrix_liste = sensor_info.get('T_global_from_sensor')
                
                if matrix_liste:
                    # Als NumPy-Array abspeichern für spätere Berechnungen
                    matrizen_dict[sensor_name] = np.array(matrix_liste)
                else:
                    print(f"Warnung: Keine 'T_global_from_sensor' für {sensor_name} gefunden.")
        else:
            print("Fehler: Keine 'sensors'-Sektion in der YAML-Datei gefunden.")
            
    except FileNotFoundError:
        print(f"Fehler: Die Datei unter '{yaml_pfad}' wurde nicht gefunden.")
    except yaml.YAMLError as exc:
        print(f"Fehler beim Parsen der YAML-Datei: {exc}")
        
    return matrizen_dict

def calc_local_coordinates_from_pixels(coord: List[Union[int, float]], cx: float = 523.9361572265625, cy: float = 526.0283813476562, fx: float = 775.8900756835938, fy: float = 775.9134521484375) -> List[float]:
    """
    coord:
        Pixel: 
        u = horizontale (von links nach rechts)
        v = vertikale (von oben nach unten)
        Tiefe in Metern: 
        z

    Brennweite: 
    fx, fy

    Koordinaten optischer Mittelpunkt: 
    cx, cy
    """
    u = coord[0]
    v= coord[1]
    z = coord[2]

    x_local = ((u-cx)*z)/fx
    y_local = ((v-cy)*z)/fy 

    coord_local = [x_local, y_local, z]
    return coord_local

def transform_lokal_coordinate_in_global_space(coord, matrix_name, matrix_dict):
    """
    Wandelt die Koordinaten anhand der Wandlungsmatrix vom lokalen System in das globale System. Wichtig die Koordinaten müssen in Meter
    angegeben werden.  
    """
    # Prüfen, ob der gesuchte Sensor im Dictionary existiert
    if matrix_name not in matrix_dict:
        print(f"Fehler: Sensor '{matrix_name}' ist nicht in den geladenen Matrizen vorhanden.")
        return None  # Oder wirf einen Fehler (raise ValueError)

    relevant_matrix = matrix_dict[matrix_name]

    # wandle array in numpy-array
    coord_array = np.array(coord)

    # array homogenisieren (1 anfügen) damit es mit Matrize verrechnet werden kann      
    coord_array = np.append(coord_array, 1.0)

    # Matrixmultiplikation durführen
    p_global_homo = relevant_matrix @ coord_array

    # von vierstelligem Array zu dreistelligem zurückwandeln
    p_global = p_global_homo[:3]

    return p_global 
        



# Der Main-Block: Wird NUR ausgeführt, wenn du diese Datei direkt startest
if __name__ == "__main__":
    pfad = 'fahrsimulator-main/utils/master_extrinsics_to_global.yaml'
    
    # 1. EINMALIG am Anfang des Programms die YAML laden
    all_matrices = lade_sensor_matrizen(pfad)
    
    # 2. Beliebig oft Punkte transformieren, ohne die Datei neu zu öffnen
    lokaler_punkt = [0.1, 0.2, 0.5] # Koordianten müssen in Meter angegeben werden

    # Angenommen Pixelwerte sind (2,4, 666) => Der Wertebereich der Pixeltiefe ist 0 - 4778 und dieser Bereich deckt einen Bereich von 3m
    # ab, startend ab 1m von der Kamera entfernt
    pixel_coord = [2,4,666]

    # tiefe in Meter umrechnen
    pixel_coord[2] = pixel_coord[2] * (3 / 4778)
    print(f"pixel_coord: {pixel_coord}")

    # Pixelkoordinaten in Metrische umwandeln
    local_coord_from_px = calc_local_coordinates_from_pixels(pixel_coord[0], pixel_coord[1], pixel_coord[2])     
    print(f"local_coord_from_px: {local_coord_from_px}")

    globaler_punkt = transform_lokal_coordinate_in_global_space(
        coord=local_coord_from_px, 
        matrix_name='tof', 
        matrix_dict=all_matrices
    )
    
    print("Globaler Punkt:", globaler_punkt)