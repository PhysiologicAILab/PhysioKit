from PySide6.QtCore import Signal, QObject, QThread
import time
from datetime import datetime
import csv
import os
import shutil
import numpy as np

class Data_Signals(QObject):
    data_signal = Signal(list)
    time_signal = Signal(int)
    log_signal = Signal(str)
    stop_signal = Signal(bool)
    record_signal = Signal(bool)


class File_IO(QThread):
    """
        The class to handle file operations
    """

    def __init__(self, uiObj, config):
        super(File_IO, self).__init__()

        self.ui = uiObj
        self.config = config
        self.signals = Data_Signals()

        self.stop_flag = False
        self.wait_for_external_sync = False
        self.start_recording = False
        self.stop_recording = False
        self.reset_temp_file = False

        temp_utc_sec = str((datetime.now() - datetime(1970, 1, 1)).total_seconds())
        temp_utc_sec = temp_utc_sec.replace('.', '_') + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '')
        self.config.TEMP_FILENAME = temp_utc_sec + "_temp.csv"
        self.csv_header = ['']
        self.ui.write_eventcode = ''
        self.config.CSVFILE_HANDLE = open(self.config.TEMP_FILENAME, 'w', encoding="utf", newline="")
        self.writer = csv.writer(self.config.CSVFILE_HANDLE)

        self.csv_header = self.ui.channels + ["event_code"]
        self.writer.writerow(self.csv_header)


    def csvWrite_function(self, value):
        if not self.stop_flag:
            try:
                self.writer.writerow(value + [self.ui.write_eventcode])
            except:
                print("Error writing data:", value + [self.ui.write_eventcode])

    def stop(self):
        self.stop_flag = True
        time.sleep(0.3)
        # On closing of the thread
        if os.path.exists(self.config.TEMP_FILENAME):
            if not self.config.CSVFILE_HANDLE.closed:
                self.config.CSVFILE_HANDLE.close()
                time.sleep(0.2)
            os.remove(self.config.TEMP_FILENAME)
            time.sleep(0.2)
        self.terminate()
        print("FileIO thread terminated...")

    def run(self):
        while not self.stop_flag:
            # pass

            if self.wait_for_external_sync:
                start_signal = False
                if self.ext_sync_flag:
                    if self.sync_role == "server":
                        self.ui.server_thread.send_sync_to_client()
                        start_signal = True
                        self.signals.record_signal.emit(start_signal)
                    else:
                        self.ui.client_thread.wait_for_sync = True
                else:
                    start_signal = True
                    self.signals.record_signal.emit(start_signal)

                self.wait_for_external_sync = False

            # def start_record_process(self):
            # Start recording flag
            elif self.start_recording:

                start_signal = True
                self.signals.record_signal.emit(start_signal)

                if not os.path.exists(self.config.TEMP_FILENAME):
                    self.config.CSVFILE_HANDLE = open(self.config.TEMP_FILENAME, 'w', encoding="utf", newline="")
                    self.writer = csv.writer(self.config.CSVFILE_HANDLE)
                    self.writer.writerow(self.csv_header)

                self.start_recording = False
                time.sleep(0.1)

            # stop recording - flag
            elif self.stop_recording:

                self.ui.pushButton_record_data.setText("Record Data")
                # self.ui.pushButton_record_data.setEnabled(True)
                self.ui.pushButton_sync.setEnabled(True)

                if not self.config.CSVFILE_HANDLE.closed:
                    time.sleep(0.1)
                    self.config.CSVFILE_HANDLE.close()
                    time.sleep(0.1)
                self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                                self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + 
                                                self.ui.utc_sec + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '') + '.csv')
                if os.path.exists(self.config.TEMP_FILENAME):
                    shutil.move(self.config.TEMP_FILENAME, self.save_file_path)
                    self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
                    time.sleep(0.1)
                else:
                    self.ui.label_status.setText("Error saving data")

                # prepare for next recording
                self.config.CSVFILE_HANDLE = open(self.config.TEMP_FILENAME, 'w', encoding="utf", newline="")
                self.writer = csv.writer(self.config.CSVFILE_HANDLE)
                self.writer.writerow(self.csv_header)
                self.ui.pushButton_record_data.setEnabled(True)
                
                self.stop_recording = False

            elif self.reset_temp_file:
                if os.path.exists(self.config.TEMP_FILENAME):
                    if not self.config.CSVFILE_HANDLE.closed:
                        self.config.CSVFILE_HANDLE.close()
                    os.remove(self.config.TEMP_FILENAME)

                self.config.CSVFILE_HANDLE = open(self.config.TEMP_FILENAME, 'w', encoding="utf", newline="")
                self.writer = csv.writer(self.config.CSVFILE_HANDLE)
                self.writer.writerow(self.csv_header)
                self.reset_temp_file = False
                time.sleep(0.1)

            else:
                time.sleep(0.1)