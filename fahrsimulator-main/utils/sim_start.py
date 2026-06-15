import pyautogui
import time
import subprocess


def start_silab_prozess(simulation_path,exe_pfad=r"D:\SILAB\bin\SILAB.exe",arbeitsverzeichnis=r"D:\SILAB\bin"):

    print("\n===== SILAB START =====")
    print(f"EXE: {exe_pfad}")
    print(f"CFG: {simulation_path}")
    print(f"CWD: {arbeitsverzeichnis}")

    try:


        print(
            f"Starte SiLab mit: {simulation_path}"
        )

        subprocess.Popen(
            [exe_pfad, simulation_path],
            cwd=arbeitsverzeichnis
        )

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