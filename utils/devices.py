import serial
import serial.tools.list_ports as lp

class serialPort():
    def __init__(self, baudrate=38400) -> None:
        self.ser = serial.Serial()
        self.baudrate = baudrate
        self.timeout = None  # specify timeout when using readline()
        self.ports = lp.comports()

    def connectPort(self, port_name):
        self.ser.port = port_name  # "/dev/cu.usbmodem14101" # 'COM3'  # Arduino serial port
        self.ser.baudrate = self.baudrate
        self.ser.timeout = self.timeout  # specify timeout when using readline()
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        # self.ser.bytesize = serial.EIGHTBITS
        self.ser.open()
        # self.ser.reset_input_buffer()
        # self.ser.write(str.encode('1\r\n', 'UTF-8'))
        return self.ser.is_open

    def disconnectPort(self):
        self.ser.close()
        return
