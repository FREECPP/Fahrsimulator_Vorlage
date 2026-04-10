import time
from serial.tools import list_ports
from pyshimmer import DEFAULT_BAUDRATE, ShimmerBluetooth
from serial import Serial


def debug_all_com_ports():
    """
    Zeigt ALLE COM-Ports und ihre Properties an.
    Hilfreich um zu sehen, wie dein Shimmer erkannt wird.
    """
    print("\n=== DEBUG: Alle verfügbaren COM-Ports ===\n")
    ports = list_ports.comports()

    if not ports:
        print("Keine COM-Ports gefunden!")
        return

    for i, port in enumerate(ports):
        print(f"Port {i}:")
        print(f"  device:      {port.device}")
        print(f"  name:        {port.name}")
        print(f"  description: {port.description}")
        print(f"  hwid:        {port.hwid}")
        print(f"  vid:         {port.vid}")
        print(f"  pid:         {port.pid}")
        print()


def find_shimmer_com_port_smart(shimmer_mac=None):
    """
    Findet Shimmer COM-Port über die MAC-Adresse in der hwid.

    Args:
        shimmer_mac (str): Optional - MAC-Adresse zum Suchen (z.B. "00:06:66:1C:40:75")
                          Wenn None, wird nach Shimmer3-Präfixen gesucht.
    """
    time.sleep(2)
    ports = list_ports.comports()

    if not ports:
        raise RuntimeError("Keine COM-Ports gefunden!")

    if shimmer_mac:
        mac_clean = shimmer_mac.replace(":", "").upper()
        print(f"Suche nach Shimmer mit MAC: {shimmer_mac}")

        for port in ports:
            hwid = (port.hwid or "").upper()

            if mac_clean in hwid:
                print(f"✓ Shimmer gefunden: {port.device} (MAC: {shimmer_mac})")
                return port.device

        print(f"⚠ MAC {shimmer_mac} nicht gefunden! Alle verfügbaren Ports:")
        for port in ports:
            print(f"  {port.device}: {port.hwid}")
        raise RuntimeError(f"Shimmer mit MAC {shimmer_mac} nicht gefunden!")

    print("Suche nach Shimmer3-Geräten (MAC-Präfix 000666)...")

    for port in ports:
        hwid = (port.hwid or "").upper()

        if "BTHENUM" in hwid: 
            if "000666" in hwid:
                print(f"✓ Shimmer3 gefunden: {port.device}")
                return port.device

    raise RuntimeError(
        "Kein Shimmer COM-Port gefunden!\n"
        "Optionen:\n"
        "1. Shimmer-Gerät in Windows koppeln\n"
        "2. Mit MAC-Adresse aufrufen: find_shimmer_com_port_smart('00:06:66:1C:40:75')"
    )


def pair_shimmer(shimmer_mac=None):
    """Findet Shimmer COM-Port"""
    return find_shimmer_com_port_smart(shimmer_mac)


def connect_to_shimmer(shimmer_mac=None):
    """
    Verbindet mit Shimmer über Serial + ShimmerBluetooth

    Args:
        shimmer_mac (str): Optional - MAC-Adresse des Shimmer (z.B. "00:06:66:1C:40:75")
    """
    com_port = find_shimmer_com_port_smart(shimmer_mac)
    print(f"Verbinde mit {com_port}...")

    for n in range(5):
        try:
            serial = Serial(com_port, DEFAULT_BAUDRATE, timeout=2)
            shim_dev = ShimmerBluetooth(serial)
            shim_dev.initialize()
            print("✓ Shimmer erfolgreich initialisiert!")
            return shim_dev
        except Exception as e:
            print(f"✗ Fehler beim Verbinden: {e}, versuche erneut {n}")
            pass
        n += 1
        time.sleep(2)
    return None

if __name__ == "__main__":
    debug_all_com_ports()
    try:
        #shim = connect_to_shimmer()
        shim = connect_to_shimmer("00:06:66:1C:40:75")

        print("Verbindung erfolgreich!")
    except Exception as e:
        print(f"Fehler: {e}")