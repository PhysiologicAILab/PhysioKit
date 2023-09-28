import os
os.environ["PYSIDE_DESIGNER_PLUGINS"] = '.'

# This Python file uses the following encoding: utf-8
from .utils.external_sync import ServerThread, ClientThread
from .utils.biofeedback_vis import BioFeedback_Thread

import threading
import time
import json
import shutil
import numpy as np
import csv
from datetime import datetime

import numpy as np
import cv2
from copy import deepcopy

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QFileDialog
from PySide6.QtCore import QFile, QObject, Signal, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QImage

import warnings
warnings.filterwarnings("ignore")

global osname
osname = ''
try:
    osname = os.uname().sysname
except:
    pass

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.animation import TimedAnimation
from matplotlib.figure import Figure

from .utils.data_processing_lib import lFilter, lFilter_moving_average
from .utils.devices import serialPort
import argparse


global live_acquisition_flag, hold_acquisition_thread, nChannels, \
temp_filename, marker_event_status, sampling_rate, csvfile_handle, \
anim_running

live_acquisition_flag = False
hold_acquisition_thread = True
nChannels = 4                   #default
marker_event_status = False
sampling_rate = 250             #default
csvfile_handle = None
anim_running = False

# Setup a signal slot mechanism, to send data to GUI in a thread-safe way.
class Communicate(QObject):
    data_signal = Signal(list)
    data_signal_filt = Signal(list)
    bf_signal = Signal(float)
    time_signal = Signal(int)
    log_signal = Signal(str)
    stop_signal = Signal(bool)


class Server_Sync(QObject):
    record_signal = Signal(bool)



