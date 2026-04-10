import struct


def parse_silab_data(data: bytes) -> dict:
    """
    Parse binary SiLab UDP packet.

    Expected format (52 bytes):
    - TIME (ulonglong, 8 bytes)
    - SPEED (float, 4 bytes)
    - RPM (long, 4 bytes)
    - X, Y, Z (float, 4 bytes each) - position
    - PITCH, ROLL (float, 4 bytes each) - orientation
    - STWH (float, 4 bytes) - steering wheel
    - ACCPED, BRPED, CLPED (float, 4 bytes each) - pedals

    Args:
        data: Raw binary data from SiLab UDP packet

    Returns:
        Formatted dict with parsed data or raises error
    """
    if len(data) != 52:
        raise ValueError(f"Invalid data length: expected 52 bytes, got {len(data)}")

    try:
        # Unpack binary data (little-endian format)
        unpacked = struct.unpack('<Qfffffffffff', data)

        sim_time = unpacked[0]
        speed = unpacked[1]
        rpm = unpacked[2]
        x, y, z = unpacked[3], unpacked[4], unpacked[5]
        pitch, roll = unpacked[6], unpacked[7]
        steering = unpacked[8]
        acc_pedal, brake_pedal, clutch_pedal = unpacked[9], unpacked[10], unpacked[11]

        # Return a structured dictionary with numeric values
        return {
            "sim_time": sim_time, # Updates seemingly correctly
            "speed": speed, # Gets recognized correctly -> Max value is ~70
            "rpm": rpm, # Gets recognized correctly -> Max value is ~8.7
            "x": x,
            "y": y,
            "z": z,
            "pitch": pitch,
            "roll": roll,
            "steering": steering, # Gets recognized correctly -> Goes from -7.85 to 7.85
            "acc_pedal": acc_pedal, # Gets recognized correctly -> Max value is 1
            "brake_pedal": brake_pedal, # Gets recognized correctly -> Max value is 3.5
            "clutch_pedal": clutch_pedal # Does not get recognized!
        }
    except struct.error as e:
        raise ValueError(f"Failed to parse SiLab data: {str(e)}") from e