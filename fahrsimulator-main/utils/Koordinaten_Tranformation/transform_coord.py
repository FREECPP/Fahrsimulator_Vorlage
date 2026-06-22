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
    cx: float = 523.9361572265625, # Optischer Mittelpunkt X in Pixel (px) 
    cy: float = 526.0283813476562, # Optischer Mittelpunkt Y in Pixel (px)
    fx: float = 775.8900756835938, # Brennweite X in Pixel (px)
    fy: float = 775.9134521484375  # Brennweite Y in Pixel (px)
) -> npt.NDArray[np.float64]:
    """
    Transformiert den Frame und behält die exakte Pixel-Reihenfolge bei.
    Ungültige Pixel werden als [NaN, NaN, NaN] markiert.

    Hinweis zu den Einheiten:
    Die intrinsischen Kameraparameter (cx, cy, fx, fy) sind standardmäßig in Pixeln (px)
    angegeben. Da die Formel (u - cx) * z / fx das Verhältnis von Pixelabständen nutzt,
    kürzen sich die Pixel-Einheiten (px/px) heraus. Die resultierenden X- und Y-Koordinaten
    übernehmen daher automatisch die Einheit des Z-Wertes (Meter).

    Parameter:
    ----------
    depth_frame : npt.NDArray[np.float64]
        Der Eingabe-Tiefenframe (Werte in Metern).
    matrix_name : str
        Name des Sensors zur Auswahl der Transformationsmatrix.
    matrix_dict : Dict[str, npt.NDArray[np.float64]]
        Dictionary mit den 4x4 Extrinsics-Matrizen (basierend auf Metern).
    cx, cy : float, optional
        Optischer Mittelpunkt der Kamera in Pixeln (px).
    fx, fy : float, optional
        Brennweite der Kamera in Pixeln (px).
    
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
    Wandelt rohe Tiefenwerte generisch in Meter um.
    Ungültige Messwerte (0) bleiben geschützt und werden nicht verfälscht.
    """
    # Falls eine einzelne Pixel-Liste [u, v, z_raw] übergeben wird
    if isinstance(depth_data, list) and len(depth_data) == 3:
        u, v, z_raw = depth_data
        if z_raw <= 0:
            return [u, v, 0.0] # Ungültig bleibt ungültig
        z_m = (z_raw * (range_width_m / max_raw_value)) + start_offset_m
        return [u, v, z_m]
        
    # Falls ein ganzes NumPy-Array (der Frame) übergeben wird
    elif isinstance(depth_data, np.ndarray):
        frame_m = depth_data.astype(np.float64)
        
        # Maske erstellen: Wo hat die Kamera wirklich gemessen?
        valid_mask = depth_data > 0
        
        # NUR die gültigen Pixel umrechnen
        frame_m[valid_mask] = (frame_m[valid_mask] * (range_width_m / max_raw_value)) + start_offset_m
        
        # Die ungültigen Pixel setzen wir direkt auf NaN (oder 0.0)
        frame_m[~valid_mask] = np.nan
        
        return frame_m
        
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
    
    #------------------------------------------------------------------------------------------------
    # Versuch A lokale Koordinate des Eyetrackers in globales System überführen
    print("Versuch A lokale Koordinate des Eyetrackers in globales System überführen")
    local_point_in_mm = [-8.802811622619629, 63.141273498535156, 741.1033935546875]
    local_point_in_m = local_point_in_m = [coord / 1000.0 for coord in local_point_in_mm] 
    print(f"Local_Point: {local_point_in_m}")
    global_point = transform_lokal_coordinate_in_global_space(local_point_in_m,"tobii", all_matrices) 
    print(f"Global_Point: {global_point}")

    #------------------------------------------------------------------------------------------------
    # Versuch B Tiefenframe in globales System überführen
    print("Versuch B Tiefenframe in globales System überführen")

    # Laden des beispiel-Frames
    test_array: npt.NDArray = np.load("fahrsimulator-main/utils/tof_frame_1774261873.7449481(1).npy")

    # Tiefenwerte die als Integer im Frame stehen in Meter umrechnen
    test_array_m = scale_raw_depth_to_meters(test_array)

    # Gesammter Frame in Globale Koordinaten umgerechnet
    umgerechneter_frame = transform_depth_frame_to_global_space_keep_structure(test_array_m,"tof", all_matrices)

    # Frame wieder in richtige Form bringen
    globale_punkt_matrix = umgerechneter_frame.reshape(512, 512, 3)
    print(globale_punkt_matrix)

    #------------------------------------------------------------------------------------------------
    # Versuch C RGB-Kamera-Frame in globales System überführen
    print("Versuch C RGB-Kamera-Frame in globales System überführen")
    # 1. Angenommen, du hast ein RGB-Bild (z. B. 1024x1024)
    color_frame = np.zeros((1024, 1024, 3), dtype=np.uint8) 

    # 2. Künstlichen Tiefen-Frame erstellen (z. B. alles 2.5 Meter entfernt)
    künstliche_tiefe = create_constant_depth_frame(color_frame, constant_depth_m=2.5)

    # 3. In den globalen 3D-Raum transformieren
    # (matrix_name und matrix_dict müssen natürlich definiert sein)
    punkte_3d_global = transform_depth_frame_to_global_space_keep_structure(
        depth_frame=künstliche_tiefe,
        matrix_name="cam1",
        matrix_dict=all_matrices
    )
    print(punkte_3d_global)

    # Das Ergebnis 'punkte_3d_global' hat nun die Form (1048576, 3) 
    # und enthält die globalen X, Y, Z Koordinaten in Metern.

