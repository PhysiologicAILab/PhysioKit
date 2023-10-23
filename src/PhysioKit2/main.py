import os
import sys
os.environ["PYSIDE_DESIGNER_PLUGINS"] = '.'
os.environ["QT_LOGGING_RULES"]='*.debug=false;qt.pysideplugin=false'
import argparse
from importlib.resources import files

# This Python file uses the following encoding: utf-8

import threading
import time
import json
import shutil
import numpy as np
import csv
from datetime import datetime

import cv2
from copy import deepcopy

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QFileDialog
from PySide6.QtCore import QFile, QObject, Signal, QThread, Qt
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QPixmap, QImage

import warnings
warnings.filterwarnings("ignore")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.animation import TimedAnimation
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from .utils.data_processing_lib import lFilter, lFilter_moving_average
from .utils.external_sync import ServerThread, ClientThread
from .utils.biofeedback_vis import BioFeedback_Thread
from .utils.devices import serialPort
from .utils import config
from .sqa.inference_thread import sqaPPGInference


class Server_Sync(QObject):
    record_signal = Signal(bool)


class physManager(QWidget):
    def __init__(self, args_parser):
        super(physManager, self).__init__(parent=None)
        self.load_ui(args_parser)
        
    def load_ui(self, args_parser):
        loader = QUiLoader()
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        self.ui.graphicsView.viewport().setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        
        pixmap = QPixmap(files('PhysioKit2.images').joinpath('banner.png'))
        self.ui.label.setPixmap(pixmap)

        self.ui.exp_loaded = False
        self.ui.biofeedback_enable = False
        self.ui.sq_thread_created = False
        
        self.ui.resize(args_parser.width, args_parser.height)
        # self.ui.adjustSize()

        # Default params
        self.ext_sync_flag = False
        self.ui.baudrate = 115200

        self.ui.spObj = serialPort()
        self.ui.ser_port_names = []
        self.ui.ser_ports_desc = []
        self.ui.ser_open_status = False
        self.ui.curr_ser_port_name = ''

        temp_utc_sec = str((datetime.now() - datetime(1970, 1, 1)).total_seconds())
        temp_utc_sec = temp_utc_sec.replace('.', '_') + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '')
        config.TEMP_FILENAME = temp_utc_sec + "_temp.csv"
        self.csv_header = ['']
        self.ui.write_eventcode = ''
        config.CSVFILE_HANDLE = open(config.TEMP_FILENAME, 'w', encoding="utf", newline="")
        self.writer = csv.writer(config.CSVFILE_HANDLE)

        sw_config_path = args_parser.config 
        self.ui.sw_config_dict = None
        try:
            with open(sw_config_path) as json_file:
                self.ui.sw_config_dict = json.load(json_file)
        except:
            print("Error opening the Software (SW) Config file")
            return

        try:
            config.SAMPLING_RATE = int(self.ui.sw_config_dict["acq_params"]["fs"])
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
            
        for port, desc, hwid in sorted(self.ui.spObj.ports):
            # print("{}: {} [{}]".format(port, desc, hwid))
            self.ui.ser_ports_desc.append(str(port))
            if config.OS_NAME == 'Darwin':
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

        ui_file.close()


    def closeEvent(self, event):
        config.LIVE_ACQUISITION_FLAG = False
        config.HOLD_ACQUISITION_THREAD = False

        if self.phys_data_acq_started_flag:
            if self.phys_data_acquisition_thread.isRunning():
                self.phys_data_acquisition_thread.stop()

        if config.ANIM_RUNNING:
            TimedAnimation._stop(self.myAnim)
            config.ANIM_RUNNING = False

        if self.ui.sq_thread_created:
            if self.ui.sq_inference_thread.isRunning():
                self.ui.sq_inference_thread.stop()

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

        if os.path.exists(config.TEMP_FILENAME):
            if not config.CSVFILE_HANDLE.closed:
                config.CSVFILE_HANDLE.close()
            time.sleep(0.2)
            os.remove(config.TEMP_FILENAME)


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
                    config.SAMPLING_RATE, self.ui.bf_win, self.ui.bf_step, self.ui.bf_opt, self.ui.bf_metric, parent=self)
                if self.ui.bf_opt == "size":
                    self.ui.biofeedback_thread.update_bf_size.connect(self.update_bf_visualization_size)
                else:
                    color_bar_image = files('PhysioKit2.images').joinpath('color_bar.png')
                    pixmap = QPixmap(color_bar_image)
                    self.ui.label_palette.setPixmap(pixmap)
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
            config.NCHANNELS = len(self.ui.channels)
            self.ui.channel_types = self.ui.params_dict["exp"]["channel_types"]
            config.CHANNEL_TYPES = self.ui.channel_types
            self.ui.channel_plot_colors = self.ui.sw_config_dict["exp"]["channel_plot_colors"][:config.NCHANNELS]
            self.csv_header = self.ui.channels + ["event_code"]
            self.writer.writerow(self.csv_header)

            # # Place the matplotlib figure
            gv_rect = self.ui.graphicsView.viewport().rect()
            gv_width = gv_rect.width()
            gv_height = gv_rect.height()
            self.figCanvas = FigCanvas(sampling_rate=config.SAMPLING_RATE,
                                       channels = self.ui.channels, 
                                       channel_types = config.CHANNEL_TYPES,
                                       ch_colors = self.ui.channel_plot_colors, 
                                       sq_flag = self.ui.params_dict["exp"]["assess_signal_quality"], 
                                       width = gv_width, height = gv_height)
            self.myAnim = PlotAnimation(figCanvas=self.figCanvas)
            self.graphic_scene = QGraphicsScene()
            self.graphic_scene.addWidget(self.figCanvas)
            self.ui.graphicsView.setScene(self.graphic_scene)
            self.ui.graphicsView.show()

            if "ppg" in config.CHANNEL_TYPES and self.ui.params_dict["exp"]["assess_signal_quality"]:
                sq_legend_image = files('PhysioKit2.images').joinpath('sq_indication.png')
                pixmap = QPixmap(sq_legend_image)
                self.ui.label_sq_legend.setPixmap(pixmap)                
                self.sqa_config = files('PhysioKit2.sqa.config').joinpath('sqa_ppg.json')
                self.ui.ppg_sq_indices = list(np.where(np.array(config.CHANNEL_TYPES) == "ppg")[0])
                num_sq_ch = len(self.ui.ppg_sq_indices)
                self.ui.sq_inference_thread = sqaPPGInference(
                    self.sqa_config, config.SAMPLING_RATE, num_sq_ch, axis=1, parent=self)
                self.ui.sq_inference_thread.update_sq_vec.connect(self.myAnim.addSQData)
                self.ui.sq_thread_created = True

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

        self.ui.pushButton_record_data.setEnabled(False)
        if not config.CSVFILE_HANDLE.closed:
            time.sleep(0.5)
            config.CSVFILE_HANDLE.close()
            time.sleep(0.5)
        self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                           self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + 
                                           self.ui.utc_sec + '_' + str(round(np.random.rand(1)[0], 6)).replace('0.', '') + '.csv')
        if os.path.exists(config.TEMP_FILENAME):
            shutil.move(config.TEMP_FILENAME, self.save_file_path)
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
            time.sleep(0.5)
        else:
            self.ui.label_status.setText("Error saving data")

        self.ui.pushButton_record_data.setText("Start Recording")
        self.ui.comboBox_event.setEnabled(False)
        self.ui.pushButton_Event.setEnabled(False)

        if config.MARKER_EVENT_STATUS:
            config.MARKER_EVENT_STATUS = False
            self.myAnim.event_toggle = True

        # prepare for next recording
        config.CSVFILE_HANDLE = open(config.TEMP_FILENAME, 'w', encoding="utf", newline="")
        self.writer = csv.writer(config.CSVFILE_HANDLE)
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
        self.myAnim.event_toggle = True
        if not config.MARKER_EVENT_STATUS:
            config.MARKER_EVENT_STATUS = True
            self.ui.write_eventcode = self.ui.eventcode
            self.ui.pushButton_Event.setText("Stop Marking")
        else:
            config.MARKER_EVENT_STATUS = False
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
        if not config.LIVE_ACQUISITION_FLAG:
            config.LIVE_ACQUISITION_FLAG = True
            if not self.phys_data_acq_started_flag:
                # self.phys_data_acquisition_thread = threading.Thread(name='phys_data_acquisition', target=self.phys_data_acquisition, daemon=True)
                # self.phys_data_acquisition_thread.start()

                self.phys_data_acquisition_thread = dataAcquisition(self.ui, parent=self)
                self.phys_data_acquisition_thread.data_signal.connect(self.csvWrite_function)
                self.phys_data_acquisition_thread.data_signal_filt.connect(self.myAnim.addData)
                self.phys_data_acquisition_thread.time_signal.connect(self.update_time_elapsed)
                self.phys_data_acquisition_thread.log_signal.connect(self.update_log)
                self.phys_data_acquisition_thread.stop_signal.connect(self.stop_record_from_thread)

                if self.ui.params_dict["exp"]["assess_signal_quality"]:
                    self.phys_data_acquisition_thread.sq_signal.connect(self.ui.sq_inference_thread.add_sq_data)
                
                self.phys_data_acquisition_thread.start()

                self.phys_data_acq_started_flag = True
                self.ui.label_status.setText("Live acquisition started")

                if self.ui.params_dict["exp"]["assess_signal_quality"]:
                    self.ui.sq_inference_thread.start()

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
            if os.path.exists(config.TEMP_FILENAME):
                if not config.CSVFILE_HANDLE.closed:
                    config.CSVFILE_HANDLE.close()
                os.remove(config.TEMP_FILENAME)

            config.CSVFILE_HANDLE = open(config.TEMP_FILENAME, 'w', encoding="utf", newline="")
            self.writer = csv.writer(config.CSVFILE_HANDLE)
            self.writer.writerow(self.csv_header)

            config.LIVE_ACQUISITION_FLAG = False
            self.ui.pushButton_record_data.setEnabled(False)
            self.ui.pushButton_start_live_acquisition.setText('Start Live Acquisition')

            self.ui.listWidget_expConditions.setEnabled(True)


    def start_record_process(self):
        sync_comm = Server_Sync()
        sync_comm.record_signal.connect(self.start_recording)

        if not os.path.exists(config.TEMP_FILENAME):
            config.CSVFILE_HANDLE = open(config.TEMP_FILENAME, 'w', encoding="utf", newline="")
            self.writer = csv.writer(config.CSVFILE_HANDLE)
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
            config.MARKER_EVENT_STATUS = False

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
        self.filt_objs = {}
        self.eda_moving_average_window_size = int(config.SAMPLING_RATE/4.0)

        self.resp_lowcut = 0.1
        self.resp_highcut = 0.5
        self.ppg_lowcut = 0.5
        self.ppg_highcut = 5.0
        self.filt_order = 1

        for nCh in range(config.NCHANNELS):
            if self.ui.channel_types[nCh] == 'eda':
                self.filt_objs[str(nCh)] = lFilter_moving_average(window_size=self.eda_moving_average_window_size)
            elif self.ui.channel_types[nCh] == 'resp':
                self.filt_objs[str(nCh)] = lFilter(self.resp_lowcut, self.resp_highcut, config.SAMPLING_RATE, order=self.filt_order)
            elif self.ui.channel_types[nCh] == 'ppg':
                self.filt_objs[str(nCh)] = lFilter(self.ppg_lowcut, self.ppg_highcut, config.SAMPLING_RATE, order=self.filt_order)


    def stop(self):
        self.stop_flag = True
        self.terminate()
        print("Data acquisition thread terminated...")


    def run(self):
        
        if self.ui.biofeedback_enable:
            self.bf_signal.connect(self.ui.biofeedback_thread.add_bf_data)

        value = []
        value_filt = []
        buffersize = (config.NCHANNELS)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n
        prev_elapsed_time = 0
        curr_elapsed_time = 0

        while not self.stop_flag:
            if config.LIVE_ACQUISITION_FLAG and self.ui.spObj.ser.is_open:
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
                    for nCh in range(config.NCHANNELS):
                        serial_val = int(serial_data[nCh])
                        value.append(serial_val)
                        value_filt.append(self.filt_objs[str(nCh)].lfilt(serial_val))

                    # serial_val = int(serial_data[config.NCHANNELS])
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
                    if "ppg" in config.CHANNEL_TYPES:
                        filt_val = []
                        for idx in self.ui.ppg_sq_indices:
                            filt_val.append(value_filt[idx])
                        self.sq_signal.emit(filt_val)
                    if self.ui.biofeedback_enable:
                        self.bf_signal.emit(value_filt[self.ui.bf_ch_index])

                    time.sleep(0.001)

                except:
                    try:
                        assert len(serial_data) == (config.NCHANNELS)  #data channels + time_stamp
                        print('error in reading data', serial_data)
                        time.sleep(0.1)
                    except:
                        print('Mismatch in the number of channels specified in JSON file and the serial data received from Arduino or microcontroller')
                        time.sleep(0.1)

            else:
                if self.ui.data_record_flag:
                     self.log_signal.emit("Data not recording. Check serial port connection and retry...")
                if not config.HOLD_ACQUISITION_THREAD:
                    break
                else:
                    time.sleep(1)



