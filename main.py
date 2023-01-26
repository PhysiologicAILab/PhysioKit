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
from datetime import datetime

global live_acquisition_flag, hold_acquisition_thread, nChannels
live_acquisition_flag = False
hold_acquisition_thread = True
nChannels = 4


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
        self.csv_header = ['']
        self.ui.write_eventcode = ''
        self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(self.csvfile)

        ui_file.close()



    def update_exp_condition(self):
        self.ui.curr_exp_condition = self.ui.conditions[self.ui.listWidget_expConditions.currentRow()]
        self.ui.label_status.setText("Experiment Condition Selected: " + self.ui.curr_exp_condition)


    def load_exp_params(self):
        global nChannels
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

            self.ui.channels = self.ui.params_dict["exp"]["channels"]
            nChannels = len(self.ui.channels)
            self.ui.channel_types = self.ui.params_dict["exp"]["channel_types"]
            self.ui.channel_plot_colors = self.ui.params_dict["exp"]["channel_plot_colors"]
            self.csv_header = self.ui.channels + ["arduino_ts", "event_code"]
            self.writer.writerow(self.csv_header)

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
            self.writer.writerow(value + [self.ui.write_eventcode])

            if self.ui.timed_acquisition:
                elapsed_time = (datetime.now() - self.ui.record_start_time).total_seconds()
                # self.ui.label_status.setText("Time remaining: " + str(self.ui.max_acquisition_time - elapsed_time))
                if (elapsed_time >= self.ui.max_acquisition_time):
                    self.ui.data_record_flag = False
                    stop_record_thread = threading.Thread(name='stop_record', target=self.stop_record_process, daemon=True)
                    stop_record_thread.start()
        return

    
    def stop_record_process(self):
        if not self.csvfile.closed:
            self.csvfile.close()
            time.sleep(1)
        self.save_file_path = os.path.join(self.ui.data_root_dir, self.ui.pid + "_" +
                                        self.ui.curr_exp_name + '_' + self.ui.curr_exp_condition + '_' + self.ui.utc_sec + '.csv')
        if os.path.exists(self.temp_filename):
            shutil.move(self.temp_filename, self.save_file_path)
            self.ui.label_status.setText("Recording stopped and data saved for: Exp - " + self.ui.curr_exp_name + "; Condition - " + self.ui.curr_exp_condition)
        else:
            self.ui.label_status.setText("Error saving data")

        self.ui.pushButton_record_data.setText("Start Recording")
        
        self.ui.lineEdit_Event.setEnabled(False)
        self.ui.pushButton_Event.setEnabled(False)

        if self.ui.event_status:
            self.ui.event_status = False
            self.myFig.event_toggle = True

        # prepare for next recording
        self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
        self.writer = csv.writer(self.csvfile)
        self.writer.writerow(self.csv_header)


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
            self.ui.write_eventcode = self.ui.eventcode
            self.ui.pushButton_Event.setText("Stop Marking")
        else:
            self.ui.event_status = False
            self.ui.write_eventcode = ''
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
                if not self.csvfile.closed:
                    self.csvfile.close()
                os.remove(self.temp_filename)

            self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
            self.writer = csv.writer(self.csvfile)
            self.writer.writerow(self.csv_header)

            live_acquisition_flag = False
            self.ui.pushButton_record_data.setEnabled(False)
            self.ui.pushButton_start_live_acquisition.setText('Start Live Acquisition')

            self.ui.listWidget_expConditions.setEnabled(True)


    
    def record_data(self):
        if not self.ui.data_record_flag:
            if not os.path.exists(self.temp_filename):
                self.csvfile = open(self.temp_filename, 'w', encoding="utf", newline="")
                self.writer = csv.writer(self.csvfile)
                self.writer.writerow(self.csv_header)

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
            stop_record_thread = threading.Thread(name='stop_record', target=self.stop_record_process, daemon=True)
            stop_record_thread.start()