class PPG(QWidget):
    def __init__(self, args_parser):
        super(PPG, self).__init__(parent=None)
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
                    self.server_thread = ServerThread(self.sync_ip, self.sync_port, parent=self)
                    self.server_thread.update.connect(self.update_log)

                elif self.sync_role == "client":
                    self.sync_ip = self.ui.sw_config_dict["client"]["server_ip"]
                    self.sync_port = self.ui.sw_config_dict["client"]["tcp_port"]
                    self.ui.pushButton_sync.setEnabled(True)
                    self.ui.pushButton_sync.setText("Connect with Server")
                    self.client_thread = ClientThread(self.sync_ip, self.sync_port, parent=self)
                    self.client_thread.connect_update.connect(self.client_connect_status)
                    self.client_thread.sync_update.connect(self.start_recording)
                    self.server_sync_available = False

                else:
                    print("Invalid role specified for external sync settings in SW config file. Please check and start the application again...")
                    return

                self.ui.pushButton_sync.pressed.connect(self.setup_external_sync)
        except:
            print("Invalid configuration in SW config file. Please check and start the application again...")
            
        global osname
        for port, desc, hwid in sorted(self.ui.spObj.ports):
            # print("{}: {} [{}]".format(port, desc, hwid))
            self.ui.ser_ports_desc.append(str(port))
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

        self.ui.comboBox_event.currentIndexChanged.connect(self.update_event_code)
        self.ui.pushButton_Event.pressed.connect(self.toggle_marking)

        self.ui.listWidget_expConditions.currentItemChanged.connect(self.update_exp_condition)

        self.myAnim = None

        global temp_filename, csvfile_handle
        temp_utc_sec = str((datetime.now() - datetime(1970, 1, 1)).total_seconds())
        temp_utc_sec = temp_utc_sec.replace('.', '_') + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '')
        temp_filename = temp_utc_sec + "_temp.csv"
        self.csv_header = ['']
        self.ui.write_eventcode = ''
        csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(csvfile_handle)

        self.ui.biofeedback_enable = False

        ui_file.close()


    def closeEvent(self, event):
        global hold_acquisition_thread, temp_filename, csvfile_handle, \
            live_acquisition_flag, anim_running
        live_acquisition_flag = False
        hold_acquisition_thread = False

        if anim_running:
            TimedAnimation._stop(self.myAnim)
            anim_running = False

        if self.ui.biofeedback_enable:
            if self.ui.biofeedback_thread.isRunning():
                self.ui.biofeedback_thread.stop()

        if self.ext_sync_flag:
            if self.sync_role == "server":
                if self.server_thread.isRunning():
                    self.server_thread.stop()
            else:
                if self.client_thread.isRunning():
                    self.client_thread.stop()

        if os.path.exists(temp_filename):
            if not csvfile_handle.closed:
                csvfile_handle.close()
            time.sleep(0.2)
            os.remove(temp_filename)


    def update_exp_condition(self):
        indx = self.ui.listWidget_expConditions.currentRow()
        self.ui.curr_exp_condition = self.ui.conditions[indx]
        if self.ui.timed_acquisition:
            self.ui.curr_acquisition_time = self.ui.max_acquisition_time[indx]
            self.ui.curr_acquisition_time_ms = self.ui.curr_acquisition_time*1000.0
        self.ui.label_status.setText("Experiment Condition Selected: " + self.ui.curr_exp_condition)


    def setup_external_sync(self):
        if self.sync_role == "server":
            self.ui.label_status.setText("Server started...")
            self.ui.pushButton_sync.setText("Server Running")
            self.server_thread.start()
            self.ui.pushButton_sync.setEnabled(False)

        elif self.sync_role == "client":
            self.ui.pushButton_sync.setEnabled(False)
            self.ui.label_status.setText("Client is attempting to reach server with IP address = " + self.sync_ip)
            self.client_thread.start()


    def client_connect_status(self, connect_status):
        if connect_status:
            self.ui.pushButton_sync.setText("Running Client")
            self.ui.label_status.setText("Client is connected to the server with IP address = " + self.sync_ip)
        else:
            self.ui.label_status.setText("Client could not connect with to the server with IP address = " + self.sync_ip + "; Check IP address and verify that server is running.")
            self.ui.pushButton_sync.setEnabled(True)


    def update_sync_flag(self, sync_flag):
        self.server_sync_available = True
        self.ui.data_record_flag = sync_flag


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
            return

        # try:
        if self.ui.params_dict != None:

            self.ui.timed_acquisition = self.ui.params_dict["exp"]["timed_acquisition"]
            # print(self.ui.timed_acquisition, type(self.ui.timed_acquisition))
            if self.ui.timed_acquisition:
                self.ui.max_acquisition_time = self.ui.params_dict["exp"]["max_time_seconds"]
                self.ui.curr_acquisition_time = self.ui.max_acquisition_time[0]
                self.ui.curr_acquisition_time_ms = self.ui.max_acquisition_time[0] * 1000.0

            self.ui.event_codes = []
            self.ui.event_code_names = []
            for key, val in self.ui.params_dict["exp"]["event_codes"].items():
                self.ui.event_codes.append(key)
                self.ui.event_code_names.append(val)
            self.ui.comboBox_event.addItems(self.ui.event_codes)
            self.ui.eventcode = self.ui.event_codes[0]

            if "biofeedback" in self.ui.params_dict:
                if bool(self.ui.params_dict["biofeedback"]["enabled"]):
                    self.ui.biofeedback_enable = True
                    self.ui.bf_win = int(self.ui.params_dict["biofeedback"]["visual_feedback"]["window"])
                    self.ui.bf_step = int(self.ui.params_dict["biofeedback"]["visual_feedback"]["step"])
                    self.ui.bf_opt = self.ui.params_dict["biofeedback"]["visual_feedback"]["varying_parameter"]
                    self.ui.bf_ch_index = self.ui.params_dict["biofeedback"]["visual_feedback"]["ch_index"]
                    self.ui.bf_metric = self.ui.params_dict["biofeedback"]["visual_feedback"]["metric"]
                else:
                    self.ui.biofeedback_enable = False
                
            if self.ui.biofeedback_enable:
                self.ui.tabWidget.setCurrentIndex(1)
                self.ui.biofeedback_thread = BioFeedback_Thread(
                    sampling_rate, self.ui.bf_win, self.ui.bf_step, self.ui.bf_opt, self.ui.bf_metric, parent=self)
                if self.ui.bf_opt == "size":
                    self.ui.biofeedback_thread.update_bf_size.connect(self.update_bf_visualization_size)
                else:
                    self.ui.biofeedback_thread.update_bf_color.connect(self.update_bf_visualization_color)

                if self.ui.bf_opt == "size":
                    img_width = 1280
                    img_height = 720
                    self.ui.bf_center_coordinates = (img_width//2, img_height//2)
                    self.ui.bf_disp_image = 255*np.ones((img_height, img_width, 3), np.uint8)
                    self.ui.bf_circle_thickness = -1
                    self.ui.bf_circle_color = (127, 127, 127)

                    disp_image = deepcopy(self.ui.bf_disp_image)
                    disp_image = cv2.circle(disp_image, self.ui.bf_center_coordinates,
                                            self.ui.biofeedback_thread.circle_radius_baseline, self.ui.bf_circle_color, self.ui.bf_circle_thickness)
                    h, w, ch = disp_image.shape
                    bytesPerLine = ch * w
                    qimg = QImage(self.ui.bf_disp_image.data, w, h, bytesPerLine, QImage.Format_RGB888)
                    self.preview_pixmap = QPixmap.fromImage(qimg)
                    self.ui.label_biofeedback.setPixmap(self.preview_pixmap)
                    self.ui.label_palette.hide()

                else:
                    self.ui.label_biofeedback.setStyleSheet("background-color:rgb(127,127,127); border-radius: 10px")

                print("Biofeedback Enabled")


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
            self.csv_header = self.ui.channels + ["event_code"]
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
            self.figCanvas = FigCanvas(channels = self.ui.channels, ch_colors = self.ui.channel_plot_colors)
            self.myAnim = LivePlotFigCanvas(figCanvas=self.figCanvas)
            self.graphic_scene = QGraphicsScene()
            self.graphic_scene.addWidget(self.figCanvas)
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
        self.ui.comboBox_event.setEnabled(False)
        self.ui.pushButton_Event.setEnabled(False)

        if marker_event_status:
            marker_event_status = False
            self.myAnim.event_toggle = True

        # prepare for next recording
        csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(csvfile_handle)
        self.writer.writerow(self.csv_header)
        self.ui.pushButton_record_data.setEnabled(True)


    def update_pid(self, text):
        self.ui.pid = text


    def update_event_code(self, indx):
        try:
            self.ui.eventcode = self.ui.event_codes[indx]
        except:
            self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
            self.ui.eventcode = 0

    def toggle_marking(self):
        global marker_event_status
        self.myAnim.event_toggle = True
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

                if self.ui.biofeedback_enable:
                    self.ui.biofeedback_thread.start()

            else:
                self.ui.label_status.setText("Live acquisition started.")
            self.ui.pushButton_start_live_acquisition.setText('Stop Live Acquisition')        
            self.ui.listWidget_expConditions.setEnabled(False)

            if self.ui.exp_loaded:
                self.ui.pushButton_record_data.setEnabled(True)

        else:
            self.ui.label_status.setText("Live acquisition stopped.")
            # To reset the graph and clear the values
            
            self.myAnim.reset_draw()
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
        sync_comm = Server_Sync()
        sync_comm.record_signal.connect(self.start_recording)

        global temp_filename, csvfile_handle

        if not os.path.exists(temp_filename):
            csvfile_handle = open(temp_filename, 'w', encoding="utf", newline="")
            self.writer = csv.writer(csvfile_handle)
            self.writer.writerow(self.csv_header)

        sync_signal = False
        if self.ext_sync_flag:
            if self.sync_role == "server":
                self.server_thread.send_sync_to_client()
                sync_signal = True
                sync_comm.record_signal.emit(sync_signal)
            else:
                self.client_thread.wait_for_sync = True
        else:
            sync_signal = True
            sync_comm.record_signal.emit(sync_signal)


    def start_recording(self, start_signal):
        global marker_event_status
        if start_signal:
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

            self.ui.comboBox_event.setEnabled(True)
            self.ui.pushButton_Event.setEnabled(True)
            marker_event_status = False

            try:
                self.ui.eventcode = self.ui.event_codes[self.ui.comboBox_event.currentIndex]
            except:
                self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
                self.ui.eventcode = 0

        else:
            self.ui.label_status.setText('Server not running... Please retry...')
            self.ui.pushButton_record_data.setText("Record Data")
            # self.ui.pushButton_record_data.setEnabled(True)
            self.ui.pushButton_sync.setEnabled(True)

    def record_data(self):
        self.ui.pushButton_record_data.setText("Waiting")
        self.ui.pushButton_record_data.setEnabled(False)

        if not self.ui.data_record_flag:
            start_record_thread = threading.Thread(name='start_record', target=self.start_record_process, daemon=True)
            start_record_thread.start()

        else:
            self.ui.data_record_flag = False
            stop_record_thread = threading.Thread(name='stop_record', target=self.stop_record_process, daemon=True)
            stop_record_thread.start()


    def stop_record_from_thread(self, stop_signal):
        if stop_signal:
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

    def update_bf_visualization_size(self, radius):
        disp_image = deepcopy(self.ui.bf_disp_image)
        disp_image = cv2.circle(disp_image, self.ui.bf_center_coordinates, radius, self.ui.bf_circle_color, self.ui.bf_circle_thickness)
        h, w, ch = disp_image.shape
        bytesPerLine = ch * w
        qimg = QImage(disp_image.data, w, h, bytesPerLine, QImage.Format_RGB888)
        self.preview_pixmap = QPixmap.fromImage(qimg)
        self.ui.label_biofeedback.setPixmap(self.preview_pixmap)

    def update_bf_visualization_color(self, color):
        self.ui.label_biofeedback.setStyleSheet(color)


    def phys_data_acquisition(self):
        global live_acquisition_flag, hold_acquisition_thread, nChannels
        # Setup the signal-slot mechanism.
        mySrc = Communicate()
        mySrc.data_signal.connect(self.csvWrite_function)
        mySrc.data_signal_filt.connect(self.myAnim.addData)
        mySrc.time_signal.connect(self.update_time_elapsed)
        mySrc.log_signal.connect(self.update_log)
        mySrc.stop_signal.connect(self.stop_record_from_thread)
        if self.ui.biofeedback_enable:
            mySrc.bf_signal.connect(self.ui.biofeedback_thread.add_bf_data)

        value = []
        value_filt = []
        buffersize = (nChannels)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n
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
                                mySrc.stop_signal.emit(True)
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
                    if self.ui.biofeedback_enable:
                        mySrc.bf_signal.emit(value_filt[self.ui.bf_ch_index])

                except:
                    try:
                        assert len(serial_data) == (nChannels)  #data channels + time_stamp
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

class FigCanvas(FigureCanvas):
    def __init__(self, channels, ch_colors, parent=None, width=13.8, height=7.5, dpi=100):
        global nChannels, sampling_rate
        
        self.max_plot_time = 10 # 30 second time window
        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*sampling_rate)

        self.plot_signals = []
        self.axs = {}
        self.lines = {}
        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)

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

        super(FigCanvas, self).__init__(self.fig)



class LivePlotFigCanvas(TimedAnimation):
    def __init__(self, figCanvas: FigureCanvas, interval: int = 40) -> None:
        self.fig = figCanvas.fig
        global nChannels, sampling_rate, anim_running
        self.sampling_rate = sampling_rate

        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4

        self.max_plot_time = 10 # 30 second time window
        self.event_toggle = False
        self.measure_time = 1  # moving max_plot_time sample by 1 sec.
        self.max_frames_for_relimiting_axis = self.measure_time * sampling_rate

        self.count_frame = 0
        self.plot_signals = figCanvas.plot_signals
        self.axs = figCanvas.axs
        self.lines = figCanvas.lines
        anim_running = True

        super(LivePlotFigCanvas, self).__init__(self.fig, interval, blit=True)


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * self.sampling_rate)))


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
    if osname == 'Darwin':
        app.setStyle('Fusion')
    
    widget = PPG(args_parser)
    widget.show()
    ret = app.exec()

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