class FigCanvas(FigureCanvas):
    def __init__(self, sampling_rate, channels, channel_types, ch_colors, sq_flag, parent=None, width=13.8, height=7.5, dpi=100):
        
        self.max_plot_time = 10 # 30 second time window
        self.max_plot_channels = 4
        self.nChannels = len(channels)
        self.nChannels = min(self.nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
        self.channel_types = channel_types[:self.nChannels]
        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*sampling_rate)

        self.plot_signals = []
        self.axs = {}
        self.lines = {}

        self.sq_flag = sq_flag
        if self.sq_flag:
            self.sq_vecs = []
            self.sq_images = {}
        width = width/dpi
        height = height/dpi

        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        # self.fig = Figure(constrained_layout=True)

        for nCh in range(self.nChannels):
            self.plot_signals.append(10 * np.ones(self.max_plot_time * sampling_rate))
    
            # if self.sq_flag and self.channel_types[nCh] == "ppg":
            if self.sq_flag:
                self.sq_vecs.append(0.5 * np.ones((1, self.max_plot_time * 2))) # 1/0.5 as 0.5 is sq_resolution. 

            if self.nChannels == self.max_plot_channels:
                self.axs[str(nCh)] = self.fig.add_subplot(2, 2, nCh+1)
            else:
                self.axs[str(nCh)] = self.fig.add_subplot(self.nChannels, 1, nCh+1)

            (self.lines[str(nCh)],) = self.axs[str(nCh)].plot(self.x_axis, self.plot_signals[nCh], ch_colors[nCh], markersize=10, linestyle='solid')
            
            if self.sq_flag and self.channel_types[nCh] == "ppg":
                self.sq_images[str(nCh)] = self.axs[str(nCh)].imshow(
                    self.sq_vecs[nCh], clim=(0,1), cmap=plt.cm.RdYlGn, aspect='auto', alpha=0.5, extent=(0, self.max_plot_time, 0, 1)
                    )
            self.axs[str(nCh)].set_xlabel('Time (seconds)', fontsize=16)
            self.axs[str(nCh)].set_ylabel(channels[nCh], fontsize=16)
            self.axs[str(nCh)].set_xlim(0, self.max_plot_time)
            self.axs[str(nCh)].set_ylim(0, 1)
            self.axs[str(nCh)].yaxis.set_ticks_position('left')
            self.axs[str(nCh)].xaxis.set_ticks_position('bottom')

        super(FigCanvas, self).__init__(self.fig)



