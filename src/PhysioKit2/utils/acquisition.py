from PySide6.QtCore import Signal, QObject, QThread
from PhysioKit2.utils.data_processing_lib import lFilter, lFilter_moving_average
import time
from datetime import datetime
import serial
import serial.tools.list_ports as lp


class Data_Signals(QObject):
    data_signal = Signal(list)
    data_signal_filt = Signal(list)
    sq_signal = Signal(list)
    bf_signal = Signal(float)
    time_signal = Signal(int)
    log_signal = Signal(str)
    # stop_signal = Signal(bool)


class Data_Acquisition_Thread(QThread):
    """
        The class to handle incoming data stream from Arduino
    """
    def __init__(self, config):
        super(Data_Acquisition_Thread, self).__init__()

        self.config = config
        self.signals = Data_Signals()
        self.stop_flag = False
        self.filt_objs = {}
        self.eda_moving_average_window_size = int(self.config.SAMPLING_RATE/4.0)

        self.resp_lowcut = 0.1
        self.resp_highcut = 0.5
        self.ppg_lowcut = 0.5
        self.ppg_highcut = 3.5
        self.filt_order = 2

        self.bf_out_flag = False

        self.ser = serial.Serial()
        self.timeout = None  # specify timeout when using readline()
        self.ports = lp.comports()


    def stop(self):
        self.stop_flag = True
        time.sleep(1)
        self.terminate()
        print("Acquisition thread terminated...")


    def initialize_filters(self, uiObj):

        self.ui = uiObj

        for nCh in range(self.config.NCHANNELS):
            if self.ui.channel_types[nCh] == 'eda':
                self.filt_objs[str(nCh)] = lFilter_moving_average(window_size=self.eda_moving_average_window_size)
            elif self.ui.channel_types[nCh] == 'resp':
                self.filt_objs[str(nCh)] = lFilter(self.resp_lowcut, self.resp_highcut, self.config.SAMPLING_RATE, order=self.filt_order)
            elif self.ui.channel_types[nCh] == 'ppg':
                self.filt_objs[str(nCh)] = lFilter(self.ppg_lowcut, self.ppg_highcut, self.config.SAMPLING_RATE, order=self.filt_order)


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


    def add_bf_out_signal(self, val):
        # self.bf_out_str = str(int(val))
        self.bf_out_str = val
        # print(self.bf_out_str)
        self.bf_out_flag = True


    def run(self):
        value = []
        value_filt = []
        buffersize = (self.config.NCHANNELS)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n
        prev_elapsed_time = 0
        curr_elapsed_time = 0

        while not self.stop_flag:
            if self.config.LIVE_ACQUISITION_FLAG and self.ser.is_open:
                #Read data from serial port
                try:
                    if self.bf_out_flag:
                        # if "win" in self.config.OS_NAME:
                        #     bf_key = 'o'
                        #     if self.bf_out_str != '0':
                        #         bf_key = 'i'
                        #     else:
                        #         bf_key = 'o'
                        #     # print(self.bf_out_str)
                        #     keyboard.write(bf_key)
                        self.ser.write(self.bf_out_str.encode())                            
                        self.bf_out_flag = False

                    serial_data = self.ser.readline(buffersize)
                    serial_data = serial_data.split(b'\r\n')
                    serial_data = serial_data[0].split(b',')
                    #print(serial_data)
                except Exception as e:
                    serial_data = []
                    print("Exception:", e)
                    time.sleep(0.1)

                try:
                    value = []
                    value_filt = []     #filt value update can be done at lower rate to optimize performance in future
                    for nCh in range(self.config.NCHANNELS):
                        serial_val = int(serial_data[nCh])
                        value.append(serial_val)
                        value_filt.append(self.filt_objs[str(nCh)].lfilt(serial_val))

                    # serial_val = int(serial_data[self.config.NCHANNELS])
                    # value.append(serial_val)

                    if self.ui.data_record_flag:
                        elapsed_time = (datetime.now() - self.ui.record_start_time).total_seconds()*1000
                        if self.ui.timed_acquisition:
                            if (elapsed_time >= self.ui.curr_acquisition_time_ms):
                                self.ui.data_record_flag = False
                                # self.signals.stop_signal.emit(True)
                                self.ui.fileIO_thread.stop_recording = True
                                prev_elapsed_time = 0
                                curr_elapsed_time = 0
                                
                            else:
                                self.signals.data_signal.emit(value)
                                curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                                if prev_elapsed_time < curr_elapsed_time:
                                    prev_elapsed_time = curr_elapsed_time
                                    self.signals.time_signal.emit(curr_elapsed_time)

                        else:
                            self.signals.data_signal.emit(value)

                            curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                            if prev_elapsed_time < curr_elapsed_time:
                                prev_elapsed_time = curr_elapsed_time
                                self.signals.time_signal.emit(curr_elapsed_time)
                    else:
                        prev_elapsed_time = 0
                        curr_elapsed_time = 0

                    self.signals.data_signal_filt.emit(value_filt)
                    if "ppg" in self.config.CHANNEL_TYPES:
                        filt_val = [0, 0]
                        fv_count = 0
                        for idx in self.ui.ppg_sq_indices:
                            filt_val[fv_count] = value_filt[idx]
                            fv_count += 1
                        self.signals.sq_signal.emit(filt_val)
                    if self.ui.biofeedback_enable:
                        self.signals.bf_signal.emit(value_filt[self.ui.bf_ch_index])

                    time.sleep(0.001)

                except Exception as e:
                    try:
                        self.ser.reset_output_buffer()
                        self.ser.reset_input_buffer()
                        assert len(serial_data) == (self.config.NCHANNELS)  #data channels + time_stamp
                        print('Serial data', serial_data)
                        print("Exception:", e)
                        time.sleep(0.1)
                    except:
                        print('Mismatch in the number of channels specified in JSON file and the serial data received from Arduino or microcontroller')
                        time.sleep(0.1)

            else:
                if self.ser.is_open:
                    self.ser.reset_output_buffer()
                    self.ser.reset_input_buffer()
                if self.ui.data_record_flag:
                     self.signals.log_signal.emit("Data not recording. Check serial port connection and retry...")

                if not self.config.HOLD_ACQUISITION_THREAD:
                    break
                else:
                    time.sleep(1)


