import neurokit2 as nk
import numpy as np
from PySide6.QtCore import Signal, QThread, Signal
import time

class BioFeedback_Thread(QThread):
    update_bf_size = Signal(int)
    update_bf_color = Signal(str)

    def __init__(self, fs, window_len, step_len, vis_opt, bf_metric, parent):
        # QThread.__init__(self, parent)
        super(BioFeedback_Thread, self).__init__(parent=parent)
        self.stop_flag = False
        self.vis_opt = vis_opt
        self.bf_metric = bf_metric
        self.fs = fs
        self.window_len = window_len
        self.step_secs = step_len
        self.step_len = step_len
        self.win_samples = self.fs * self.window_len
        self.step_samples = self.fs * self.step_len
        self.bf_signal = np.zeros(self.win_samples)
        self.count_step = 0
        self.count_init_window = 0
        self.init_window_filled = False
        self.process_flag = False
        self.set_baseline = True
        self.bf_type = ""
        if "HRV" in self.bf_metric:
            self.bf_type = "PPG"
        elif "RSP" in self.bf_metric:
            self.bf_type = "RSP"
        elif "EDA" in self.bf_metric:
            self.bf_type = "EDA"
        else:
            print("Invalid type of signal specified for biofeedback...")

        if self.bf_type == "PPG":
            self.ppg_metrics = {}
            self.ppg_metrics[self.bf_metric] = 0
            self.ppg_metrics["baseline"] = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            self.ppg_metrics["percent_change"] = np.array([1, 1, 1], dtype=np.float32)

        self.circle_radius_baseline = 150
        self.circle_radius_bf = 150

        self.red_val = 127
        self.green_val = 127
        self.blue_val = 127


    def stop(self):
        self.stop_flag = True
        self.terminate()
        print("Biofeedback thread terminated...")


    def add_bf_data(self, sig_val):
        self.bf_signal = np.roll(self.bf_signal, -1)
        self.bf_signal[-1] = sig_val
        if not self.init_window_filled:
            self.count_init_window += 1
            if self.count_init_window >= self.win_samples:
                self.init_window_filled = True
                self.process_flag = True
        else:
            self.count_step += 1
            if self.count_step >= self.step_samples:
                self.process_flag = True
                self.count_step = 0


    def run(self):
        while not self.stop_flag:
            if self.process_flag:
                self.process_flag = False
                try:
                    if self.bf_type == "PPG":
                        self.ppg_proc_signals, self.ppg_info = nk.ppg_process(self.bf_signal, sampling_rate=self.fs)
                        hrv_indices = nk.hrv_time(self.ppg_info['PPG_Peaks'])
                        self.ppg_metrics[self.bf_metric] = hrv_indices[self.bf_metric][0]
                        print("metrics:", hrv_indices[self.bf_metric][0])
                        if self.set_baseline:
                            if self.ppg_metrics[self.bf_metric] != 0:
                                self.ppg_metrics["baseline"] = np.roll(self.ppg_metrics["baseline"], -1)
                                self.ppg_metrics["baseline"][-1] = self.ppg_metrics[self.bf_metric]
                                print("Baseline metrics:", self.ppg_metrics["baseline"])
                                self.set_baseline = True

                        if np.max(self.ppg_metrics["baseline"]) != 0:
                            baseline =  [d for d in self.ppg_metrics["baseline"] if d != 0]
                            baseline = np.mean(baseline)
                            self.ppg_metrics["percent_change"] = np.roll(self.ppg_metrics["percent_change"], -1)
                            self.ppg_metrics["percent_change"][-1] = 1 + 5.0*(float(self.ppg_metrics[self.bf_metric] - baseline) / baseline)
                        # else:
                        #     self.ppg_metrics["percent_change"] = 0
                        print("percent_change", self.ppg_metrics["percent_change"])
                    
                        if self.vis_opt == "size":    
                            self.circle_radius_bf = int(round((np.mean(self.ppg_metrics["percent_change"]) * self.circle_radius_baseline)))
                            if self.circle_radius_bf < 100:
                                self.circle_radius_bf = 100
                            elif self.circle_radius_bf > 300:
                                self.circle_radius_bf = 300
                            self.update_bf_size.emit(self.circle_radius_bf)
                        
                        else:
                            red_val = self.red_val - self.red_val * self.ppg_metrics["percent_change"]
                            green_val = self.green_val + self.green_val * self.ppg_metrics["percent_change"]
                            blue_val = self.blue_val + self.blue_val * self.ppg_metrics["percent_change"]

                            biofeedback_visualization = ("background-color:" + "rgb({red},{green},{blue})".format(
                                red=red_val, green=green_val, blue=blue_val) + "; border-radius: 10px")

                            self.update_bf_color.emit(biofeedback_visualization)

                    elif self.bf_type == "RSP":
                        self.resp_val = np.mean(self.resp_signal)

                        if self.vis_opt == "size":    
                            self.circle_radius_bf = int(round(100 * (self.resp_val + 3)))
                            if self.circle_radius_bf < 100:
                                self.circle_radius_bf = 100
                            elif self.circle_radius_bf > 300:
                                self.circle_radius_bf = 300
                            self.update_bf_size.emit(self.circle_radius_bf)

                        else:
                            print("Not implemented...")

                    else:
                        print("Not implemented")

                except Exception as e:
                    print(e)

            else:
                time.sleep(self.step_secs)
