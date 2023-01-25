# This Python file uses the following encoding: utf-8
import threading
import time
import json
import shutil
import numpy as np
import csv
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QDialog, QLineEdit, QDialogButtonBox, QFormLayout, QFileDialog
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

from utils.data_processing_lib import lFilter, lFilter_moving_average
from utils.devices import serialPort
from datetime import datetime

global live_acquisition_flag
live_acquisition_flag = False



class PPG(QWidget):
    def __init__(self):
        super(PPG, self).__init__()
        self.load_ui()
        
    def load_ui(self):
        loader = QUiLoader()
        path = os.path.join(os.path.dirname(__file__), "form.ui")
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)

        self.ui.exp_loaded = False

        # Default params
        self.ui.fs = 250 #sampling rate
        self.ui.baudrate = 2000000

        self.ui.spObj = serialPort()
        self.ui.ser_port_names = []
        self.ui.ser_ports_desc = []
        self.ui.ser_open_status = False
        self.ui.curr_ser_port_name = ''
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
        self.ppgDataLoop_started = False

        self.ui.pid = ""
        self.ui.lineEdit_PID.textChanged.connect(self.update_pid)

        self.ui.pushButton_exp_params.pressed.connect(self.load_exp_params)

        self.ui.data_record_flag = False
        self.ui.timed_acquisition = False
        self.ui.max_acquisition_time = -1
        
        self.ui.pushButton_record_data.pressed.connect(self.record_data)
        self.ui.utc_timestamp_featDict = datetime.utcnow()

        self.ui.lineEdit_Event.textChanged.connect(self.update_event_code)
        self.ui.pushButton_Event.pressed.connect(self.toggle_marking)

        # Add the callbackfunc
        self.ppgDataLoop = threading.Thread(name='ppgDataLoop', target=ppgDataSendLoop, daemon=True, args=(
            self.addData_callbackFunc, self.ui.spObj))

        self.ui.listWidget_expConditions.currentItemChanged.connect(self.update_exp_condition)

        self.myFig = None
        self.temp_filename = "temp.csv"
        self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(self.csvfile)
        self.writer.writerow(["eda", "resp", "ppg1", "ppg2", "arduino_ts", "event_code"])

        ui_file.close()


    def __del__(self):
        global live_acquisition_flag
        live_acquisition_flag = False
        try:
            if self.ui.spObj.ser.is_open:
                self.ui.spObj.disconnectPort()
        except:
            pass
        if os.path.exists(self.temp_filename):
            if not self.csvfile.closed:
                self.csvfile.close()
            os.remove(self.temp_filename)


    def update_exp_condition(self):
        self.ui.curr_exp_condition = self.ui.conditions[self.ui.listWidget_expConditions.currentRow()]
        self.ui.label_status.setText("Experiment Condition Selected: " + self.ui.curr_exp_condition)


    def load_exp_params(self):
        fname = QFileDialog.getOpenFileName(filter='*.json')[0]
        self.ui.label_params_file.setText(os.path.basename(fname))

        try:
            with open(fname) as json_file:
                self.ui.params_dict = json.load(json_file)

            self.ui.fs = int(self.ui.params_dict["acq_params"]["fs"])
            self.ui.baudrate = int(self.ui.params_dict["acq_params"]["baudrate"])
            
            self.ui.timed_acquisition = self.ui.params_dict["acq_params"]["timed_acquisition"]
            # print(self.ui.timed_acquisition, type(self.ui.timed_acquisition))
            if self.ui.timed_acquisition:
                self.ui.max_acquisition_time = int(self.ui.params_dict["acq_params"]["max_time_seconds"])

            self.ui.data_root_dir = self.ui.params_dict["common"]["datapath"]
            if not os.path.exists(self.ui.data_root_dir):
                os.makedirs(self.ui.data_root_dir)

            self.ui.curr_exp_name = self.ui.params_dict["exp"]["study_name"]
            self.ui.label_study_name.setText(self.ui.curr_exp_name)
            self.ui.conditions = self.ui.params_dict["exp"]["conditions"]
            self.ui.curr_exp_condition = self.ui.conditions[0]
            self.ui.listWidget_expConditions.clear()
            self.ui.listWidget_expConditions.addItems(self.ui.conditions)
            self.ui.listWidget_expConditions.setCurrentRow(0)

            self.ui.exp_loaded = True
            self.ui.pushButton_exp_params.setEnabled(False)
            self.ui.label_status.setText("Loaded experiment parameters successfully")
        
        except:
            self.ui.label_status.setText("Error loading parameters")
            return

        # # Place the matplotlib figure
        self.myFig = LivePlotFigCanvas(uiObj=self.ui)
        self.graphic_scene = QGraphicsScene()
        self.graphic_scene.addWidget(self.myFig)
        self.ui.graphicsView.setScene(self.graphic_scene)
        self.ui.graphicsView.show()


    def addData_callbackFunc(self, value):
        # print("Add data: " + str(value))
        self.myFig.addData(value)

        if self.ui.data_record_flag:
            eda_val, resp_val, ppg1_val, ppg2_val, ts_val = value
            if self.ui.event_status:
                self.writer.writerow([eda_val, resp_val, ppg1_val, ppg2_val, ts_val, self.ui.eventcode])
            else:
                self.writer.writerow([eda_val, resp_val, ppg1_val, ppg2_val, ts_val, ''])

            if self.ui.timed_acquisition:
                elapsed_time = (datetime.now() - self.ui.record_start_time).total_seconds()
                # self.ui.label_status.setText("Time remaining: " + str(self.ui.max_acquisition_time - elapsed_time))
                if (elapsed_time >= self.ui.max_acquisition_time):
                    self.ui.data_record_flag = False
                    self.csvfile.close()
                    time.sleep(1)
                    self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                                    self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + self.ui.utc_sec + '.csv')
                    shutil.move(self.temp_filename, self.save_file_path)
                    self.ui.pushButton_record_data.setText("Start Recording")
                    self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
                    self.ui.lineEdit_Event.setEnabled(False)
                    self.ui.pushButton_Event.setEnabled(False)
                    self.ui.event_status = False

                    # prepare for next recording
                    self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
                    self.writer = csv.writer(self.csvfile)
                    self.writer.writerow(["eda", "resp", "ppg1", "ppg2", "arduino_ts", "event_code"])

        return



    def update_pid(self, text):
        self.ui.pid = text


    def update_event_code(self, text):
        try:
            self.ui.eventcode = int(text)
        except:
            self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
            self.ui.eventcode = 0

    def toggle_marking(self):
        self.myFig.event_toggle = True
        if not self.ui.event_status:
            self.ui.event_status = True
            self.ui.pushButton_Event.setText("Stop Marking")
        else:
            self.ui.event_status = False
            self.ui.pushButton_Event.setText("Start Marking")


    def update_serial_port(self):
        self.ui.curr_ser_port_name = self.ui.ser_port_names[self.ui.comboBox_comport.currentIndex()]
        self.ui.label_status.setText("Serial port specified: " + self.ui.curr_ser_port_name)


    def connect_serial_port(self):
        if not self.ui.ser_open_status:
            self.ui.ser_open_status = self.ui.spObj.connectPort(self.ui.curr_ser_port_name, self.ui.baudrate)
            self.ui.label_status.setText("Serial port is now connected: " + str(self.ui.spObj.ser))
            self.ui.pushButton_start_live_acquisition.setEnabled(True)
            if self.ui.ser_open_status:
                self.ui.pushButton_connect.setText('Disconnect')
        else:
            self.ui.spObj.disconnectPort()
            self.ui.ser_open_status = False
            self.ui.label_status.setText("Serial port is now disconnected: " + str(self.ui.spObj.ser))
            self.ui.pushButton_connect.setText('Connect')
            self.ui.pushButton_start_live_acquisition.setEnabled(False)


    def start_acquisition(self):
        global live_acquisition_flag
        if not live_acquisition_flag:
            live_acquisition_flag = True
            if not self.ppgDataLoop_started:
                self.ppgDataLoop.start()
                self.ppgDataLoop_started = True
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
            if os.path.exists(self.temp_filename):
                os.remove(self.temp_filename)

            live_acquisition_flag = False
            self.ui.pushButton_record_data.setEnabled(False)
            self.ui.pushButton_start_live_acquisition.setText('Start Live Acquisition')

            self.ui.listWidget_expConditions.setEnabled(True)


    
    def record_data(self):
        if not self.ui.data_record_flag:
            
            self.ui.record_start_time = datetime.now()
            self.ui.data_record_flag = True

            self.ui.utc_sec = str((self.ui.record_start_time - datetime(1970, 1, 1)).total_seconds())
            self.ui.utc_sec = self.ui.utc_sec.replace('.', '_')

            # self.ui.utc_timestamp_signal = datetime.utcnow()
            self.ui.pushButton_record_data.setText("Stop Recording")
            if self.ui.timed_acquisition:
                self.ui.label_status.setText("Timed Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition + "; Max-Time: " + str(self.ui.max_acquisition_time))
            else:
                self.ui.label_status.setText("Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)

            self.ui.lineEdit_Event.setEnabled(True)
            self.ui.pushButton_Event.setEnabled(True)
            self.ui.event_status = False
            try:
                self.ui.eventcode = int(self.ui.lineEdit_Event.text())
            except:
                self.ui.label_status.setText("Incorrect entry for evencode, using eventcode = 0")
                self.ui.eventcode = 0

        else:
            self.ui.data_record_flag = False
            self.csvfile.close()
            time.sleep(1)
            self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                               self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + self.ui.utc_sec + '.csv')
            shutil.move(self.temp_filename, self.save_file_path)
            self.ui.pushButton_record_data.setText("Start Recording")
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
            self.ui.lineEdit_Event.setEnabled(False)
            self.ui.pushButton_Event.setEnabled(False)
            self.ui.event_status = False

            self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow(["eda", "resp", "ppg1", "ppg2", "arduino_ts", "event_code"])


class LivePlotFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self, uiObj):
        self.uiObj = uiObj
        self.exception_count = 0

        self.max_plot_time = 10 # 30 second time window
        self.measure_time = 1  # moving max_plot_time sample by 1 sec.
        self.count_frame = 0
        self.event_toggle = False
        
        self.resp_lowcut = 0.1
        self.resp_highcut = 0.4
        self.ppg_lowcut = 0.8
        self.ppg_highcut = 3.5
        self.filt_order = 2
        self.moving_average_window_size = int(self.uiObj.fs/4.0)
        self.eda_filt_obj = lFilter_moving_average(window_size=self.moving_average_window_size)
        self.resp_filt_obj = lFilter(self.resp_lowcut, self.resp_highcut, self.uiObj.fs, order=self.filt_order)
        self.ppg1_filt_obj = lFilter(self.ppg_lowcut, self.ppg_highcut, self.uiObj.fs, order=self.filt_order)
        self.ppg2_filt_obj = lFilter(self.ppg_lowcut, self.ppg_highcut, self.uiObj.fs, order=self.filt_order)

        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*self.uiObj.fs)
        self.eda_plot_signal = 1000 * np.ones(self.max_plot_time * self.uiObj.fs)
        self.resp_plot_signal = 1000 * np.ones(self.max_plot_time * self.uiObj.fs)
        self.ppg1_plot_signal = 1000 * np.ones(self.max_plot_time * self.uiObj.fs)
        self.ppg2_plot_signal = 1000 * np.ones(self.max_plot_time * self.uiObj.fs)

        # The window
        self.fig, self.ax = plt.subplots(2, 2, figsize = (12.5, 7), layout="constrained")

        # self.ax[0, 0] settings
        (self.line1,) = self.ax[0, 0].plot(self.x_axis, self.eda_plot_signal, 'b', markersize=10, linestyle='solid')
        self.ax[0, 0].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[0, 0].set_ylabel('EDA', fontsize=16)
        self.ax[0, 0].set_xlim(0, self.max_plot_time)
        self.ax[0, 0].set_ylim(0, 1)
        self.ax[0, 0].yaxis.set_ticks_position('left')
        self.ax[0, 0].xaxis.set_ticks_position('bottom')

        # self.ax[0, 1] settings
        (self.line2,) = self.ax[0, 1].plot(self.x_axis, self.resp_plot_signal, 'g', markersize=10, linestyle='solid')
        self.ax[0, 1].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[0, 1].set_ylabel('Resp', fontsize=16)
        self.ax[0, 1].set_xlim(0, self.max_plot_time)
        self.ax[0, 1].set_ylim(0, 1)
        self.ax[0, 1].yaxis.set_ticks_position('left')
        self.ax[0, 1].xaxis.set_ticks_position('bottom')

        # self.ax[1, 0] settings
        (self.line3,) = self.ax[1, 0].plot(self.x_axis, self.ppg1_plot_signal, 'r', markersize=10, linestyle='solid')
        self.ax[1, 0].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[1, 0].set_ylabel('PPG-Finger', fontsize=16)
        self.ax[1, 0].set_xlim(0, self.max_plot_time)
        self.ax[1, 0].set_ylim(0, 1)
        self.ax[1, 0].yaxis.set_ticks_position('left')
        self.ax[1, 0].xaxis.set_ticks_position('bottom')

        # self.ax[1, 1] settings
        (self.line4,) = self.ax[1, 1].plot(self.x_axis, self.ppg2_plot_signal, 'm', markersize=10, linestyle='solid')
        self.ax[1, 1].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[1, 1].set_ylabel('PPG-Ear', fontsize=16)
        self.ax[1, 1].set_xlim(0, self.max_plot_time)
        self.ax[1, 1].set_ylim(0, 1)
        self.ax[1, 1].yaxis.set_ticks_position('left')
        self.ax[1, 1].xaxis.set_ticks_position('bottom')

        FigureCanvas.__init__(self, self.fig)
        TimedAnimation.__init__(self, self.fig, interval=int(round(10*1000.0/self.uiObj.fs)), blit = True)  # figure update frequency: 1/10th of sampling rate
        return


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * self.uiObj.fs)))

    def _init_draw(self):
        return (self.line1, self.line2, self.line3, self.line4, )

    def reset_draw(self):
        self.count_frame = 0 # self.max_plot_time * self.uiObj.fs

        return


    def addData(self, value):
        global live_acquisition_flag
        eda_val, resp_val, ppg1_val, ppg2_val, _ = value
        eda_filtered = self.eda_filt_obj.lfilt(eda_val)
        resp_filtered = self.resp_filt_obj.lfilt(resp_val)
        ppg1_filtered = self.ppg1_filt_obj.lfilt(ppg1_val)
        ppg2_filtered = self.ppg2_filt_obj.lfilt(ppg2_val)

        if live_acquisition_flag: 
            self.count_frame += 1
            self.eda_plot_signal = np.roll(self.eda_plot_signal, -1)
            self.eda_plot_signal[-1] = eda_filtered

            self.resp_plot_signal = np.roll(self.resp_plot_signal, -1)
            self.resp_plot_signal[-1] = resp_filtered

            self.ppg1_plot_signal = np.roll(self.ppg1_plot_signal, -1)
            self.ppg1_plot_signal[-1] = ppg1_filtered

            self.ppg2_plot_signal = np.roll(self.ppg2_plot_signal, -1)
            self.ppg2_plot_signal[-1] = ppg2_filtered

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
        global live_acquisition_flag
        if live_acquisition_flag:   

            if self.count_frame >= (self.measure_time * self.uiObj.fs):
                self.count_frame = 0
                self.ax[0, 0].set_ylim(np.min(self.eda_plot_signal), np.max(self.eda_plot_signal))
                self.ax[0, 1].set_ylim(np.min(self.resp_plot_signal), np.max(self.resp_plot_signal))
                self.ax[1, 0].set_ylim(np.min(self.ppg1_plot_signal), np.max(self.ppg1_plot_signal))
                self.ax[1, 1].set_ylim(np.min(self.ppg2_plot_signal), np.max(self.ppg2_plot_signal))

            if self.event_toggle:
                if self.uiObj.event_status:
                    self.line1.set_linestyle((0, (5, 5)))
                    self.line2.set_linestyle((0, (5, 5)))
                    self.line3.set_linestyle((0, (5, 5)))
                    self.line4.set_linestyle((0, (5, 5)))
                else:
                    self.line1.set_linestyle((0, ()))
                    self.line2.set_linestyle((0, ()))
                    self.line3.set_linestyle((0, ()))
                    self.line4.set_linestyle((0, ()))
                self.event_toggle = False

            self.line1.set_ydata(self.eda_plot_signal)
            self.line2.set_ydata(self.resp_plot_signal)
            self.line3.set_ydata(self.ppg1_plot_signal)
            self.line4.set_ydata(self.ppg2_plot_signal)

            self._drawn_artists = [self.line1, self.line2, self.line3, self.line4]

        return



