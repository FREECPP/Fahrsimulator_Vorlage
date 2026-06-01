"""
ToDO: 
Skript schreiben, ähnliches Prinzip, wie first_frame.py
Erste Funktion, suche auf C:\ nach Verzeichnis Analog Devices für das Setzen des Python Pfades.
"""

import numpy as np
from typing import Optional
from pathlib import Path
import os
import time
import sys 

def search_C(): 
    """
    Searches the C:\ drive for the Analog Devices SDK directory.

    Returns:
        Path: The path to the SDK's 'bin' directory.

    Raises:
        FileNotFoundError: If the SDK directory is not found on the C:\ drive.
    """
    root = Path("C:/")

    path = root / "Analog Devices" / "TOF_Evaluation_ADTF3175D-Rel5.0.0" / "bin"
    
    if path.exists():
        return path

    raise FileNotFoundError("SDK 'TOF_Evaluation_ADTF3175D-Rel5.0.0\\bin' nicht auf C:\\ gefunden. "
                            "Bitte installiere das SDK oder setze den Pfad manuell.")

def import_aditofpython(): 
    """
    Imports the Analog Devices ToF Python SDK by setting the appropriate paths.

    Returns:
        tuple: A tuple containing the imported `aditofpython` module and the SDK path as a string.

    Raises:
        FileNotFoundError: If the SDK directory is not found.
    """
    bin_path = search_C() 
    bin_str = str(bin_path)
    os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
    sys.path.insert(0, bin_str)
    import aditofpython as tof
    print(tof)
    return tof, bin_str

def try_connection(): 
    """
    Attempts to connect to the ToF camera, initialize it, and start it.

    This function:
    - Imports the ToF SDK.
    - Connects to the camera using the specified IP and configuration.
    - Initializes the camera and starts it.
    - Stops the camera after verifying the connection.

    Prints:
        Success or error messages based on the connection status.
    """
    tof, bin_str = import_aditofpython()
    system = tof.System()
    modemapping = {
        "lr-native": {"width": 1024, "height": 1024},
        "lr-qnative": {"width": 512, "height": 512},
        "lr-mixed": {"width": 512, "height": 512},
        "sr-native": {"width": 1024, "height": 1024},
        "sr-qnative": {"width": 512, "height": 512},
        "sr-mixed": {"width": 512, "height": 512},
    }
    mode =  "lr-qnative"

    ip = "ip:10.43.0.1"
    config = "config/config_adsd3500_adsd3100.json"

    cameras = []
    types = []
    system.getCameraList(cameras, ip)
    if not cameras:
        print("Keine TOF Kamera gefunden!")
        return
    camera = cameras[0]

    config_path = Path(bin_str)  / config
    try:
        os.chdir(bin_str)
        camera.initialize(str(config_path))
    except Exception as e:
        print("Fehler bei der Initialisierung der Kamera:", e)
        return
    
    camera.getAvailableFrameTypes(types)
    camera.setFrameType(mode)

    camDetails = tof.CameraDetails()
    camera.getDetails(camDetails)

    status = camera.start()
    if status: 
        print("TOF Camera started")
    
    print("\n\n =======>    Starting TOF camera was successful! \n\n")
    camera.stop()

if __name__ == "__main__":
    try_connection() 