import serial
import serial.tools.list_ports as lp

class serialPort():
    def __init__(self) -> None:
        self.ser = serial.Serial()
        self.timeout = None  # specify timeout when using readline()
        self.ports = lp.comports()

    def connectPort(self, port_name, baudrate=115200):
        self.ser.port = port_name  # "/dev/cu.usbmodem14101" # 'COM3'  # Arduino serial port
        self.ser.baudrate = baudrate
        self.ser.timeout = self.timeout  # specify timeout when using readline()
        self.ser.parity = serial.PARITY_NONE
        self.ser.stopbits = serial.STOPBITS_ONE
        # self.ser.bytesize = serial.EIGHTBITS
        try:
            self.ser.open()
            return self.ser.is_open
        except serial.serialutil.SerialException:
            return False

        # self.ser.reset_input_buffer()
        # self.ser.write(str.encode('1\r\n', 'UTF-8'))

    def disconnectPort(self):
        self.ser.close()
        return



