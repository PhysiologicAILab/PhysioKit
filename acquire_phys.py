import numpy as np
import argparse
from utils.devices import serialPort
import threading
import time
import os
import csv

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

from PySide6.QtCore import QObject, Signal
import matplotlib.pyplot as plt
from datetime import datetime

from utils.data_processing_lib import lFilter, lFilter_moving_average


class Experiment:
    def __init__(self, args_parser) -> None:

        self.pid = args_parser.pid
        self.exp_name = args_parser.exp_name
        self.savedir = os.path.join(args_parser.savedir, self.pid)
        self.acquisition_duration = int(args_parser.duration)  # seconds
        self.start_time = None

        self.live_acquisition_flag = False
        self.buffersize = (4*float.__sizeof__(float) + 1*bytes.__sizeof__(bytes))
        print("Buffer size = ", self.buffersize)
        self.fs = 250     # samples per second
        self.baudrate = 2000000  # 38400

        self.ppg_plot_duration = 3   # seconds
        self.eda_plot_duration = 10  # seconds
        self.resp_plot_duration = 10  # seconds

        utc_sec = str((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())
        utc_sec = utc_sec.replace('.', '_')
        self.save_file_path = os.path.join(self.savedir, self.exp_name + '_' + utc_sec + '.csv')
        
        if not os.path.exists(self.savedir):
            os.makedirs(self.savedir)

        self.csvfile = open(self.save_file_path, 'w', encoding="utf", newline="")
        self.writer = csv.writer(self.csvfile)

        resp_lowcut = 0.15
        resp_highcut = 0.8
        ppg_lowcut = 0.8
        ppg_highcut = 3.5
        filt_order = 2
        moving_average_window_size = int(self.fs/4.0)
        self.ppg1_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.fs, order=filt_order)
        self.ppg2_filt_obj = lFilter(ppg_lowcut, ppg_highcut, self.fs, order=filt_order)
        self.resp_filt_obj = lFilter(resp_lowcut, resp_highcut, self.fs, order=filt_order)
        self.eda_filt_obj = lFilter_moving_average(window_size=moving_average_window_size)




class SerialCom:
    def __init__(self, expObj) -> None:
        self.serial_port_status = False
        self.expObj = expObj
        self.spObj = serialPort(baudrate=self.expObj.baudrate)

    def connect(self):
        port_indx = 0
        sorted_ports = sorted(self.spObj.ports)
        for port, desc, hwid in sorted_ports:
            # if 'usb' in port:
            # print("{}: {} [{}]".format(port, desc, hwid))
            print("{}:{}".format(port_indx + 1, port))
            port_indx += 1

        print('Enter the index of the port to be connected')
        indx = int(input()) - 1
        selected_ser_port_name = sorted_ports[indx].device
        try:
            osname = os.uname().sysname
            if osname == 'Darwin':
                selected_ser_port_name = selected_ser_port_name.replace('/dev/cu', '/dev/tty')
                print('MacOS Selected Serial Port Name:', selected_ser_port_name)
            else:
                print('Selected Serial Port Name:', selected_ser_port_name)
        except:
            pass

        self.serial_port_status = self.spObj.connectPort(selected_ser_port_name)
        print("Serial port is now connected:\n" + str(self.spObj.ser))


    def disconnect(self):
        if self.serial_port_status:
            self.spObj.disconnectPort()
            self.serial_port_status = False
            print("Serial port is now disconnected:\n" + str(self.spObj.ser))
        else:
            print("Port is not connected...")



# Setup a signal slot mechanism, to send data to GUI in a thread-safe way.
class Communicate(QObject):
    data_signal = Signal(list)