# Setup a signal slot mechanism, to send data to GUI in a thread-safe way.
class Communicate(QObject):
    data_signal = Signal(list)


def ppgDataSendLoop(addData_callbackFunc, spObj):
    global live_acquisition_flag
    # Setup the signal-slot mechanism.
    mySrc = Communicate()
    mySrc.data_signal.connect(addData_callbackFunc)
    edaVal = 0
    respVal = 0
    ppgVal1 = 0
    ppgVal2 = 0
    tsVal = 0
    buffersize = 5*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n

    while(True):
        if live_acquisition_flag and spObj.ser.is_open:
            #Read data from serial port
            try:
                serial_data = spObj.ser.readline(buffersize)
                serial_data = serial_data.split(b'\r\n')
                serial_data = serial_data[0].split(b',')
                #print(serial_data)
            except:
                serial_data = []
                print('Serial port not open')

            if len(serial_data) == 5:
                try:
                    edaVal = float(serial_data[0])
                    respVal = float(serial_data[1])
                    ppgVal1 = float(serial_data[2])
                    ppgVal2 = float(serial_data[3])
                    tsVal = float(serial_data[4])
                except:
                    # ppgVal1 = ppgVal2 = edaVal = respVal = tsVal = 0
                    print('error in reading data', serial_data)

                # time.sleep(0.01)
                mySrc.data_signal.emit([edaVal, respVal, ppgVal1, ppgVal2, tsVal])  # <- Here you emit a signal!l
            else:
                print('Serial data:', serial_data)
        else:
            time.sleep(1)

def main(app):
    # app.setStyle('Fusion')
    widget = PPG()
    widget.show()
    ret = app.exec()
    del widget
    # sys.exit(ret)
    return

if __name__ == '__main__':
    # Create the application instance.
    app = QApplication([])
    main(app)
