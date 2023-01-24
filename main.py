# This Python file uses the following encoding: utf-8
import threading
import time
import json

import matplotlib.pyplot as plt

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QDialog, QLineEdit, QDialogButtonBox, QFormLayout
from PySide6.QtCore import QFile, QObject, Signal
from PySide6.QtUiTools import QUiLoader
from PySide6.QtGui import QFileDialog

from datetime import datetime
import numpy as np
# import heartpy as hp

# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
# from matplotlib.lines import Line2D
from matplotlib.animation import TimedAnimation
# from matplotlib.figure import Figure

import os
import numpy as np
import csv

from utils.data_processing_lib import lFilter, lFilter_moving_average
from utils.devices import serialPort
from datetime import datetime
# import calendar 

global live_acquisition_flag
live_acquisition_flag = False


class InputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.exp_name = QLineEdit(self)
        self.exp_conditions = QLineEdit(self)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self);

        layout = QFormLayout(self)
        layout.addRow("Experiment Name", self.exp_name)
        layout.addRow("Experiment Conditions \n (comma-separated)", self.exp_conditions)
        layout.addWidget(buttonBox)

        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

    def getInputs(self):
        return (self.exp_name.text(), self.exp_conditions.text())


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

        self.ui.baudrate = 2000000
        self.ui.spObj = serialPort(self.ui.baudrate )
        self.ui.ser_port_names = []
        self.ui.ser_open_status = False
        self.ui.curr_ser_port_name = ''
        for port, desc, hwid in sorted(self.ui.spObj.ports):
            # print("{}: {} [{}]".format(port, desc, hwid))
            self.ui.ser_port_names.append(port)
        
        self.ui.comboBox_comport.addItems(self.ui.ser_port_names)
        self.ui.curr_ser_port_name = self.ui.ser_port_names[0]
        self.ui.pushButton_connect.setEnabled(True)
        self.ui.label_status.setText("Serial port specified: " + self.ui.curr_ser_port_name +
                                     "; Select experiment and condition to start recording data.")

        self.ui.comboBox_comport.currentIndexChanged.connect(self.update_serial_port)
        self.ui.pushButton_connect.pressed.connect(self.connect_serial_port)
        self.ui.pushButton_start_live_acquisition.pressed.connect(self.start_acquisition)
        self.ppgDataLoop_started = False

        self.ui.comboBox_expName.currentIndexChanged.connect(self.update_expName)
        self.ui.pushButton_addExp.pressed.connect(self.add_exp)

        self.ui.pid = ""
        self.ui.lineEdit_PID.textChanged.connect(self.update_pid)

        self.ui.pushButton_acq_params.pressed.connect(self.load_acq_params)

        self.ui.data_record_flag = False
        self.ui.data_root_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(self.ui.data_root_dir):
            os.makedirs(self.ui.data_root_dir)
        
        self.ui.pushButton_record_data.pressed.connect(self.record_data)
        self.ui.exp_names = [self.ui.comboBox_expName.itemText(i) for i in range(self.ui.comboBox_expName.count())]
        self.ui.utc_timestamp_featDict = datetime.utcnow()

        self.ui.curr_exp_name = self.ui.exp_names[0]
        self.ui.exp_conds_dict = {}
        self.ui.conditions = [self.ui.listWidget_expConditions.item(x).text() for x in range(self.ui.listWidget_expConditions.count())]
        self.ui.exp_conds_dict[self.ui.curr_exp_name] = self.ui.conditions

        # # Place the matplotlib figure
        self.ui.fs = 250 #sampling rate
        self.myFig = LivePlotFigCanvas(uiObj=self.ui)
        self.graphic_scene = QGraphicsScene()
        self.graphic_scene.addWidget(self.myFig)
        self.ui.graphicsView.setScene(self.graphic_scene)
        self.ui.graphicsView.show()

        # Add the callbackfunc
        self.ppgDataLoop = threading.Thread(name='ppgDataLoop', target=ppgDataSendLoop, daemon=True, args=(
            self.addData_callbackFunc, self.ui.spObj))

        self.ui.listWidget_expConditions.currentItemChanged.connect(self.update_exp_condition)
        self.ui.curr_exp_condition = self.ui.conditions[0]

        ui_file.close()


    def load_acq_params(self):
        fname = QFileDialog.getOpenFileName()
        with open(fname) as json_file:
            self.ui.acq_dict = json.load(json_file)
        
        self.ui.fs = int(self.ui.acq_dict["acq_params"]["fs"])
        self.ui.baudrate = int(self.ui.acq_dict["acq_params"]["baudrate"])


    def addData_callbackFunc(self, value):
        # print("Add data: " + str(value))
        self.myFig.addData(value)
        
        if self.ui.data_record_flag:
            eda_val, resp_val, ppg1_val, ppg2_val, ts_val = value
            self.writer.writerow([eda_val, resp_val, ppg1_val, ppg2_val, ts_val])
        return

    def add_exp(self):
        exp_dlg = InputDialog()
        exp_dlg.exec()
        exp_name, exp_conds = exp_dlg.getInputs()
        exp_conds_temp_list = exp_conds.split(sep=',')
        exp_conds_temp_list = [d.strip() for d in exp_conds_temp_list]
        if len(exp_conds_temp_list) > 0:
            self.ui.exp_names.append(exp_name)
            self.ui.comboBox_expName.addItem(exp_name)
            self.ui.exp_conds_dict[exp_name] = exp_conds.split(sep=',')
            for i in range(len(self.ui.exp_conds_dict[exp_name])):
                self.ui.exp_conds_dict[exp_name][i] = self.ui.exp_conds_dict[exp_name][i].strip()
        return

    def update_expName(self):
        self.ui.curr_exp_name = self.ui.exp_names[self.ui.comboBox_expName.currentIndex()]
        self.ui.label_status.setText("Experiment changed to: " + self.ui.curr_exp_name)
        self.ui.listWidget_expConditions.clear()
        self.ui.listWidget_expConditions.addItems(self.ui.exp_conds_dict[self.ui.curr_exp_name])

        # self.ui.conditions = [self.ui.listWidget_expConditions.item(x).text() for x in range(self.ui.listWidget_expConditions.count())]
        self.ui.conditions = self.ui.exp_conds_dict[self.ui.curr_exp_name]
        self.ui.curr_exp_condition = self.ui.conditions[0]


    def update_pid(self, text):
        self.ui.pid = text

    def update_serial_port(self):
        self.ui.curr_ser_port_name = self.ui.ser_port_names[self.ui.comboBox_comport.currentIndex()]
        self.ui.label_status.setText("Serial port specified: " + self.ui.curr_ser_port_name)

    def connect_serial_port(self):
        if not self.ui.ser_open_status:
            self.ui.ser_open_status = self.ui.spObj.connectPort(self.ui.curr_ser_port_name)
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
            self.ui.pushButton_addExp.setEnabled(False)
            self.ui.comboBox_expName.setEnabled(False)
            self.ui.listWidget_expConditions.setEnabled(False)

            self.ui.pushButton_record_data.setEnabled(True)

        else:
            self.ui.label_status.setText("Live acquisition stopped.")
            # To reset the graph and clear the values
            
            self.myFig.reset_draw()
            
            live_acquisition_flag = False
            self.ui.pushButton_record_data.setEnabled(False)
            self.ui.pushButton_start_live_acquisition.setText('Start Live Acquisition')

            self.ui.pushButton_addExp.setEnabled(True)
            self.ui.comboBox_expName.setEnabled(True)
            self.ui.listWidget_expConditions.setEnabled(True)

    def update_exp_condition(self):
        self.ui.curr_exp_condition = self.ui.conditions[self.ui.listWidget_expConditions.currentRow()]
        self.ui.label_status.setText("Experiment Condition Selected: " + self.ui.curr_exp_condition)

    def record_data(self):

        if not self.ui.data_record_flag:
            self.ui.data_record_flag = True

            utc_sec = str((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())
            utc_sec = utc_sec.replace('.', '_')
            self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +  self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + utc_sec + '.csv')

            self.csvfile = open(self.save_file_path, 'w', encoding="utf", newline="")
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow(["eda", "resp", "ppg1", "ppg2", "arduino_ts"])

            # self.ui.utc_timestamp_signal = datetime.utcnow()
            self.ui.pushButton_record_data.setText("Stop Recording")
            self.ui.label_status.setText("Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
        else:
            self.csvfile.close()
            self.ui.data_record_flag = False
            self.ui.pushButton_record_data.setText("Start Recording")
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)


class LivePlotFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self, uiObj):
        self.uiObj = uiObj
        self.exception_count = 0

        # The data
        self.max_time = 20 # 30 second time window
        self.measure_time = 1  # moving max_time sample by 1 sec.
        self.count_frame = 0
        
        resp_lowcut = 0.1
        resp_highcut = 0.4
        ppg_lowcut = 0.8
        ppg_highcut = 3.5
        filt_order = 2
        moving_average_window_size = int(self.uiObj.fs/4.0)
        self.eda_filt_obj = lFilter_moving_average(window_size=moving_average_window_size)
        self.resp_filt_obj = lFilter(resp_lowcut, resp_highcut, self.uiObj.fs, order=filt_order)
        self.ppg1_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.uiObj.fs, order=filt_order)
        self.ppg2_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.uiObj.fs, order=filt_order)

        self.x_axis = np.linspace(0, self.max_time, self.max_time*self.uiObj.fs)
        self.eda_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.resp_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.ppg1_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.ppg2_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)

        eda_temp = [self.eda_filt_obj.lfilt(d) for d in self.eda_plot_signal]
        resp_temp = [self.resp_filt_obj.lfilt(d) for d in self.resp_plot_signal]
        ppg1_temp = [self.ppg1_filt_obj.lfilt(d) for d in self.ppg1_plot_signal]
        ppg2_temp = [self.ppg2_filt_obj.lfilt(d) for d in self.ppg2_plot_signal]

        # The window
        self.fig, self.ax = plt.subplots(2, 2, figsize = (12.5, 7), layout="constrained")

        # self.ax[0, 0] settings
        (self.line1,) = self.ax[0, 0].plot(self.x_axis, self.eda_plot_signal, 'r', markersize=10)
        self.ax[0, 0].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[0, 0].set_ylabel('EDA', fontsize=16)
        self.ax[0, 0].set_xlim(0, self.max_time)
        self.ax[0, 0].set_ylim(0, 1)
        self.ax[0, 0].yaxis.set_ticks_position('left')
        self.ax[0, 0].xaxis.set_ticks_position('bottom')

        # self.ax[0, 1] settings
        (self.line2,) = self.ax[0, 1].plot(self.x_axis, self.resp_plot_signal, 'g', markersize=10)
        self.ax[0, 1].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[0, 1].set_ylabel('Resp', fontsize=16)
        self.ax[0, 1].set_xlim(0, self.max_time)
        self.ax[0, 1].set_ylim(0, 1)
        self.ax[0, 1].yaxis.set_ticks_position('left')
        self.ax[0, 1].xaxis.set_ticks_position('bottom')

        # self.ax[1, 0] settings
        (self.line3,) = self.ax[1, 0].plot(self.x_axis, self.ppg1_plot_signal, 'b', markersize=10)
        self.ax[1, 0].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[1, 0].set_ylabel('PPG-Finger', fontsize=16)
        self.ax[1, 0].set_xlim(0, self.max_time)
        self.ax[1, 0].set_ylim(0, 1)
        self.ax[1, 0].yaxis.set_ticks_position('left')
        self.ax[1, 0].xaxis.set_ticks_position('bottom')

        # self.ax[1, 1] settings
        (self.line4,) = self.ax[1, 1].plot(self.x_axis, self.ppg2_plot_signal, 'm', markersize=10)
        self.ax[1, 1].set_xlabel('Time (seconds)', fontsize=16)
        self.ax[1, 1].set_ylabel('PPG-Ear', fontsize=16)
        self.ax[1, 1].set_xlim(0, self.max_time)
        self.ax[1, 1].set_ylim(0, 1)
        self.ax[1, 1].yaxis.set_ticks_position('left')
        self.ax[1, 1].xaxis.set_ticks_position('bottom')

        FigureCanvas.__init__(self, self.fig)
        TimedAnimation.__init__(self, self.fig, interval=int(round(10*1000.0/self.uiObj.fs)), blit = True)
        return


    def new_frame_seq(self):
        return iter(range(int(self.max_time * self.uiObj.fs)))

    def _init_draw(self):
        return (self.line1, self.line2, self.line3, self.line4, )

    def reset_draw(self):
        self.count_frame = 0 # self.max_time * self.uiObj.fs

        self.x_axis = np.linspace(0, self.max_time, self.max_time*self.uiObj.fs)
        self.eda_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.resp_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.ppg1_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)
        self.ppg2_plot_signal = 1000 * np.ones(self.max_time * self.uiObj.fs)

        resp_lowcut = 0.1
        resp_highcut = 0.4
        ppg_lowcut = 0.8
        ppg_highcut = 3.5
        filt_order = 2
        moving_average_window_size = int(self.uiObj.fs/4.0)
        self.ppg1_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.uiObj.fs, order=filt_order)
        self.ppg2_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.uiObj.fs, order=filt_order)
        self.resp_filt_obj = lFilter(resp_lowcut, resp_highcut, self.uiObj.fs, order=filt_order)
        self.eda_filt_obj = lFilter_moving_average(window_size=moving_average_window_size)

        temp_eda = [self.eda_filt_obj.lfilt(d) for d in self.eda_plot_signal]
        temp_resp = [self.resp_filt_obj.lfilt(d) for d in self.resp_plot_signal]
        temp_ppg1 = [self.ppg1_filt_obj.lfilt(d) for d in self.ppg1_plot_signal]
        temp_ppg2 = [self.ppg2_filt_obj.lfilt(d) for d in self.ppg2_plot_signal]

        return


    def addData(self, value):
        self.count_frame += 1
        eda_val, resp_val, ppg1_val, ppg2_val, _ = value
        eda_filtered = self.eda_filt_obj.lfilt(eda_val)
        resp_filtered = self.resp_filt_obj.lfilt(resp_val)
        ppg1_filtered = self.ppg1_filt_obj.lfilt(ppg1_val)
        ppg2_filtered = self.ppg2_filt_obj.lfilt(ppg2_val)

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
            print(str(self.exception_count))
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
    buffersize = 1024

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
