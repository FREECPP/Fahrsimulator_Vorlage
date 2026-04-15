
# <BeginExample>
import time
import tobii_research as tr


def execute(eyetracker):
    time_synchronization_data(eyetracker)

def time_synchronization_data_callback(time_synchronization_data):
    #print(f"Unix-Systime: {time.time_ns() / 1e3}")
    print(f"Tobii-System-Time-Stamp: {tr.get_system_time_stamp()}")
    print(time_synchronization_data)


def time_synchronization_data(eyetracker):
    print("Subscribing to time synchronization data for eye tracker with serial number {0}.".
    format(eyetracker.serial_number))
    eyetracker.subscribe_to(tr.EYETRACKER_TIME_SYNCHRONIZATION_DATA,
    time_synchronization_data_callback, as_dictionary=True)

    # Wait while some time synchronization data is collected.
    print("Wait some Time")
    time.sleep(2)

    eyetracker.unsubscribe_from(tr.EYETRACKER_TIME_SYNCHRONIZATION_DATA,
    time_synchronization_data_callback)
    print("Unsubscribed from time synchronization data.")
# <EndExample>

def find_tracker() -> None:
    try:
        found_eyetrackers = tr.find_all_eyetrackers()
        device = found_eyetrackers[0]
        print(f"Using eyetracker: {device.device_name} @ {device.address}")
        return device

    except Exception as e:
        print(f"Error in EyetrackerLogger: {e}")

dev = find_tracker()
execute(dev)