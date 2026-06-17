import numpy as np
import yaml
from typing import List, Union
from typing import Dict
import numpy.typing as npt



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
    Wandelt einen einzelnen Pixel auf einem Frame anhand einer Tiefe durch die Gesetze des Lochkamera-Modells in eine Koordinate des drei-
    dimensionalen Raums.
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
    v = coord[1]
    z = coord[2]

    x_local = ((u-cx)*z)/fx
    y_local = ((v-cy)*z)/fy 

    coord_local = [x_local, y_local, z]
    return coord_local

def transform_lokal_coordinate_in_global_space(coord, matrix_name, matrix_dict):
    """
    Wandelt die Koordinaten anhand der Wandlungsmatrix vom lokalen System in das globale System. Wichtig die Koordinaten müssen in Meter
    angegeben werden.  

    :param coord: dreidimensionale Raumkoordinaten noch nicht homogenisiert
    :param matrix_name: Name der Wandlungsmatrix in der yaml-Datei(Wandlungsmatrix enthält die Matrize um eine lokale Kooridinate in eine 
                        globale Koordinate zu wandeln - basierend auf Position und Rotation des Sensors zum Globalen Ursprung)
    :param matrix_dict: das dictionary mit allen Wandlungsmatrizen
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

def transform_depth_frame_to_global_space_keep_structure(
    depth_frame: npt.NDArray[np.float64], 
    matrix_name: str, 
    matrix_dict: Dict[str, npt.NDArray[np.float64]],
    cx: float = 523.9361572265625, 
    cy: float = 526.0283813476562, 
    fx: float = 775.8900756835938, 
    fy: float = 775.9134521484375
) -> npt.NDArray[np.float64]:
    """
    Transformiert den Frame und behält die exakte Pixel-Reihenfolge bei.
    Ungültige Pixel werden als [NaN, NaN, NaN] markiert.
    
    Rückgabe-Form: (Breite * Höhe, 3) -> z.B. (262144, 3)
    """
    if matrix_name not in matrix_dict:
        print(f"Fehler: Sensor '{matrix_name}' nicht in Matrizen vorhanden.")
        return np.array([])

    T_global_from_sensor = matrix_dict[matrix_name]
    height, width = depth_frame.shape

    # 1. Gitter für ALLE Pixel erstellen (kein Filtern!)
    u, v = np.meshgrid(np.arange(width), np.arange(height))
    
    # Wir flachen das Gitter ab (flatten), damit es zu einer langen Kette wird
    u_flat = u.flatten()
    v_flat = v.flatten()
    z_flat = depth_frame.flatten()

    # 2. Lokale 3D-Koordinaten für ALLE Pixel berechnen
    x_local = ((u_flat - cx) * z_flat) / fx
    y_local = ((v_flat - cy) * z_flat) / fy

    # Stacken zu einer (N, 3) Matrix
    points_local = np.vstack((x_local, y_local, z_flat)).T

    # 3. Homogenisieren für 4x4 Matrix
    ones = np.ones((points_local.shape[0], 1))
    points_local_homo = np.hstack((points_local, ones))

    # 4. Global transformieren
    points_global_homo = points_local_homo @ T_global_from_sensor.T
    points_global = points_global_homo[:, :3]

    # 5. Jetzt machen wir die ungültigen Pixel unschädlich, behalten aber ihre Zeile!
    # Ein Pixel ist ungültig, wenn die ursprüngliche Tiefe <= 0.1 Meter war
    invalid_mask = z_flat <= 0.1
    
    # Setze X, Y, Z dieser Zeilen auf NaN
    points_global[invalid_mask] = np.nan

    return points_global

def scale_raw_depth_to_meters(
    depth_data: Union[npt.NDArray, List[Union[int, float]]],
    max_raw_value: float = 4778.0,
    range_width_m: float = 3.0,
    start_offset_m: float = 1.0
) -> Union[npt.NDArray[np.float64], List[float]]:
    """
    Wandelt rohe Tiefenwerte generisch in Meter um, unter Berücksichtigung 
    von Wertebereich, Werte-Spanne und einem Start-Offset.
    
    :param depth_data: Ein 2D-NumPy-Array (Frame) oder eine Liste [u, v, z_raw]
    :param max_raw_value: Der maximale Sensorwert (z.B. 4778)
    :param range_width_m: Der abgedeckte Bereich in Metern (z.B. 3.0 Meter)
    :param start_offset_m: Die Mindestdistanz, ab der die Kamera misst (z.B. 1.0 Meter)
    """
    # Falls eine einzelne Pixel-Liste [u, v, z_raw] übergeben wird
    if isinstance(depth_data, list) and len(depth_data) == 3:
        u, v, z_raw = depth_data
        # Lineare Skalierung + Offset addieren
        z_m = (z_raw * (range_width_m / max_raw_value)) + start_offset_m
        return [u, v, z_m]
        
    # Falls ein ganzes NumPy-Array (der Frame) übergeben wird
    elif isinstance(depth_data, np.ndarray):
        # Kopie erstellen und in Float wandeln für präzise Division
        frame_m = depth_data.astype(np.float64)
        # Die mathematische Operation wird auf ALLE Pixel gleichzeitig angewendet
        return (frame_m * (range_width_m / max_raw_value)) + start_offset_m
        
    else:
        raise ValueError("Ungültiger Datentyp. Erwartet wird eine Liste [u,v,z] oder ein NumPy-Array.")
    
def create_constant_depth_frame(
    color_frame: npt.NDArray, 
    constant_depth_m: float
) -> npt.NDArray[np.float64]:
    """
    Geeignet für RGB-Frames
    Erstellt eine künstliche Tiefenmatrix, bei der jeder Pixel die gleiche 
    vorgegebene Tiefe in Metern besitzt – exakt passend zur Größe des RGB-Frames.
    
    :param color_frame: Das RGB-Bild mit der Form (Höhe, Breite, 3)
    :param constant_depth_m: Die gewünschte feste Entfernung in Metern (z.B. 2.5)
    :return: Eine 2D-Tiefenmatrix der Form (Höhe, Breite) gefüllt mit dem Tiefenwert.
    """
    # Wir holen uns nur die ersten beiden Dimensionen (Höhe und Breite)
    # Die 3 für die Farbkanäle ignorieren wir mit [:2]
    height, width = color_frame.shape[:2]
    
    # np.full erstellt eine Matrix der gewünschten Größe und füllt sie komplett mit dem Wert
    depth_frame = np.full((height, width), constant_depth_m, dtype=np.float64)
    
    return depth_frame
        



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
    local_coord_from_px = calc_local_coordinates_from_pixels(pixel_coord)     
    print(f"local_coord_from_px: {local_coord_from_px}")

    globaler_punkt = transform_lokal_coordinate_in_global_space(
        coord=local_coord_from_px, 
        matrix_name='tof', 
        matrix_dict=all_matrices
    )
    
    print("Globaler Punkt:", globaler_punkt)

    test_array: npt.NDArray = np.load("fahrsimulator-main/utils/tof_frame_1774261873.7449481(1).npy")
    test_array_m = scale_raw_depth_to_meters(test_array)
    umgerechneter_frame = transform_depth_frame_to_global_space_keep_structure(test_array_m,"tof", all_matrices)
    globale_punkt_matrix = umgerechneter_frame.reshape(512, 512, 3)
    print(globale_punkt_matrix)

    """
    TODO: 
    Gegenrechen: 
    - Punkte in einem tof-Frame umrechnen in Koordinaten manuell und dies mit der Funktion vergleichen

    - Eyetracker-Gaze-Punkte manuell in globale Koordinaten umrechnen und mit Funktion vergleichen
    """