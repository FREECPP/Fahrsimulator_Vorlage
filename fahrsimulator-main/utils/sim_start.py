import pyautogui
import time
import subprocess
import os


def start_silab_prozess(exe_pfad = r"D:\SILAB\bin\SILAB.exe", argumente = r"D:\SILAB\Projects\SILABDemo\SILABDemo_Highway.cfg", arbeitsverzeichnis = r"D:\SILAB\bin"):
   
    try:
        subprocess.Popen([exe_pfad, argumente], cwd=arbeitsverzeichnis)
        time.sleep(3)

        pyautogui.press('enter')
        time.sleep(20)

        pyautogui.hotkey('ctrl', 'l')
        time.sleep(3)

        pyautogui.press('enter')
        time.sleep(7)

        pyautogui.hotkey('ctrl', 's')

    except Exception as e:
        print(f"Fehler beim Starten: {e}")

if __name__ == "__main__":
    start_silab_prozess()