import neurokit2 as nk
import numpy as np
from PySide6.QtCore import Signal, QThread, Signal
import time

class BioFeedback_Thread(QThread):
    update_bf_vis_out_int = Signal(int)
    update_bf_vis_out_str = Signal(str)
    update_bf_generic_out = Signal(str)

    def __init__(self, fs, bf_dict, parent):
        # QThread.__init__(self, parent)
        super(BioFeedback_Thread, self).__init__(parent=parent)
        self.stop_flag = False
        self.fs = fs
        self.bf_metric = bf_dict["metric"]
        self.window_len = float(bf_dict["window"])
        self.step_len = float(bf_dict["step"])
        self.bf_type = bf_dict["type"]
        if self.bf_type == "visual":
            self.vis_artifact = bf_dict["visual_feedback"]["varying_parameter"]
        
        self.win_samples = int(self.fs * self.window_len)
        self.step_samples = int(self.fs * self.step_len)
        self.normalizing_samples = int(self.fs * 4)
        self.bf_signal = np.zeros(self.win_samples)
        self.bf_signal_for_norm = np.zeros(self.normalizing_samples)
        self.count_step = 0
        self.count_init_window = 0
        self.init_window_filled = False
        self.process_flag = False
        self.set_baseline = True
        self.max_bf_signal = 1
        self.min_bf_signal = 0
        self.bf_threshold = 225
        self.resp_bf_max_val = 150
        self.resp_bf_min_val = 70
        self.resp_bf_off = 0


        self.bf_signal_type = ""
        if "HRV" in self.bf_metric:
            self.bf_signal_type = "PPG"
        elif "RSP" in self.bf_metric:
            self.bf_signal_type = "RSP"
        elif "EDA" in self.bf_metric:
            self.bf_signal_type = "EDA"
        else:
            print("Invalid type of signal specified for biofeedback...")

        if self.bf_signal_type == "PPG":
            self.ppg_metrics = {}
            self.ppg_metrics[self.bf_metric] = 0
            self.ppg_metrics["baseline"] = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
            self.ppg_metrics["percent_change"] = np.array([1, 1, 1], dtype=np.float32)

        if self.bf_type == "visual":
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
        self.bf_signal_for_norm = np.roll(self.bf_signal_for_norm, -1)

        self.bf_signal[-1] = sig_val
        self.bf_signal_for_norm[-1] = sig_val
        if not self.init_window_filled:
            self.count_init_window += 1
            if self.count_init_window >= self.win_samples:
                self.init_window_filled = True
                self.process_flag = True
                mx = np.max(self.bf_signal_for_norm)
                mn = np.min(self.bf_signal_for_norm)
                if mx - mn > self.bf_threshold:
                    self.max_bf_signal = mx
                    self.min_bf_signal = mn
        else:
            self.count_step += 1
            if self.count_step >= self.step_samples:
                self.process_flag = True
                self.count_step = 0
                mx = np.max(self.bf_signal_for_norm)
                mn = np.min(self.bf_signal_for_norm)
                if mx - mn > self.bf_threshold:
                    self.max_bf_signal = mx
                    self.min_bf_signal = mn


    def run(self):
        while not self.stop_flag:
            if self.process_flag:
                self.process_flag = False
                try:
                    if self.bf_signal_type == "PPG":
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
                        # print("percent_change", self.ppg_metrics["percent_change"])
                    
                        if self.bf_type == "visual":
                            if self.vis_artifact == "size":    
                                self.circle_radius_bf = int(round((np.mean(self.ppg_metrics["percent_change"]) * self.circle_radius_baseline)))
                                if self.circle_radius_bf < 100:
                                    self.circle_radius_bf = 100
                                elif self.circle_radius_bf > 300:
                                    self.circle_radius_bf = 300
                                self.update_bf_vis_out_int.emit(self.circle_radius_bf)
                            
                            else:
                                red_val = int(self.red_val - self.red_val * self.ppg_metrics["percent_change"])
                                green_val = int(self.green_val + self.green_val * self.ppg_metrics["percent_change"])
                                blue_val = int(self.blue_val + self.blue_val * self.ppg_metrics["percent_change"])

                                biofeedback_visualization = ("background-color:" + "rgb({red},{green},{blue})".format(
                                    red=red_val, green=green_val, blue=blue_val) + "; border-radius: 10px")

                                self.update_bf_vis_out_str.emit(biofeedback_visualization)

                        elif self.bf_type == "generic_uart":
                            # map the percentage change to string/ char before using this function.
                            self.update_bf_generic_out.emit(str(self.ppg_metrics["percent_change"]))

                    elif self.bf_signal_type == "RSP":
                        
                        self.resp_val = np.mean(self.bf_signal)
                        # print("Max - Min", self.max_bf_signal - self.min_bf_signal)
                        self.resp_val = (self.resp_val - self.min_bf_signal)/ (self.max_bf_signal - self.min_bf_signal)
                        # self.resp_val = int(self.resp_val * 255)
                        # self.resp_val = (1 - self.resp_val)

                        # print("self.resp_val:", self.resp_val)
                        if self.resp_val < 0.6:
                            self.resp_val = '0'
                        elif self.resp_val >= 0.6 and self.resp_val < 0.65:
                            self.resp_val = '1'
                        elif self.resp_val >= 0.65 and self.resp_val < 0.70:
                            self.resp_val = '2'
                        elif self.resp_val >= 0.70 and self.resp_val < 0.75:
                            self.resp_val = '3'
                        elif self.resp_val >= 0.75 and self.resp_val < 0.80:
                            self.resp_val = '4'
                        elif self.resp_val >= 0.80 and self.resp_val < 0.85:
                            self.resp_val = '5'
                        elif self.resp_val >= 0.85 and self.resp_val < 0.9:
                            self.resp_val = '6'
                        elif self.resp_val >= 0.90 and self.resp_val < 0.95:
                            self.resp_val = '7'
                        elif self.resp_val >= 0.95:
                            self.resp_val = '8'
                        else:
                            pass

                        
                        #     self.resp_val = int(self.resp_val * self.resp_bf_max_val)

                        # if self.resp_val > self.resp_bf_max_val:
                        #     self.resp_val = self.resp_bf_max_val
                        # if self.resp_val < 0:
                        #     self.resp_val = 0

                        if self.bf_type == "visual":
                            if self.vis_artifact == "size":    
                                self.circle_radius_bf = int(round(100 * (self.resp_val + 3)))
                                if self.circle_radius_bf < 100:
                                    self.circle_radius_bf = 100
                                elif self.circle_radius_bf > 300:
                                    self.circle_radius_bf = 300
                                self.update_bf_vis_out_int.emit(self.circle_radius_bf)

                            else:
                                print("Not implemented...")
                        
                        elif self.bf_type == "generic_uart":
                            self.update_bf_generic_out.emit(self.resp_val)

                    else:
                        print("Not implemented")

                except Exception as e:
                    print(e)

            else:
                time.sleep(self.step_len)