class LivePlotFigCanvas(FigureCanvas, TimedAnimation):
    def __init__(self, uiObj):
        self.uiObj = uiObj
        self.exception_count = 0
        global nChannels

        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
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
        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*self.uiObj.fs)

        self.filt_objs = {}
        self.plot_signals = []
        self.axs = {}
        self.lines = {}

        self.fig = Figure(figsize=(12.5, 7), layout="constrained")

        for nCh in range(self.nChannels):
            if self.uiObj.channel_types[nCh] == 'eda':
                self.filt_objs[str(nCh)] = lFilter_moving_average(window_size=self.moving_average_window_size)
            elif self.uiObj.channel_types[nCh] == 'resp':
                self.filt_objs[str(nCh)] = lFilter(self.resp_lowcut, self.resp_highcut, self.uiObj.fs, order=self.filt_order)
            elif self.uiObj.channel_types[nCh] == 'ppg':
                self.filt_objs[str(nCh)] = lFilter(self.ppg_lowcut, self.ppg_highcut, self.uiObj.fs, order=self.filt_order)

            self.plot_signals.append(1000 * np.ones(self.max_plot_time * self.uiObj.fs))

            if self.nChannels == self.max_plot_channels:
                self.axs[str(nCh)] = self.fig.add_subplot(2, 2, nCh+1)
            else:
                self.axs[str(nCh)] = self.fig.add_subplot(self.nChannels, 1, nCh+1)

            (self.lines[str(nCh)],) = self.axs[str(nCh)].plot(self.x_axis, self.plot_signals[nCh], self.uiObj.channel_plot_colors[nCh], markersize=10, linestyle='solid')
            self.axs[str(nCh)].set_xlabel('Time (seconds)', fontsize=16)
            self.axs[str(nCh)].set_ylabel(self.uiObj.channels[nCh], fontsize=16)
            self.axs[str(nCh)].set_xlim(0, self.max_plot_time)
            self.axs[str(nCh)].set_ylim(0, 1)
            self.axs[str(nCh)].yaxis.set_ticks_position('left')
            self.axs[str(nCh)].xaxis.set_ticks_position('bottom')

        FigureCanvas.__init__(self, self.fig)
        TimedAnimation.__init__(self, self.fig, interval=int(round(10*1000.0/self.uiObj.fs)), blit = True)  # figure update frequency: 1/10th of sampling rate
        return


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * self.uiObj.fs)))


    def _init_draw(self):
        lines = []
        for nCh in range(self.nChannels):
            lines.append(self.lines[str(nCh)])
        lines = tuple(lines)
        return (lines)


    def reset_draw(self):
        self.count_frame = 0 # self.max_plot_time * self.uiObj.fs

        return


    def addData(self, value):
        global live_acquisition_flag
        val_filt = []
        for nCh in range(self.nChannels):
            val_filt.append(self.filt_objs[str(nCh)].lfilt(value[nCh]))

        if live_acquisition_flag: 
            self.count_frame += 1
            for nCh in range(self.nChannels):
                self.plot_signals[nCh] = np.roll(self.plot_signals[nCh], -1)
                self.plot_signals[nCh][-1] = val_filt[nCh]
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

                for nCh in range(self.nChannels):
                    self.axs[str(nCh)].set_ylim(np.min(self.plot_signals[nCh]), np.max(self.plot_signals[nCh]))

            if self.event_toggle:
                if self.uiObj.event_status:
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

            # self._drawn_artists = [self.line1, self.line2, self.line3, self.line4]

        return



# Setup a signal slot mechanism, to send data to GUI in a thread-safe way.
class Communicate(QObject):
    data_signal = Signal(list)


def ppgDataSendLoop(addData_callbackFunc, spObj):
    global live_acquisition_flag, hold_acquisition_thread, nChannels
    # Setup the signal-slot mechanism.
    mySrc = Communicate()
    mySrc.data_signal.connect(addData_callbackFunc)
    value = []
    buffersize = (nChannels + 1)*4*bytes.__sizeof__(bytes()) + 2*bytes.__sizeof__(bytes())    #4 sensor unsigned int and 1 tsVal unsigned long => 5 * 4 bytes + 2 bytes for \r\n

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

            try:
                value = []
                for nCh in range(nChannels + 1):
                    value.append(float(serial_data[nCh]))
            except:
                print('error in reading data', serial_data)
                try:
                    assert len(serial_data) == (nChannels + 1)  #data channels + time_stamp
                except:
                    print('Mismatch in the number of channels specified in JSON file and the serial data received from Arduino or microcontroller')

            # time.sleep(0.01)
            mySrc.data_signal.emit(value)  # <- Here you emit a signal!l

        else:
            if not hold_acquisition_thread:
                break
            else:
                time.sleep(1)

def main(app):
    if osname == 'Darwin':
        app.setStyle('Fusion')
    
    widget = PPG()
    widget.show()
    ret = app.exec()
    del widget

    fn = "temp.csv"
    if os.path.exists(fn):
        os.remove(fn)

    # sys.exit(ret)
    return

if __name__ == '__main__':
    # Create the application instance.
    app = QApplication([])
    main(app)
