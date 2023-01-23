# This Python file uses the following encoding: utf-8
import threading
import time

import matplotlib.pyplot as plt

from PySide6.QtWidgets import QApplication, QWidget, QGraphicsScene, QDialog, QLineEdit, QDialogButtonBox, QFormLayout
from PySide6.QtCore import QFile, QObject, Signal
from PySide6.QtUiTools import QUiLoader

from datetime import datetime
import numpy as np
from utils.data_processing_lib import lFilter, lFilter_moving_average
import heartpy as hp

# from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.lines import Line2D
from matplotlib.animation import TimedAnimation
from matplotlib.figure import Figure

import os
import numpy as np

from devices import serialPort
from datetime import datetime
import calendar

global raw_ppg_signal_1, raw_ppg_signal_2
global raw_resp, raw_eda
global utc_time_stamp, arduino_time
live_acquisition_flag = False
update_bar_plot_axis = False

raw_resp = []
raw_eda = []
raw_ppg_signal_1 = []
raw_ppg_signal_2 = []
utc_time_stamp = []
arduino_time = []

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
        global raw_ppg_signal_1, raw_ppg_signal_2
        global raw_resp, raw_eda

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

        self.ui.data_record_flag = False
        self.ui.data_root_dir = os.path.join(os.getcwd(), 'data')
        if not os.path.exists(self.ui.data_root_dir):
            os.makedirs(self.ui.data_root_dir)
        self.ui.pushButton_record_data.pressed.connect(self.record_data)
        raw_ppg_signal_1 = []
        raw_ppg_signal_2 = []
        raw_resp = []
        raw_eda = []

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

    def addData_callbackFunc(self, value):
        # print("Add data: " + str(value))
        self.myFig.addData(value)      
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
            self.myFig.ppg1_plot_signal = (self.myFig.x_axis * 0.0) + 50
            self.myFig.ppg2_plot_signal = (self.myFig.x_axis * 0.0) + 50
            self.myFig.resp_plot_signal = (self.myFig.x_axis * 0.0) + 50
            self.myFig.eda_plot_signal = (self.myFig.x_axis * 0.0) + 50

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
            self.ui.utc_timestamp_signal = datetime.utcnow()
            self.ui.pushButton_record_data.setText("Stop Recording")
            self.ui.label_status.setText("Recording started for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
        else:
            th = threading.Thread(target=self.save_raw_signal)
            th.start()
            self.ui.data_record_flag = False
            self.ui.pushButton_record_data.setText("Start Recording")
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)

    def save_raw_signal(self):
        global raw_ppg_signal_1, raw_ppg_signal_2
        global raw_resp, raw_eda
        global utc_time_stamp, arduino_time

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                                    'raw_eda_' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(raw_eda))

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                                    'raw_resp_' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(raw_resp))

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                            'raw_ppg1_' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(raw_ppg_signal_1))

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                            'raw_ppg2_' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(raw_ppg_signal_2))

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                                    'time_stamp' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(utc_time_stamp))

        fname_signal = os.path.join(self.ui.data_root_dir, self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' +
                                    'arduino_time' + str(calendar.timegm(self.ui.utc_timestamp_signal.timetuple())) + '.npy')
        np.save(fname_signal, np.array(arduino_time))

        raw_resp = []
        raw_eda = []
        raw_ppg_signal_1 = []
        raw_ppg_signal_2 = []
        utc_time_stamp = []
        arduino_time = []



class LivePlotFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self, uiObj):
        self.uiObj = uiObj
        self.added_ppg1_data = []
        self.added_ppg2_data = []
        self.added_resp_data = []
        self.added_eda_data = []
        self.exception_count = 0
        # print(matplotlib.__version__)
        # The data
        self.max_time = 20 # 30 second time window
        self.measure_time = 1  # moving max_time sample by 1 sec.
        self.normalizing_time = 10  # moving max_time sample by 1 sec.
        self.xlim = self.max_time*self.uiObj.fs
        self.x_axis = np.linspace(0, self.xlim - 1, self.xlim)
        self.ppg1_plot_signal = (self.x_axis * 0.0) + 50
        self.ppg2_plot_signal = (self.x_axis * 0.0) + 50
        self.resp_plot_signal = (self.x_axis * 0.0) + 50
        self.eda_plot_signal = (self.x_axis * 0.0) + 50
        self.x_axis = self.x_axis/self.uiObj.fs
        # The window
        self.fig = Figure(figsize=(22,14), dpi=50, tight_layout=True)

        self.ax1 = self.fig.add_subplot(3, 1, 1)
        # self.ax1 settings
        self.ax1.set_xlabel('Time (seconds)', fontsize=24)
        self.ax1.set_ylabel('PPG Signal', fontsize=24)
        self.line1 = Line2D([], [], color='blue')
        self.line1_tail = Line2D([], [], color='red', linewidth=3)
        self.line1_head = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        self.ax1.add_line(self.line1)
        self.ax1.add_line(self.line1_tail)
        self.ax1.add_line(self.line1_head)
        self.ax1.set_xlim(0, self.max_time)
        # self.ax1.autoscale(enable=True, axis='y', tight=True)
        self.ax1.set_ylim(-100, 200)

        # # Hide the right and top spines
        # self.ax1.spines['right'].set_visible(False)
        # self.ax1.spines['top'].set_visible(False)

        # Only show ticks on the left and bottom spines
        self.ax1.yaxis.set_ticks_position('left')
        self.ax1.xaxis.set_ticks_position('bottom')


        self.ax2 = self.fig.add_subplot(3, 1, 2)
        # self.ax2 settings
        self.ax2.set_xlabel('Time (seconds)', fontsize=24)
        self.ax2.set_ylabel('Respiratory Signal', fontsize=24)
        self.line2 = Line2D([], [], color='blue')
        self.line2_tail = Line2D([], [], color='red', linewidth=3)
        self.line2_head = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        self.ax2.add_line(self.line2)
        self.ax2.add_line(self.line2_tail)
        self.ax2.add_line(self.line2_head)
        self.ax2.set_xlim(0, self.max_time)
        # self.ax2.autoscale(enable=True, axis='y', tight=True)
        self.ax2.set_ylim(-100, 200)

        # # Hide the right and top spines
        # self.ax2.spines['right'].set_visible(False)
        # self.ax2.spines['top'].set_visible(False)

        # Only show ticks on the left and bottom spines
        self.ax2.yaxis.set_ticks_position('left')
        self.ax2.xaxis.set_ticks_position('bottom')


        self.ax3 = self.fig.add_subplot(3, 1, 3)
        # self.ax3 settings
        self.ax3.set_xlabel('Time (seconds)', fontsize=24)
        self.ax3.set_ylabel('Electrodermal Activity Signal', fontsize=24)
        self.line3 = Line2D([], [], color='blue')
        self.line3_tail = Line2D([], [], color='red', linewidth=3)
        self.line3_head = Line2D([], [], color='red', marker='o', markeredgecolor='r')
        self.ax3.add_line(self.line3)
        self.ax3.add_line(self.line3_tail)
        self.ax3.add_line(self.line3_head)
        self.ax3.set_xlim(0, self.max_time)
        # self.ax3.autoscale(enable=True, axis='y', tight=True)
        self.ax3.set_ylim(-100, 200)

        # # Hide the right and top spines
        # self.ax3.spines['right'].set_visible(False)
        # self.ax3.spines['top'].set_visible(False)

        # Only show ticks on the left and bottom spines
        self.ax3.yaxis.set_ticks_position('left')
        self.ax3.xaxis.set_ticks_position('bottom')

        FigureCanvas.__init__(self, self.fig)
        TimedAnimation.__init__(self, self.fig, interval=int(round(1000.0/self.uiObj.fs)), blit = True)

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
        self.count_frame = 0# self.max_time * self.uiObj.fs
        return

    def new_frame_seq(self):
        return iter(range(self.x_axis.size))

    def _init_draw(self):
        lines = [self.line1, self.line1_tail, self.line1_head, self.line2,
                     self.line2_tail, self.line2_head, self.line3, self.line3_tail, self.line3_head]
        for l in lines:
            l.set_data([], [])
        return

    def addData(self, value):
        global raw_resp, raw_eda
        global raw_ppg_signal_1, raw_ppg_signal_2
        global utc_time_stamp, arduino_time
        eda_val, resp_val, ppg1_val, ppg2_val, ts_val = value
        ppg1_filtered = self.ppg1_filt_obj.lfilt(ppg1_val)
        ppg2_filtered = self.ppg2_filt_obj.lfilt(ppg2_val)
        resp_filtered = self.resp_filt_obj.lfilt(resp_val)
        eda_filtered = self.eda_filt_obj.lfilt(eda_val)
        # self.added_ppg1_data.append(value)
        self.added_ppg1_data.append(ppg1_filtered)
        self.added_ppg2_data.append(ppg2_filtered)
        self.added_resp_data.append(resp_filtered)
        self.added_eda_data.append(eda_filtered)
        if self.uiObj.data_record_flag:
            raw_eda.append(eda_val) # raw signals saved without any filtering.
            raw_resp.append(resp_val)
            raw_ppg_signal_1.append(ppg1_val)
            raw_ppg_signal_2.append(ppg2_val) # raw signals saved without any filtering.
            utc_sec = (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
            utc_time_stamp.append(utc_sec)
            arduino_time.append(ts_val)

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
            margin = 2
            while(len(self.added_ppg1_data) > 0):

                self.ppg1_plot_signal = np.roll(self.ppg1_plot_signal, -1)
                self.ppg1_plot_signal[-1] = self.added_ppg1_data[-1]
                del(self.added_ppg1_data[0])

                self.ppg2_plot_signal = np.roll(self.ppg2_plot_signal, -1)
                self.ppg2_plot_signal[-1] = self.added_ppg2_data[-1]
                del(self.added_ppg2_data[0])

                self.resp_plot_signal = np.roll(self.resp_plot_signal, -1)
                self.resp_plot_signal[-1] = self.added_resp_data[-1]
                del(self.added_resp_data[0])

                self.eda_plot_signal = np.roll(self.eda_plot_signal, -1)
                self.eda_plot_signal[-1] = self.added_eda_data[-1]
                del(self.added_eda_data[0])

                self.count_frame += 1

            if self.count_frame >= (self.measure_time * self.uiObj.fs):
                self.count_frame = 0
                # self.ax1.autoscale(axis='y', tight=True)
                # self.ax2.autoscale(axis='y', tight=True)
                # self.ax3.autoscale(axis='y', tight=True)
                self.ax1.set_ylim(np.min(self.ppg1_plot_signal[-self.normalizing_time*self.uiObj.fs:]), np.max(
                    self.ppg1_plot_signal[-self.normalizing_time*self.uiObj.fs:]))
                
                self.ax2.set_ylim(np.min(self.resp_plot_signal[-self.normalizing_time*self.uiObj.fs:]), np.max(
                    self.resp_plot_signal[-self.normalizing_time*self.uiObj.fs:]))

                self.ax3.set_ylim(np.min(self.eda_plot_signal[-self.normalizing_time*self.uiObj.fs:]), np.max(
                    self.eda_plot_signal[-self.normalizing_time*self.uiObj.fs:]))

            self.line1.set_data(self.x_axis[0: self.x_axis.size - margin],
                                self.ppg1_plot_signal[0: self.x_axis.size - margin])
            self.line1_tail.set_data(np.append(self.x_axis[-10:-1 - margin], self.x_axis[-1 - margin]), np.append(
                self.ppg1_plot_signal[-10:-1 - margin], self.ppg1_plot_signal[-1 - margin]))
            self.line1_head.set_data(self.x_axis[-1 - margin], self.ppg1_plot_signal[-1 - margin])

            self.line2.set_data(self.x_axis[0: self.x_axis.size - margin],
                                self.resp_plot_signal[0: self.x_axis.size - margin])
            self.line2_tail.set_data(np.append(self.x_axis[-10:-1 - margin], self.x_axis[-1 - margin]), np.append(
                self.resp_plot_signal[-10:-1 - margin], self.resp_plot_signal[-1 - margin]))
            self.line2_head.set_data(
                self.x_axis[-1 - margin], self.resp_plot_signal[-1 - margin])

            self.line3.set_data(self.x_axis[0: self.x_axis.size - margin],
                                self.eda_plot_signal[0: self.x_axis.size - margin])
            self.line3_tail.set_data(np.append(self.x_axis[-10:-1 - margin], self.x_axis[-1 - margin]), np.append(
                self.eda_plot_signal[-10:-1 - margin], self.eda_plot_signal[-1 - margin]))
            self.line3_head.set_data(
                self.x_axis[-1 - margin], self.eda_plot_signal[-1 - margin])

            self._drawn_artists = [self.line1, self.line1_tail, self.line1_head, self.line2,
                                   self.line2_tail, self.line2_head, self.line3, self.line3_tail, self.line3_head]


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
        if live_acquisition_flag:
            #Read data from serial port
            serial_data = spObj.ser.readline(buffersize)
            serial_data = serial_data.split(b'\r\n')
            serial_data = serial_data[0].split(b',')
            #print(serial_data)

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
