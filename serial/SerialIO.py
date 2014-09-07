"""
https://github.com/gregpinero/ArduinoPlot/blob/master/Arduino_Monitor.py
Listen to serial, return most recent numeric values
Lots of help from here:
http://stackoverflow.com/questions/1093598/pyserial-how-to-read-last-line-sent-from-serial-device
"""
from threading import Thread
import time
import serial

last_received = ''
def receiving(ser):
    global last_received
    buffer = ''
    while True:
        try:
            buffer = buffer + ser.readline(ser.inWaiting()).decode()
            if '\n' in buffer:
                lines = buffer.split('\n') # Guaranteed to have at least 2 entries
                last_received = lines[-2]
                #If the Arduino sends lots of empty lines, you'll lose the
                #last filled line, so you could make the above statement conditional
                #like so: if lines[-2]: last_received = lines[-2]
                buffer = lines[-1]
        except IOError:
            print("Device is not sending messages")
            time.sleep(2)
        except UnicodeDecodeError:
            print("Unicode problem")
            time.sleep(2)
        except:
            print("Uknown problem")


class SerialData(object, serial_port='/dev/ttyACM0'):
    def __init__(self, init=50):
        try:
            self.ser = serial.Serial(
                port = serial_port,
                baudrate = 115200,
            )
            time.sleep(2)
        except serial.serialutil.SerialException:
            self.ser = None
        else:
            Thread(target=receiving, args=(self.ser,)).start()

    def next(self):
        if not self.ser:
            return 0
        for i in range(40):
            raw_line = last_received
            try:
                return raw_line.strip()
            except ValueError:
                time.sleep(.005)
        return 0.

    def __del__(self):
        if self.ser:
            self.ser.close()

if __name__=='__main__':
    s = SerialData()
    for i in range(500):
        time.sleep(.015)
        print(s.next())