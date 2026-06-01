import socket
import struct
import time

def wake_on_lan(mac_address, repeat = 3):
    # Formatiere die MAC-Adresse (entferne Trennzeichen)
    if len(mac_address) == 17:
        sep = mac_address[2]
        mac_address = mac_address.replace(sep, "")

    # Erstelle das "Magic Packet"
    # Es besteht aus 6 Mal 0xff gefolgt von der 16-fachen MAC-Adresse
    data = b'ffffffffffff' + (mac_address * 16).encode()
    send_data = b''

    # Wandle den Hex-String in echte Bytes um
    for i in range(0, len(data), 2):
        send_data += struct.pack('B', int(data[i:i + 2], 16))

    # Sende das Paket als Broadcast in das Netzwerk
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for i in range(repeat):
            # Port 9 ist der Standard für WoL
            sock.sendto(send_data, ('255.255.255.255', 9))
            if repeat > 1 and i < repeat - 1:
                time.sleep(0.1)
        print(f"Magic Packet an {mac_address} gesendet!")


# --- HIER DEINE MAC-ADRESSE EINTRAGEN ---
TARGET_MAC = "BC:0F:F3:C4:C4:70"

if __name__ == "__main__":
    wake_on_lan(TARGET_MAC)