def acquisition_thread_function(addData_callbackFunc, serObj, expObj):
    mySrc = Communicate()
    mySrc.data_signal.connect(addData_callbackFunc)

    edaVal = 0
    respVal = 0
    ppgVal1 = 0
    ppgVal2 = 0

    print('Started acquisition thread with live_acquisition_flag = ', expObj.live_acquisition_flag)
    expObj.writer.writerow(["eda", "resp", "ppg1", "ppg2", "arduino_ts"])
    elapsed = 0
    
    while(True):
        
        if elapsed >= expObj.acquisition_duration:
            expObj.live_acquisition_flag = False
            plt.close()
            break
        # print(elapsed, expObj.acquisition_duration, '\r', end='')

        try:
            #Read data from serial port
            serial_data_raw = serObj.spObj.ser.readline(expObj.buffersize)
            serial_data = serial_data_raw.split(b'\r\n')
            serial_data = serial_data[0].split(b',')

            if len(serial_data) == 5:
                edaVal = float(serial_data[0])
                respVal = float(serial_data[1])
                ppgVal1 = float(serial_data[2])
                ppgVal2 = float(serial_data[3])
                arduino_ts = float(serial_data[4])

                if expObj.live_acquisition_flag:
                    expObj.writer.writerow([edaVal, respVal, ppgVal1, ppgVal2, arduino_ts])
                    elapsed = (datetime.now() - expObj.start_time).total_seconds()

                mySrc.data_signal.emit([edaVal, respVal, ppgVal1, ppgVal2])

            else:
                print('Serial data:', serial_data_raw)
                time.sleep(1)
                # serObj.spObj.reset_input_buffer()
        except:
            print('error in reading data')
            time.sleep(1)

    expObj.csvfile.close()
    print('Exiting acquisition thread')


