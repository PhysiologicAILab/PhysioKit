# This Python file uses the following encoding: utf-8
import threading
import time
import json
import shutil
import numpy as np
import csv
from datetime import datetime

import numpy as np

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QFileDialog
from PySide6.QtCore import QFile, QObject, Signal
from PySide6.QtUiTools import QUiLoader

import os
global osname
osname = ''
try:
    osname = os.uname().sysname
except:
    pass

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.animation import TimedAnimation
from matplotlib.figure import Figure

from utils.data_processing_lib import lFilter, lFilter_moving_average
from utils.devices import serialPort
from utils.external_sync import External_Sync
import argparse



global live_acquisition_flag, hold_acquisition_thread, nChannels, temp_filename, marker_event_status, sampling_rate, csvfile_handle
live_acquisition_flag = False
hold_acquisition_thread = True
nChannels = 4                   #default
marker_event_status = False
sampling_rate = 250             #default
csvfile_handle = None

# Setup a signal slot mechanism, to send data to GUI in a thread-safe way.
class Communicate(QObject):
    data_signal = Signal(list)
    data_signal_filt = Signal(list)
    time_signal = Signal(int)
    log_signal = Signal(str)


class PPG(QWidget):
    def __init__(self, args_parser):
        super(PPG, self).__init__()
        self.load_ui(args_parser)
        
    def load_ui(self, args_parser):
        loader = QUiLoader()
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)

        self.ui.exp_loaded = False

        global sampling_rate
        # Default params
        self.ext_sync_flag = False
        self.ui.baudrate = 115200

        self.resp_lowcut = 0.1
        self.resp_highcut = 0.4
        self.ppg_lowcut = 0.8
        self.ppg_highcut = 3.5
        self.filt_order = 2
        self.eda_moving_average_window_size = int(sampling_rate/4.0)

        self.ui.spObj = serialPort()
        self.ui.ser_port_names = []
        self.ui.ser_ports_desc = []
        self.ui.ser_open_status = False
        self.ui.curr_ser_port_name = ''

        sw_config_path = args_parser.config 
        self.ui.sw_config_dict = None
        try:
            with open(sw_config_path) as json_file:
                self.ui.sw_config_dict = json.load(json_file)
        except:
            print("Error opening the Software (SW) Config file")
            return

        try:
            sampling_rate = int(self.ui.sw_config_dict["acq_params"]["fs"])
            self.ui.baudrate = int(self.ui.sw_config_dict["acq_params"]["baudrate"])

            # External Sync         
            self.ext_sync_flag = bool(self.ui.sw_config_dict["external_sync"]["enable"])
            if self.ext_sync_flag:
                self.ui.label_sync.setEnabled(True)
                self.sync_role = self.ui.sw_config_dict["external_sync"]["role"]
                if self.sync_role == "server":
                    self.sync_ip = ""
                    self.sync_port = self.ui.sw_config_dict["server"]["tcp_port"]
                    self.ui.pushButton_sync.setEnabled(True)
                    self.ui.pushButton_sync.setText("Start TCP Server")
                elif self.sync_role == "client":
                    self.sync_ip = self.ui.sw_config_dict["client"]["server_ip"]
                    self.sync_port = self.ui.sw_config_dict["client"]["tcp_port"]
                    self.ui.pushButton_sync.setEnabled(True)
                    self.ui.pushButton_sync.setText("Connect with Server")
                else:
                    print("Invalid role specified for external sync settings in SW config file. Please check and start the application again...")
                    return

                self.sync_obj = External_Sync(self.sync_role, self.sync_ip, self.sync_port)
                self.ui.pushButton_sync.pressed.connect(self.setup_external_sync)
        except:
            print("Invalid configuration in SW config file. Please check and start the application again...")
            
        global osname
        for port, desc, hwid in sorted(self.ui.spObj.ports):
            # print("{}: {} [{}]".format(port, desc, hwid))
            self.ui.ser_ports_desc.append(str(port) + "; " + str(desc) + "; " + str(hwid))
            if osname == 'Darwin':
                port = port.replace('/dev/cu', '/dev/tty')
            self.ui.ser_port_names.append(port)

        self.ui.comboBox_comport.addItems(self.ui.ser_ports_desc)
        if len(self.ui.ser_port_names) >= 1:
            self.ui.pushButton_connect.setEnabled(True)
            self.ui.curr_ser_port_name = self.ui.ser_port_names[0]
        self.ui.label_status.setText("Serial port specified: " + self.ui.curr_ser_port_name +
                                     "; Select experiment and condition to start recording data.")
        self.ui.comboBox_comport.currentIndexChanged.connect(self.update_serial_port)
        self.ui.pushButton_connect.pressed.connect(self.connect_serial_port)
        self.ui.pushButton_start_live_acquisition.pressed.connect(self.start_acquisition)
        self.phys_data_acq_started_flag = False

        self.ui.pid = ""
        self.ui.lineEdit_PID.textChanged.connect(self.update_pid)

        self.ui.pushButton_exp_params.pressed.connect(self.load_exp_params)

        self.ui.data_record_flag = False

        self.ui.pushButton_record_data.pressed.connect(self.record_data)
        self.ui.utc_timestamp_featDict = datetime.utcnow()

        self.ui.lineEdit_Event.textChanged.connect(self.update_event_code)
        self.ui.pushButton_Event.pressed.connect(self.toggle_marking)

        self.ui.listWidget_expConditions.currentItemChanged.connect(self.update_exp_condition)

        self.myFig = None

        global temp_filename, csvfile_handle
        temp_utc_sec = str((datetime.now() - datetime(1970, 1, 1)).total_seconds())
        temp_utc_sec = temp_utc_sec.replace('.', '_') + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '')
        temp_filename = temp_utc_sec + "_temp.csv"
        self.csv_header = ['']
        self.ui.write_eventcode = ''
        csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(csvfile_handle)

        ui_file.close()



    def update_exp_condition(self):
        indx = self.ui.listWidget_expConditions.currentRow()
        self.ui.curr_exp_condition = self.ui.conditions[indx]
        if self.ui.timed_acquisition:
            self.ui.curr_acquisition_time = self.ui.max_acquisition_time[indx]
            self.ui.curr_acquisition_time_ms = self.ui.curr_acquisition_time*1000.0
        self.ui.label_status.setText("Experiment Condition Selected: " + self.ui.curr_exp_condition)


    def setup_external_sync(self):
        if self.sync_role == "server":
            self.ui.label_status.setText("Server is starting...")
            start_server_thread = threading.Thread(name='start_server', target=self.sync_obj.start_accepting_client_connection, daemon=True)
            start_server_thread.start()
            self.ui.pushButton_sync.setText("Running Server")
            self.ui.label_status.setText("Server is ready to accept client connection...")
            self.ui.pushButton_sync.setEnabled(False)

        elif self.sync_role == "client":
            self.ui.pushButton_sync.setEnabled(False)
            self.ui.label_status.setText("Client is attempting to reach server with IP address = " + self.sync_ip)
            connect_status = self.sync_obj.connect_with_server()
            if connect_status:
                self.ui.pushButton_sync.setText("Running Client")
                self.ui.label_status.setText("Client is connected to the server with IP address = " + self.sync_ip)
            else:
                self.ui.label_status.setText("Client could not connect with to the server with IP address = " + self.sync_ip + "; Check IP address and verify that server is running.")
                self.ui.pushButton_sync.setEnabled(True)


    def load_exp_params(self):

        global nChannels, sampling_rate
        
        fname = QFileDialog.getOpenFileName(filter='*.json')[0]
        self.ui.label_params_file.setText(os.path.basename(fname))

        self.ui.params_dict = None
        try:
            with open(fname) as json_file:
                self.ui.params_dict = json.load(json_file)
        except:
            self.ui.label_status.setText("Error opening the JSON file")

        # try:
        if self.ui.params_dict != None:

            self.ui.timed_acquisition = self.ui.params_dict["exp"]["timed_acquisition"]
            # print(self.ui.timed_acquisition, type(self.ui.timed_acquisition))
            if self.ui.timed_acquisition:
                self.ui.max_acquisition_time = self.ui.params_dict["exp"]["max_time_seconds"]
                self.ui.curr_acquisition_time = self.ui.max_acquisition_time[0]
                self.ui.curr_acquisition_time_ms = self.ui.max_acquisition_time[0] * 1000.0

            self.ui.data_root_dir = self.ui.params_dict["exp"]["datapath"]
            if not os.path.exists(self.ui.data_root_dir):
                os.makedirs(self.ui.data_root_dir)

            self.ui.curr_exp_name = self.ui.params_dict["exp"]["study_name"]
            self.ui.label_study_name.setText(self.ui.curr_exp_name)
            self.ui.conditions = self.ui.params_dict["exp"]["conditions"]
            self.ui.curr_exp_condition = self.ui.conditions[0]
            self.ui.listWidget_expConditions.clear()
            self.ui.listWidget_expConditions.addItems(self.ui.conditions)
            self.ui.listWidget_expConditions.setCurrentRow(0)

            self.ui.channels = self.ui.params_dict["exp"]["channels"]
            nChannels = len(self.ui.channels)
            self.ui.channel_types = self.ui.params_dict["exp"]["channel_types"]
            self.ui.channel_plot_colors = self.ui.sw_config_dict["exp"]["channel_plot_colors"][:nChannels]
            self.csv_header = self.ui.channels + ["arduino_ts", "event_code"]
            self.writer.writerow(self.csv_header)

            self.filt_objs = {}
            self.eda_moving_average_window_size = int(sampling_rate/4.0)

            for nCh in range(nChannels):
                if self.ui.channel_types[nCh] == 'eda':
                    self.filt_objs[str(nCh)] = lFilter_moving_average(window_size=self.eda_moving_average_window_size)
                elif self.ui.channel_types[nCh] == 'resp':
                    self.filt_objs[str(nCh)] = lFilter(self.resp_lowcut, self.resp_highcut, sampling_rate, order=self.filt_order)
                elif self.ui.channel_types[nCh] == 'ppg':
                    self.filt_objs[str(nCh)] = lFilter(self.ppg_lowcut, self.ppg_highcut, sampling_rate, order=self.filt_order)

            # # Place the matplotlib figure
            self.myFig = LivePlotFigCanvas(channels = self.ui.channels, ch_colors = self.ui.channel_plot_colors)
            self.graphic_scene = QGraphicsScene()
            self.graphic_scene.addWidget(self.myFig)
            self.ui.graphicsView.setScene(self.graphic_scene)
            self.ui.graphicsView.show()

            self.ui.exp_loaded = True
            if self.ui.ser_open_status:
                self.ui.pushButton_start_live_acquisition.setEnabled(True)

            self.ui.pushButton_exp_params.setEnabled(False)
            self.ui.label_status.setText("Loaded experiment parameters successfully")

        # except:
        #     self.ui.label_status.setText("Error loading parameters")



    def csvWrite_function(self, value):
        try:
            self.writer.writerow(value + [self.ui.write_eventcode])
        except:
            print("Error writing data:", value + [self.ui.write_eventcode])

    
    def stop_record_process(self):
        global temp_filename, marker_event_status, csvfile_handle

        self.ui.pushButton_record_data.setEnabled(False)
        if not csvfile_handle.closed:
            time.sleep(0.5)
            csvfile_handle.close()
            time.sleep(0.5)
        self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                           self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + 
                                           self.ui.utc_sec + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '') + '.csv')
        if os.path.exists(temp_filename):
            shutil.move(temp_filename, self.save_file_path)
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
            time.sleep(0.5)
        else:
            self.ui.label_status.setText("Error saving data")

        self.ui.pushButton_record_data.setText("Start Recording")
        self.ui.lineEdit_Event.setEnabled(False)
        self.ui.pushButton_Event.setEnabled(False)

        if marker_event_status:
            marker_event_status = False
            self.myFig.event_toggle = True

        # prepare for next recording
        csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(csvfile_handle)
        self.writer.writerow(self.csv_header)
        self.ui.pushButton_record_data.setEnabled(True)


    def update_pid(self, text):
        self.ui.pid = text


    def update_event_code(self, text):
        try:
            self.ui.eventcode = int(text)
        except:
            self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
            self.ui.eventcode = 0

    def toggle_marking(self):
        global marker_event_status
        self.myFig.event_toggle = True
        if not marker_event_status:
            marker_event_status = True
            self.ui.write_eventcode = self.ui.eventcode
            self.ui.pushButton_Event.setText("Stop Marking")
        else:
            marker_event_status = False
            self.ui.write_eventcode = ''
            self.ui.pushButton_Event.setText("Start Marking")


    def update_serial_port(self):
        self.ui.curr_ser_port_name = self.ui.ser_port_names[self.ui.comboBox_comport.currentIndex()]
        self.ui.label_status.setText("Serial port specified: " + self.ui.curr_ser_port_name)


    def connect_serial_port(self):
        if not self.ui.ser_open_status:
            self.ui.ser_open_status = self.ui.spObj.connectPort(self.ui.curr_ser_port_name, self.ui.baudrate)
            if self.ui.ser_open_status:
                self.ui.label_status.setText("Serial port is now connected: " + str(self.ui.spObj.ser))
                self.ui.pushButton_connect.setText('Disconnect')
                if self.ui.exp_loaded:
                    self.ui.pushButton_start_live_acquisition.setEnabled(True)
            else:
                self.ui.label_status.setText("Serial port could not get connected: Please retry")

        else:
            self.ui.spObj.disconnectPort()
            self.ui.ser_open_status = False
            self.ui.label_status.setText("Serial port is now disconnected: " + str(self.ui.spObj.ser))
            self.ui.pushButton_connect.setText('Connect')
            self.ui.pushButton_start_live_acquisition.setEnabled(False)


    def start_acquisition(self):
        global live_acquisition_flag, temp_filename, csvfile_handle
        if not live_acquisition_flag:
            live_acquisition_flag = True
            if not self.phys_data_acq_started_flag:
                self.phys_data_acquisition_thread = threading.Thread(name='phys_data_acquisition', target=self.phys_data_acquisition, daemon=True)
                self.phys_data_acquisition_thread.start()
                self.phys_data_acq_started_flag = True
                self.ui.label_status.setText("Live acquisition started")
            else:
                self.ui.label_status.setText("Live acquisition started.")
            self.ui.pushButton_start_live_acquisition.setText('Stop Live Acquisition')        
            self.ui.listWidget_expConditions.setEnabled(False)

            if self.ui.exp_loaded:
                self.ui.pushButton_record_data.setEnabled(True)

        else:
            self.ui.label_status.setText("Live acquisition stopped.")
            # To reset the graph and clear the values
            
            self.myFig.reset_draw()
            if os.path.exists(temp_filename):
                if not csvfile_handle.closed:
                    csvfile_handle.close()
                os.remove(temp_filename)

            csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
            self.writer = csv.writer(csvfile_handle)
            self.writer.writerow(self.csv_header)

            live_acquisition_flag = False
            self.ui.pushButton_record_data.setEnabled(False)
            self.ui.pushButton_start_live_acquisition.setText('Start Live Acquisition')

            self.ui.listWidget_expConditions.setEnabled(True)


    def start_record_process(self):

        global temp_filename, marker_event_status, csvfile_handle
        self.ui.pushButton_record_data.setText("Starting to Record...")
        self.ui.pushButton_record_data.setEnabled(False)

        if not os.path.exists(temp_filename):
            csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
            self.writer = csv.writer(csvfile_handle)
            self.writer.writerow(self.csv_header)

        sync_signal = False
        if self.ext_sync_flag:
            if self.sync_role == "server":
                self.sync_obj.send_sync_to_client()
                sync_signal = True
            else:
                sync_signal = self.sync_obj.wait_for_server_sync()
                if not sync_signal:
                    self.ui.label_status.setText('Server not running... Please retry...')
                    self.ui.pushButton_record_data.setText("Record Data")
                    self.ui.pushButton_record_data.setEnabled(True)
        else:
            sync_signal = True

        if sync_signal:
            self.ui.record_start_time = datetime.now()
            self.ui.data_record_flag = True

            self.ui.utc_sec = str((self.ui.record_start_time - datetime(1970, 1, 1)).total_seconds())
            self.ui.utc_sec = self.ui.utc_sec.replace('.', '_')

            self.ui.pushButton_record_data.setText("Stop Recording")
            self.ui.pushButton_record_data.setEnabled(True)

            if self.ui.timed_acquisition:
                self.ui.label_status.setText("Timed Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition + "; Max-Time: " + str(self.ui.curr_acquisition_time))
            else:
                self.ui.label_status.setText("Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)

            self.ui.lineEdit_Event.setEnabled(True)
            self.ui.pushButton_Event.setEnabled(True)
            marker_event_status = False

            try:
                self.ui.eventcode = int(self.ui.lineEdit_Event.text())
            except:
                self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
                self.ui.eventcode = 0
    

    def record_data(self):
        if not self.ui.data_record_flag:
            start_record_thread = threading.Thread(name='start_record', target=self.start_record_process, daemon=True)
            start_record_thread.start()

        else:
            self.ui.data_record_flag = False
            stop_record_thread = threading.Thread(name='stop_record', target=self.stop_record_process, daemon=True)
            stop_record_thread.start()


    def update_time_elapsed(self, elapsed_time):
        if self.ui.timed_acquisition:
            self.ui.label_status.setText("Time remaining (seconds): " + str(self.ui.curr_acquisition_time - elapsed_time))
        else:
            self.ui.label_status.setText("Time elapsed (seconds): " + str(elapsed_time))

    def update_log(self, log_message):
        self.ui.label_status.setText(log_message)


    def phys_data_acquisition(self):
        global live_acquisition_flag, hold_acquisition_thread, nChannels
        # Setup the signal-slot mechanism.
        mySrc = Communicate()
        mySrc.data_signal.connect(self.csvWrite_function)
        mySrc.data_signal_filt.connect(self.myFig.addData)
        mySrc.time_signal.connect(self.update_time_elapsed)
        mySrc.log_signal.connect(self.update_log)

        value = []
        value_filt = []
        buffersize = (nChannels + 1)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n
        prev_elapsed_time = 0
        curr_elapsed_time = 0

        while(True):
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

                try:
                    value = []
                    value_filt = []
                    for nCh in range(nChannels):
                        serial_val = float(serial_data[nCh])
                        value.append(serial_val)
                        value_filt.append(self.filt_objs[str(nCh)].lfilt(serial_val))

                    serial_val = float(serial_data[nChannels])
                    value.append(serial_val)

                    if self.ui.data_record_flag:
                        if self.ui.timed_acquisition:
                            elapsed_time = (datetime.now() - self.ui.record_start_time).total_seconds()*1000
                            if (elapsed_time >= self.ui.curr_acquisition_time_ms):
                                self.ui.data_record_flag = False
                                stop_record_thread = threading.Thread(name='stop_record', target=self.stop_record_process, daemon=True)
                                stop_record_thread.start()
                                prev_elapsed_time = 0
                                curr_elapsed_time = 0
                                
                            else:
                                mySrc.data_signal.emit(value)
                                curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                                if prev_elapsed_time < curr_elapsed_time:
                                    prev_elapsed_time = curr_elapsed_time
                                    mySrc.time_signal.emit(curr_elapsed_time)

                        else:
                            mySrc.data_signal.emit(value)

                            curr_elapsed_time = int(round(elapsed_time/1000.0, 0))
                            if prev_elapsed_time < curr_elapsed_time:
                                prev_elapsed_time = curr_elapsed_time
                                mySrc.time_signal.emit(curr_elapsed_time)
                    else:
                        prev_elapsed_time = 0
                        curr_elapsed_time = 0

                    mySrc.data_signal_filt.emit(value_filt)

                except:
                    try:
                        assert len(serial_data) == (nChannels + 1)  #data channels + time_stamp
                        print('error in reading data', serial_data)
                    except:
                        print('Mismatch in the number of channels specified in JSON file and the serial data received from Arduino or microcontroller')

            else:
                if self.ui.data_record_flag:
                     mySrc.log_signal.emit("Data not recording. Check serial port connection and retry...")
                if not hold_acquisition_thread:
                    break
                else:
                    time.sleep(1)



class LivePlotFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self, channels, ch_colors):
        self.exception_count = 0
        global nChannels, sampling_rate

        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
        self.max_plot_time = 10 # 30 second time window
        self.count_frame = 0
        self.event_toggle = False
        self.measure_time = 1  # moving max_plot_time sample by 1 sec.
        self.max_frames_for_relimiting_axis = self.measure_time * sampling_rate
                
        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*sampling_rate)

        self.plot_signals = []
        self.axs = {}
        self.lines = {}

        self.fig = Figure(figsize=(13.8, 7.5), layout="tight")

        for nCh in range(self.nChannels):
            self.plot_signals.append(1000 * np.ones(self.max_plot_time * sampling_rate))

            if self.nChannels == self.max_plot_channels:
                self.axs[str(nCh)] = self.fig.add_subplot(2, 2, nCh+1)
            else:
                self.axs[str(nCh)] = self.fig.add_subplot(self.nChannels, 1, nCh+1)

            (self.lines[str(nCh)],) = self.axs[str(nCh)].plot(self.x_axis, self.plot_signals[nCh], ch_colors[nCh], markersize=10, linestyle='solid')
            self.axs[str(nCh)].set_xlabel('Time (seconds)', fontsize=16)
            self.axs[str(nCh)].set_ylabel(channels[nCh], fontsize=16)
            self.axs[str(nCh)].set_xlim(0, self.max_plot_time)
            self.axs[str(nCh)].set_ylim(0, 1)
            self.axs[str(nCh)].yaxis.set_ticks_position('left')
            self.axs[str(nCh)].xaxis.set_ticks_position('bottom')

        FigureCanvas.__init__(self, self.fig)
        # TimedAnimation.__init__(self, self.fig, interval=int(round(10*1000.0/sampling_rate)), blit = True)  # figure update frequency: 1/10th of sampling rate
        TimedAnimation.__init__(self, self.fig, interval=50, blit = True)  # figure update frequency: 30 FPS
        return


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * sampling_rate)))


    def _init_draw(self):
        lines = []
        for nCh in range(self.nChannels):
            lines.append(self.lines[str(nCh)])
        lines = tuple(lines)
        return (lines)


    def reset_draw(self):
        self.count_frame = 0 # self.max_plot_time * sampling_rate

        return


    def addData(self, value):
        self.count_frame += 1

        for nCh in range(self.nChannels):
            self.plot_signals[nCh] = np.roll(self.plot_signals[nCh], -1)
            self.plot_signals[nCh][-1] = value[nCh]
        return


    def _step(self, *args):
        # Extends the _step() method for the TimedAnimation class.
        try:
            TimedAnimation._step(self, *args)
        except Exception as e:
            self.exception_count += 1
            print("Plot exception count:", str(self.exception_count))
            TimedAnimation._stop(self)
            pass
        return


    def _draw_frame(self, framedata):
        global live_acquisition_flag, marker_event_status
        if live_acquisition_flag:   

            if self.count_frame >= self.max_frames_for_relimiting_axis:
                self.count_frame = 0

                for nCh in range(self.nChannels):
                    self.axs[str(nCh)].set_ylim(np.min(self.plot_signals[nCh]), np.max(self.plot_signals[nCh]))

            if self.event_toggle:
                if marker_event_status:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, (5, 5)))
                else:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, ()))
                self.event_toggle = False

            self._drawn_artists = []
            for nCh in range(self.nChannels):
                self.lines[str(nCh)].set_ydata(self.plot_signals[nCh])
                self._drawn_artists.append(self.lines[str(nCh)])

        return


def main(app, args_parser):
    global hold_acquisition_thread, temp_filename, csvfile_handle, live_acquisition_flag

    if osname == 'Darwin':
        app.setStyle('Fusion')
    
    widget = PPG(args_parser)
    widget.show()
    ret = app.exec()

    live_acquisition_flag = False
    del widget
    hold_acquisition_thread = False

    if os.path.exists(temp_filename):
        if not csvfile_handle.closed:
            csvfile_handle.close()
        time.sleep(0.2)
        os.remove(temp_filename)

    # sys.exit(ret)
    return

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/Uno/sw_config.json', type=str,
                        dest='config', help='Software Config file-path')
    parser.add_argument('REMAIN', nargs='*')
    args_parser = parser.parse_args()

    # Create the application instance.
    app = QApplication([])
    main(app, args_parser)