class PlotAnimation(TimedAnimation):
    def __init__(self, figCanvas: FigureCanvas, interval: int = 40) -> None:
        self.fig = figCanvas.fig
        self.sq_flag = figCanvas.sq_flag
        self.nChannels = figCanvas.nChannels
        self.channel_types = figCanvas.channel_types

        self.exception_count = 0
        self.ppg_sq_indices = list(np.where(np.array(self.channel_types) == "ppg")[0])

        self.max_plot_time = 10 # 30 second time window
        self.event_toggle = False
        self.measure_time = 0.2  # moving max_plot_time sample by 0.2 sec.
        self.max_frames_for_relimiting_axis = self.measure_time * config.SAMPLING_RATE

        self.count_frame = 0
        self.plot_signals = figCanvas.plot_signals
        self.sq_vecs = figCanvas.sq_vecs
        self.axs = figCanvas.axs
        self.lines = figCanvas.lines
        self.sq_images = figCanvas.sq_images
        config.ANIM_RUNNING = True

        super(PlotAnimation, self).__init__(self.fig, interval, blit=True)


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * config.SAMPLING_RATE)))


    def _init_draw(self):
        lines = []
        sq_images = []
        for nCh in range(self.nChannels):
            lines.append(self.lines[str(nCh)])
            if self.channel_types[nCh] == "ppg":
                sq_images.append(self.sq_images[str(nCh)])
        lines = tuple(lines)
        sq_images = tuple(sq_images)
        return (lines, sq_images)


    def reset_draw(self):
        self.count_frame = 0 # self.max_plot_time * config.SAMPLING_RATE
        return

    def addSQData(self, value):
        for indx in range(len(self.ppg_sq_indices)):
            self.sq_vecs[self.ppg_sq_indices[indx]] = 1 - value[indx]
            # print(1 - value[indx])
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

        if config.LIVE_ACQUISITION_FLAG:   

            if self.count_frame >= self.max_frames_for_relimiting_axis:
                self.count_frame = 0
                # for nCh in range(self.nChannels):
                #     mx = np.max(self.plot_signals[nCh])
                #     mn = np.min(self.plot_signals[nCh])
                #     self.plot_signals[nCh] = (self.plot_signals[nCh] - mn)/(mx - mn)
                #     # self.axs[str(nCh)].set_ylim(np.min(self.plot_signals[nCh]), np.max(self.plot_signals[nCh]))

                self._drawn_artists = []
                for nCh in range(self.nChannels):
                    mx = np.max(self.plot_signals[nCh])
                    mn = np.min(self.plot_signals[nCh])
                    sig = (self.plot_signals[nCh] - mn)/(mx - mn)
                    self.lines[str(nCh)].set_ydata(sig)
                    if self.sq_flag and self.channel_types[nCh] == "ppg":
                        self.sq_images[str(nCh)].set_data(self.sq_vecs[nCh])
                        self._drawn_artists.append(self.sq_images[str(nCh)])
                    self._drawn_artists.append(self.lines[str(nCh)])

            if self.event_toggle:
                if config.MARKER_EVENT_STATUS:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, (5, 5)))
                else:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, ()))
                self.event_toggle = False

            # self._drawn_artists = []
            # for nCh in range(self.nChannels):
            #     mx = np.max(self.plot_signals[nCh])
            #     mn = np.min(self.plot_signals[nCh])
            #     sig = (self.plot_signals[nCh] - mn)/(mx - mn)
            #     self.lines[str(nCh)].set_ydata(sig)
            #     if self.sq_flag and self.channel_types[nCh] == "ppg":
            #         self.sq_images[str(nCh)].set_data(self.sq_vecs[nCh])
            #         self._drawn_artists.append(self.sq_images[str(nCh)])
            #     self._drawn_artists.append(self.lines[str(nCh)])
        return





def main(argv=sys.argv):

    # Create the application instance.
    app = QApplication([])

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=files('PhysioKit2.configs.avr_default').joinpath('sw_config.json'), type=str,
                        dest='config', help='Software Config file-path')

    (width,height) = app.screens()[-1].size().toTuple()
    print("Adjusting the interface to the screen resolution: width, height", width, height)

    parser.add_argument('--width', default=width, dest="width", type=int)
    parser.add_argument('--height', default=height, dest="height", type=int)

    # args = parser.parse_args(argv[1:])

    parser.add_argument('REMAIN', nargs='*')
    args_parser = parser.parse_args()


    if config.OS_NAME == 'Darwin':
        app.setStyle('Fusion')
    
    widget = physManager(args_parser)
    widget.show()
    ret = app.exec()

    # sys.exit(ret)
    return

if __name__ == '__main__':
    main()
