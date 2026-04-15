    1 def execute(eyetracker):
    2     time_synchronization_data(eyetracker)
    3 
    4 
    5 # <BeginExample>
    6 import time
    7 import tobii_research as tr
    8 
    9 
   10 def time_synchronization_data_callback(time_synchronization_data):
   11     print(time_synchronization_data)
   12 
   13 
   14 def time_synchronization_data(eyetracker):
   15     print("Subscribing to time synchronization data for eye tracker with serial number {0}.".
   16           format(eyetracker.serial_number))
   17     eyetracker.subscribe_to(tr.EYETRACKER_TIME_SYNCHRONIZATION_DATA,
   18                             time_synchronization_data_callback, as_dictionary=True)
   19 
   20     # Wait while some time synchronization data is collected.
   21     time.sleep(2)
   22 
   23     eyetracker.unsubscribe_from(tr.EYETRACKER_TIME_SYNCHRONIZATION_DATA,
   24                                 time_synchronization_data_callback)
   25     print("Unsubscribed from time synchronization data.")
   26 # <EndExample>