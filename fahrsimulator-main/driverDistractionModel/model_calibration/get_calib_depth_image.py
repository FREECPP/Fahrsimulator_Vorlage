from pathlib import Path
import os
import sys 
import cv2 
import time
import numpy as np

def search_C(): 
    """
    Searches for the Analog Devices TOF SDK installation directory on the C: drive.

    Returns:
        Path: The path to the SDK's 'bin' directory.

    Raises:
        FileNotFoundError: If the SDK directory is not found on the C: drive.
    """
    root = Path("C:/")
    path = root / "Analog Devices" / "TOF_Evaluation_ADTF3175D-Rel5.0.0" / "bin"
    if path.exists():
        return path

    raise FileNotFoundError("SDK 'TOF_Evaluation_ADTF3175D-Rel5.0.0\\bin' nicht auf C:\\ gefunden. "
                            "Bitte installiere das SDK oder setze den Pfad manuell.")

def import_aditofpython(): 
    """
    Imports the Analog Devices TOF Python SDK and sets up the environment variables.

    Returns:
        tuple: A tuple containing the imported 'aditofpython' module and the SDK's 'bin' directory as a string.
    """
    bin_path = search_C() 
    bin_str = str(bin_path)
    os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")
    sys.path.insert(0, bin_str)
    import aditofpython as tof
    print(tof)
    return tof, bin_str

def get_snap(): 
    """
    Captures a single depth frame from the TOF camera, saves it as a .npy file, and displays a colorized version.

    This function initializes the TOF camera, waits for 5 seconds, captures a depth frame, and performs the following:
    - Saves the raw depth data as a .npy file.
    - Applies a color map to the depth data for visualization.
    - Displays the colorized depth image in an OpenCV window.

    Raises:
        Exception: If there are issues with camera initialization, frame capture, or file operations.
    """
    tof, bin_str = import_aditofpython()
    system = tof.System()
    mode =  "lr-qnative"
    ip = "ip:10.43.0.1"
    config = "config/config_adsd3500_adsd3100.json"

    cameras = []
    types = []
    system.getCameraList(cameras, ip)
    if not cameras:
        print("Keine TOF Kamera gefunden!")
        return False
    camera = cameras[0]

    config_path = Path(bin_str)  / config
    try:
        os.chdir(bin_str)
        camera.initialize(str(config_path))
    except Exception as e:
        print("Fehler bei der Initialisierung der Kamera:", e)
        return False
    
    camera.getAvailableFrameTypes(types)
    camera.setFrameType(mode)

    camDetails = tof.CameraDetails()
    camera.getDetails(camDetails)

    status = camera.start()
    if status: 
        print("TOF Camera started")

    print("Waiting for 5 seconds before capturing a snapshot...")
    time.sleep(5)

    i = 0
    try:
        while True: 
            frame = tof.Frame()
            status = camera.requestFrame(frame)
            if status:
                fdd = tof.FrameDataDetails()
                status = frame.getDataDetails("depth", fdd)
                if not status:
                    print("Failed to get frame data details.")
                    return False

                depth_image = np.array(frame.getData("depth"), copy=False)

                # Save the depth image as an .npy file
                BASE = Path(__file__).resolve().parents[2]   
                output_path = BASE / "driverDistractionModel/model_calibration/params/depth_calib_frame.npy"                

                MAX_DIST = 2000.0  
                if i == 20: 
                    depth_clip = np.clip(depth_image.astype(np.float32), 0, MAX_DIST)
                    depth_u8 = (depth_clip / MAX_DIST * 255).astype(np.uint8)   
                    depth_vis = cv2.applyColorMap(depth_u8, cv2.COLORMAP_TURBO)

                    img_depth_rot = cv2.rotate(depth_vis, cv2.ROTATE_180)
                    
                    # Display the colorized depth image
                    cv2.imshow("Colorized Depth Image", img_depth_rot)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows() 
                    
                    np.save(output_path, depth_image)
                    print(f"Snapshot saved as .npy file at: {output_path}")
                    return True
                
                i +=1
                
                
            else:
                print("Failed to capture frame from the camera.")
    except Exception as e:
        print("Error during snapshot capture:", e)
    finally:
        camera.stop()

if __name__ == "__main__":
    get_snap()