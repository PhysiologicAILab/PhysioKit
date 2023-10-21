from PySide6.QtCore import Signal, QThread, Signal
from datetime import datetime
import time


    # def phys_data_acquisition(self):
    #     global live_acquisition_flag, hold_acquisition_thread, nChannels, channel_types
    #     # Setup the signal-slot mechanism.
    #     mySrc = Communicate()
    #     mySrc.data_signal.connect(self.csvWrite_function)
    #     mySrc.data_signal_filt.connect(self.myAnim.addData)
    #     mySrc.time_signal.connect(self.update_time_elapsed)
    #     mySrc.log_signal.connect(self.update_log)
    #     mySrc.stop_signal.connect(self.stop_record_from_thread)
    #     mySrc.sq_signal.connect(self.ui.sq_inference_thread.add_sq_data)




class dataAcquisition(QThread):
    """
        The class to handle incoming data stream from Arduino
    """
    data_signal = Signal(list)
    data_signal_filt = Signal(list)
    sq_signal = Signal(list)
    bf_signal = Signal(float)
    time_signal = Signal(int)
    log_signal = Signal(str)
    stop_signal = Signal(bool)

    def __init__(self, uiObj, parent):
        super(dataAcquisition, self).__init__(parent=parent)

        self.ui = uiObj
        self.stop_flag = False


    def stop(self):
        self.stop_flag = True
        self.terminate()
        print("Data acquisition thread terminated...")


    def run(self):

        global live_acquisition_flag, hold_acquisition_thread, nChannels, channel_types
        
        if self.ui.biofeedback_enable:
            self.bf_signal.connect(self.ui.biofeedback_thread.add_bf_data)

        value = []
        value_filt = []
        buffersize = (nChannels)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n
        prev_elapsed_time = 0
        curr_elapsed_time = 0

        while not self.stop_flag:
            if live_acquisition_flag and self.ui.spObj.ser.is_open:
                #Read data from serial port
                try:
                    serial_data = self.ui.spObj.ser.readline(buffersize)
                    serial_data = serial_data.split(b'\r\n')
                    serial_data = serial_data[0].split(b',')
                    #print(serial_data)
                except:
                    serial_data = []
                    print('Serial port not open')
                    time.sleep(0.1)

                try:
                    value = []
                    value_filt = []
                    for nCh in range(nChannels):
                        serial_val = int(serial_data[nCh])
                        value.append(serial_val)
                        value_filt.append(self.filt_objs[str(nCh)].lfilt(serial_val))

                    # serial_val = int(serial_data[nChannels])
                    # value.append(serial_val)

                    if self.ui.data_record_flag:
                        elapsed_time = (datetime.now() - self.ui.record_start_time).total_seconds()*1000
                        if self.ui.timed_acquisition:
                            if (elapsed_time >= self.ui.curr_acquisition_time_ms):
                                self.ui.data_record_flag = False
                                self.stop_signal.emit(True)
                                prev_elapsed_time = 0
                                curr_elapsed_time = 0
                                
                            else:
                                self.data_signal.emit(value)
                                curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                                if prev_elapsed_time < curr_elapsed_time:
                                    prev_elapsed_time = curr_elapsed_time
                                    self.time_signal.emit(curr_elapsed_time)

                        else:
                            self.data_signal.emit(value)

                            curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                            if prev_elapsed_time < curr_elapsed_time:
                                prev_elapsed_time = curr_elapsed_time
                                self.time_signal.emit(curr_elapsed_time)
                    else:
                        prev_elapsed_time = 0
                        curr_elapsed_time = 0

                    self.data_signal_filt.emit(value_filt)
                    if "ppg" in channel_types:
                        filt_val = []
                        for idx in self.ui.ppg_sq_indices:
                            filt_val.append(value_filt[idx])
                        self.sq_signal.emit(filt_val)
                    if self.ui.biofeedback_enable:
                        self.bf_signal.emit(value_filt[self.ui.bf_ch_index])

                    time.sleep(0.001)

                except:
                    try:
                        assert len(serial_data) == (nChannels)  #data channels + time_stamp
                        print('error in reading data', serial_data)
                        time.sleep(0.1)
                    except:
                        print('Mismatch in the number of channels specified in JSON file and the serial data received from Arduino or microcontroller')
                        time.sleep(0.1)

            else:
                if self.ui.data_record_flag:
                     self.log_signal.emit("Data not recording. Check serial port connection and retry...")
                if not hold_acquisition_thread:
                    break
                else:
                    time.sleep(1)