class PhysPlot():
    def __init__(self, expObj) -> None:
        # self.fig, self.ax = plt.subplots(2, 2, figsize=(8*2, 5*2), layout='constrained')
        self.fig, self.ax = plt.subplots(2, 2, layout='constrained')
        self.fig.suptitle('Physiological Signals')
        self.plot_sampling_factor = 10.0
        self.N = np.linspace(0, expObj.acquisition_duration, int((expObj.fs * expObj.acquisition_duration)/self.plot_sampling_factor)+1)
        self.blit = True
        self.sample_count = 0
        self.expObj = expObj
        self.interv = int(self.plot_sampling_factor*1000.0/self.expObj.fs)

        self.xdata_ppg = np.linspace(-1*expObj.ppg_plot_duration, 0, expObj.ppg_plot_duration * expObj.fs)
        self.xdata_eda = np.linspace(-1*expObj.eda_plot_duration, 0, expObj.eda_plot_duration * expObj.fs)
        self.xdata_resp = np.linspace(-1*expObj.resp_plot_duration, 0, expObj.resp_plot_duration * expObj.fs)
        # self.xdata_ppg = np.linspace(0, expObj.ppg_plot_duration, expObj.ppg_plot_duration * expObj.fs)
        # self.xdata_eda = np.linspace(0, expObj.eda_plot_duration, expObj.eda_plot_duration * expObj.fs)
        # self.xdata_resp = np.linspace(0, expObj.resp_plot_duration, expObj.resp_plot_duration * expObj.fs)

        self.plot_eda = 1000 * np.ones(expObj.eda_plot_duration * expObj.fs)
        self.plot_resp = 1000 * np.ones(expObj.resp_plot_duration * expObj.fs)
        self.plot_ppg1 = 1000 * np.ones(expObj.ppg_plot_duration * expObj.fs)
        self.plot_ppg2 = 1000 * np.ones(expObj.ppg_plot_duration * expObj.fs)

        self.plot_eda = [self.expObj.eda_filt_obj.lfilt(d) for d in self.plot_eda]
        self.plot_resp = [self.expObj.resp_filt_obj.lfilt(d) for d in self.plot_resp]
        self.plot_ppg1 = [self.expObj.ppg1_filt_obj.lfilt(d) for d in self.plot_ppg1]
        self.plot_ppg2 = [self.expObj.ppg2_filt_obj.lfilt(d) for d in self.plot_ppg2]


    def init_func(self):
        (self.l1,) = self.ax[0, 0].plot([], [], 'r', markersize=10)
        self.ax[0, 0].set_title('EDA')
        self.ax[0, 0].set_xlim(0, self.expObj.eda_plot_duration)
        self.ax[0, 0].set_ylim(0, 1)
        self.ax[0, 0].set_xlabel('Time (seconds)')
        self.ax[0, 0].set_ylabel('Signal Amplitude')
        self.ax[0, 0].axis('equal')

        (self.l2,) = self.ax[0, 1].plot([], [], 'g', markersize=10)
        self.ax[0, 1].set_title('Resp')
        self.ax[0, 1].set_xlim(0, self.expObj.resp_plot_duration)
        self.ax[0, 1].set_ylim(0, 1)
        self.ax[0, 1].set_xlabel('Time (seconds)')
        self.ax[0, 1].set_ylabel('Signal Amplitude')
        self.ax[0, 1].axis('equal')

        (self.l3,) = self.ax[1, 0].plot([], [], 'b', markersize=10)
        self.ax[1, 0].set_title('PPG1')
        self.ax[1, 0].set_xlim(0, self.expObj.ppg_plot_duration)
        self.ax[1, 0].set_ylim(0, 1)
        self.ax[1, 0].set_xlabel('Time (seconds)')
        self.ax[1, 0].set_ylabel('Signal Amplitude')
        self.ax[1, 0].axis('equal')

        (self.l4,) = self.ax[1, 1].plot([], [], 'c', markersize=10)
        self.ax[1, 1].set_title('PPG2')
        self.ax[1, 1].set_xlim(0, self.expObj.ppg_plot_duration)
        self.ax[1, 1].set_ylim(0, 1)
        self.ax[1, 1].set_xlabel('Time (seconds)')
        self.ax[1, 1].set_ylabel('Signal Amplitude')
        self.ax[1, 1].axis('equal')

        # self.PhysPlotAnimation = FuncAnimation(self.fig, self.update, frames=self.N, interval=self.interv, blit=self.blit)
        # self.PhysPlotAnimation.event_source.start()

        self.fig.canvas.draw()
        return (self.l1, self.l2, self.l3, self.l4,)


    def update(self, frame):

        xmin_eda = np.min(self.xdata_eda)
        xmax_eda = np.max(self.xdata_eda)
        ymin_eda = np.min(self.plot_eda)
        ymax_eda = np.max(self.plot_eda)
        # print('xlims_eda', xmin_eda, xmax_eda)
        if xmax_eda > 0:
            self.ax[0, 0].set_xlim(xmin_eda, xmax_eda)
        if np.abs(ymax_eda - ymin_eda) > 0:
            self.ax[0, 0].set_ylim(ymin_eda, ymax_eda)

        xmin_resp = np.min(self.xdata_resp)
        xmax_resp = np.max(self.xdata_resp)
        ymin_resp = np.min(self.plot_resp)
        ymax_resp = np.max(self.plot_resp)
        # print('xlims_resp', xmin_resp, xmax_resp)
        if xmax_resp > 0:
            self.ax[0, 1].set_xlim(xmin_resp, xmax_resp)
        if np.abs(ymax_resp - ymin_resp) > 0:
            self.ax[0, 1].set_ylim(ymin_resp, ymax_resp)

        xmin_ppg = np.min(self.xdata_ppg)
        xmax_ppg = np.max(self.xdata_ppg)
        # print('xlims_ppg', xmin_ppg, xmax_ppg)
        if xmax_ppg > 0:
            self.ax[1, 0].set_xlim(xmin_ppg, xmax_ppg)
            self.ax[1, 1].set_xlim(xmin_ppg, xmax_ppg)

        ymin_ppg1 = np.min(self.plot_ppg1)
        ymax_ppg1 = np.max(self.plot_ppg1)
        # print('ylims_ppg1', ymin_ppg1, ymax_ppg1)
        if np.abs(ymax_ppg1 - ymin_ppg1) > 0:
            self.ax[1, 0].set_ylim(ymin_ppg1, ymax_ppg1)

        ymin_ppg2 = np.min(self.plot_ppg2)
        ymax_ppg2 = np.max(self.plot_ppg2)
        # print('ylims_ppg2', ymin_ppg2, ymax_ppg2)
        if np.abs(ymax_ppg2 - ymin_ppg2) > 0:
            self.ax[1, 1].set_ylim(ymin_ppg2, ymax_ppg2)

        self.l1.set_data(self.xdata_eda, self.plot_eda)
        self.l2.set_data(self.xdata_resp, self.plot_resp)
        self.l3.set_data(self.xdata_ppg, self.plot_ppg1)
        self.l4.set_data(self.xdata_ppg, self.plot_ppg2)

        # self.fig.canvas.draw()
        return (self.l1, self.l2, self.l3, self.l4,)


    def animate(self):
        start_pos = self.fig.add_axes((0.9, 0.01, 0.1, 0.04))
        self.start_button = Button(start_pos, "Start") #, hovercolor="0.975")
        self.start_button.on_clicked(self._start)
        # self.fig.canvas.draw()
        plt.show()

    def _start(self, event):
        if not self.expObj.live_acquisition_flag:
            self.PhysPlotAnimation.event_source.start()
            self.expObj.start_time = datetime.now()
            self.start_button.__setattr__('text', 'Stop')
            # self.fig.canvas.draw()
            self.expObj.live_acquisition_flag = True


    def addData(self, value):
        eda_val, resp_val, ppg1_val, ppg2_val = value
        self.sample_count += 1
        time_point = float(self.sample_count)/self.expObj.fs

        self.xdata_ppg = np.roll(self.xdata_ppg, -1)
        self.xdata_eda = np.roll(self.xdata_eda, -1)
        self.xdata_resp = np.roll(self.xdata_resp, -1)
        self.plot_eda = np.roll(self.plot_eda, -1)
        self.plot_resp = np.roll(self.plot_resp, -1)
        self.plot_ppg1 = np.roll(self.plot_ppg1, -1)
        self.plot_ppg2 = np.roll(self.plot_ppg2, -1)

        ppg1_filtered = self.expObj.ppg1_filt_obj.lfilt(ppg1_val)
        ppg2_filtered = self.expObj.ppg2_filt_obj.lfilt(ppg2_val)
        resp_filtered = self.expObj.resp_filt_obj.lfilt(resp_val)
        eda_filtered = self.expObj.eda_filt_obj.lfilt(eda_val)

        self.xdata_ppg[-1] = time_point
        self.xdata_eda[-1] = time_point
        self.xdata_resp[-1] = time_point
        self.plot_eda[-1] = eda_filtered
        self.plot_resp[-1] = resp_filtered
        self.plot_ppg1[-1] = ppg1_filtered
        self.plot_ppg2[-1] = ppg2_filtered

        return


def main(args_parser):

    expObj = Experiment(args_parser)
    serObj = SerialCom(expObj)
    sigPlot = PhysPlot(expObj)

    serObj.connect()

    sigPlot.PhysPlotAnimation = FuncAnimation(
        sigPlot.fig, sigPlot.update, init_func=sigPlot.init_func, frames=sigPlot.N, interval=sigPlot.interv, blit=sigPlot.blit)

    acquisition_thread = threading.Thread(name='acquisition_thread', target=acquisition_thread_function, args=(sigPlot.addData, serObj, expObj), daemon=True)        
    acquisition_thread.start()

    sigPlot.animate()

    # expObj.live_acquisition_flag = False
    time.sleep(1) #let the thread gets terminated

    serObj.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=str,
                        dest='pid', help='Participant ID')
    parser.add_argument('--exp', type=str,
                        dest='exp_name', help='Name of experimental condition')
    parser.add_argument('--savepath', default='data', type=str,
                        dest='savedir', help='Directory path to save data')
    parser.add_argument('--duration', default=300, type=int,
                        dest='duration', help='Total acquisition duration in seconds')
    parser.add_argument('REMAIN', nargs='*')
    args_parser = parser.parse_args()
    main(args_parser=args_parser)