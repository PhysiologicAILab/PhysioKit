import os
import sys
from copy import deepcopy
import numpy as np
from scipy import signal
import argparse
import json
import pandas as pd
import neurokit2 as nk
from importlib.resources import files

import matplotlib.pyplot as plt
# plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["font.size"] = "18"

import warnings
warnings.filterwarnings('ignore')

from PhysioKit2.analysis_helper.utils.load_data import load_csv_data_all
from PhysioKit2.sqa.inference import sqaPPGInference
import matplotlib.pyplot as plt

class Process_Signals(object):
    def __init__(self, config, datapath, savepath, datadict) -> None:
        self.config = config
        self.datapath = datapath
        self.status = True
        msg = []

        if os.path.exists(self.config):
            with open(self.config) as json_file:
                self.exp_dict = json.load(json_file)
        else:
            self.status = False
            msg.append("Incorrect path infiified for experiment config file.\n")

        self.opt_sensor = self.exp_dict["opt_sensor"]
        if self.opt_sensor == "ppg1":
            self.sensor_name = "FingerPPG"
        elif self.opt_sensor == "ppg2":
            self.sensor_name = "EarPPG"
        elif self.opt_sensor == "best":
            self.sensor_name = "OptPPG"
        else:
            self.status = False
            msg.append("Invalid choice for optimal sensor to be used for analysis... Exiting...")

        if self.status:
            try:
                self.fs = int(self.exp_dict["fs"])
                self.total_duration = int(self.exp_dict["total_duration"])
                self.save_pth = os.path.join(savepath, "W" + str(self.exp_dict["winlen"]) + "_S" + str(self.exp_dict["step_len"]) \
                                             + "_" + self.sensor_name)
                self.ppg_plot_path = os.path.join(self.save_pth, "PPG_Plots")
                self.save_plot_flag = bool(self.exp_dict["save_plot_flag"])
                self.fs_actual = -1
                self.discard_len = 5
                self.max_freq_ppg = 8
                self.plot_low_freq = 0.5
                self.plot_high_freq = self.max_freq_ppg
                self.sqi_low_freq = 0.8
                self.sqi_high_freq = 2.0
                self.noise_low_freq = 0
                self.noise_high_freq = self.max_freq_ppg
                self.SQI_threshold = float(self.exp_dict["SQI_threshold"])

                self.sqi_window_len_sec = float(self.exp_dict["sqi_window_len_sec"])
                self.sqi_step_sec = float(self.exp_dict["sqi_step_sec"])
                self.sqa_config = files('PhysioKit2.sqa.config').joinpath('sqa_ppg.json')
                self.sqa_inference_obj = sqaPPGInference(self.sqa_config, debug=False)

                self.min_epoch_count = np.round(0.70 * (300 - self.exp_dict["winlen"]) /(self.exp_dict["step_len"]))

                if datadict != "":
                    self.datadict = datadict
                    if os.path.exists(self.datadict):
                        print("Loading: ", self.datadict)
                        self.analysis_dict_nk = np.load(self.datadict, allow_pickle=True).ravel()[0]
                    else:
                        self.status = False
                        print("Path no found: ", self.datadict)
                else:
                    print("Data dict not defined, creating new")
                    self.datadict = os.path.join(self.save_pth, "analysis_dict_nk.npy")
                    self.analysis_dict_nk = {}

                if not os.path.exists(self.save_pth):
                    os.makedirs(self.save_pth)
                    os.makedirs(self.ppg_plot_path)
                self.status = True

            except Exception as e:
                print("Exception: ", e)
        else:
            print(msg)


    def resp_process(self, resp, fs):
        resp_signals, resp_info = nk.rsp_process(resp, sampling_rate=fs)
        # resp_features = nk.rsp_intervalrelated(resp_epochs_df, sampling_rate=fs)



    def compute_sqa(self, filtered_bvp_vec, fs):

        sig_vec = deepcopy(filtered_bvp_vec)
        sig_vec = -1 * np.array(sig_vec)
        total_samples = len(sig_vec)
        # print("total_samples", total_samples)

        sqi_window_len_samples = int(fs * self.sqi_window_len_sec)
        sqi_step_samples = int(fs * self.sqi_step_sec)

        sqi_vec_array = np.array([])

        for start_time_idx in np.arange(0, total_samples - sqi_window_len_samples, sqi_step_samples-1):
            end_time_idx = start_time_idx + sqi_window_len_samples
            
            bvp_seg_filtered = sig_vec[start_time_idx: end_time_idx]
            bvp_seg_filtered = bvp_seg_filtered.reshape(1, -1)

            # compute SQIs
            # bvp_vec, sq_vec, _ = self.sqa_inference_obj.run_inference(bvp_seg_filtered, axis=1)
            sq_vec = self.sqa_inference_obj.run_inference(bvp_seg_filtered, axis=1)

            sqi_vec_array = np.append(sqi_vec_array, sq_vec)


        sqi_vec_array = 1 - sqi_vec_array
        # sqi_vec_array[sqi_vec_array < self.SQI_threshold] = 0
        # sqi_vec_array[sqi_vec_array >= self.SQI_threshold] = 1

        # fig, ax = plt.subplots(2, 1)
        # ax[0].plot(bvp_vec_array.T)
        # ax[1].plot(sqi_vec_array.T)
        # plt.show()
        # plt.close(fig)

        return np.median(sqi_vec_array)



    def ppg_process(self, ppg, fs, pid="", cond="", desc=""):

        self.max_samples = len(ppg)
        fs_actual = int((float(self.max_samples/self.total_duration)))
        if fs_actual - fs >= self.exp_dict["fs_margin"]:
            fs_actual = fs
            self.max_samples = int(fs_actual*self.total_duration)
            ppg = ppg[0:self.max_samples]
        elif fs - fs_actual >= self.exp_dict["fs_margin"]:
            fs_actual = fs

        self.fs_actual = fs_actual
        print("Achieved sampling rate: ", fs_actual)

        # actual_total_duration = int(float(self.max_samples / fs_actual))
        step_samples = int(float(self.exp_dict["step_len"]) * fs_actual)
        winlen = int(self.exp_dict["winlen"])  # seconds
        winlen_samples = int(winlen * fs_actual)
        
        self.events = {}
        e_onset = np.array(np.arange(0, self.max_samples - winlen_samples, step_samples))
        e_duration = winlen_samples * np.ones_like(e_onset)        
        e_label = np.array([str(d) for d in range(1, len(e_onset) + 1)])
        e_condition = np.array([cond]*len(e_onset))
        self.events["onset"] = e_onset
        self.events["duration"] = e_duration
        self.events["label"] = e_label
        self.events["condition"] = e_condition
        # self.epoch_start = 0
        # self.epoch_end = winlen

        # ppg_signals_raw, _ = nk.ppg_process(ppg, sampling_rate=fs_actual)
        # ppg_epochs_raw = nk.epochs_create(ppg_signals_raw, events=self.events, sampling_rate=fs_actual, epochs_start=self.epoch_start, epochs_end=self.epoch_end)

        # print("*"*50)
        # print("ppg_epochs")
        # print("*"*50)
        # print("PPG_Raw", len(ppg_epochs["1"]["PPG_Raw"]))
        # print("PPG_Clean", len(ppg_epochs["1"]["PPG_Clean"]))
        # print("PPG_Rate", len(ppg_epochs["1"]["PPG_Rate"]))

        sos = signal.butter(0, (float(self.exp_dict["low_cut_freq"]), float(self.exp_dict["high_cut_freq"])), 'bandpass', fs=self.fs_actual, output='sos')
        filtered_ppg = signal.sosfilt(sos, ppg)
        filtered_ppg = filtered_ppg[self.discard_len * fs_actual:]

        ppg_signals, ppg_info = nk.ppg_process(filtered_ppg, sampling_rate=fs_actual)
        # ppg_features = nk.ppg_analyze(ppg_signals, sampling_rate=fs_actual)
        ppg_epochs = nk.epochs_create(ppg_signals, events=self.events, sampling_rate=fs_actual)
        # ppg_feats_eps = nk.ppg_intervalrelated(ppg_epochs, sampling_rate=fs_actual)

        SQI_epochs = []
        # for key, val in ppg_epochs_raw.items():
        #     ps = np.abs(np.fft.fft(val["PPG_Raw"]))**2
        #     freqs = np.fft.fftfreq(len(val["PPG_Raw"]), 1/fs_actual)
        #     pow_plot = ps[(freqs > self.plot_low_freq) & (freqs < self.plot_high_freq)]
        #     freqs_plot = freqs[(freqs > self.plot_low_freq) & (freqs < self.plot_high_freq)]
        #     sig_strength = np.sum(ps[(freqs > self.sqi_low_freq) & (freqs < self.sqi_high_freq)])
        #     noise_strength = np.sum(ps[(freqs > self.noise_low_freq) & (freqs < self.noise_high_freq)])
        #     SQI_epochs.append(np.round(float(sig_strength) / noise_strength, 2))

        # for key, val in ppg_epochs.items():
        for key, val in ppg_epochs.items():
            # print("Key", key)
            # plt.plot(val["PPG_Raw"])
            # plt.show()
            aSQI = self.compute_sqa(val["PPG_Raw"], fs_actual)
            SQI_epochs.append(np.round(aSQI, 2))

        temp_epochs_met = {}
        temp_met_list = {}
        for met in self.exp_dict["metrics"]:
            temp_met_list[met] = []

        # print(ppg_feats_eps.columns)
        # print(ppg_feats_eps["HRV_LFHF"].to_list())
        # print(ppg_feats_eps["HRV_pNN50"].to_list())
        # print(ppg_feats_eps["HRV_SDNN"].to_list())
        # print(ppg_feats_eps["PPG_Rate_Mean"].to_list())
        # exit()

        ppg_features = {}
        ppg_features["SQI"] = np.mean(SQI_epochs)
        ppg_features_epoch = {}
        ppg_features_epoch["epoch_num"] = []
        # If any metrics is not in valid ramge, the all metrics in the epoch will be considered as invalid
        # If no epoch is valid, then the session is invalid
        ppg_features["session_valid"] = True

        for epoch_num in ppg_epochs:
            if SQI_epochs[int(epoch_num) - 1] > self.SQI_threshold:
                try:
                    feats = nk.hrv_time(ppg_epochs[epoch_num]['PPG_Peaks'], sampling_rate=fs_actual)
                    temp_epochs_met[epoch_num] = {}
                    for met in self.exp_dict["metrics"]:
                        if met == "PPG_Rate_Mean":
                            met_val = ppg_epochs[epoch_num]["PPG_Rate"].mean()
                            # met_val = ppg_feats_eps[met][int(epoch_num) - 1]
                        else:
                            met_val = feats[met][0]
                            # met_val = ppg_feats_eps[met][int(epoch_num) - 1]

                        temp_epochs_met[epoch_num][met] = met_val
                        temp_met_list[met].append(met_val)
                except Exception as e:
                    print(epoch_num, ": error:", e)
        # print("met:", met, ": ", temp_met_list[met])
        # exit()

        if self.exp_dict["skip_iqr_checks"]:
            for met in self.exp_dict["metrics"]:
                if (len(temp_met_list[met]) > 0):
                    med_val = np.nanmedian(temp_met_list[met])
                    if not np.isnan(med_val):
                        ppg_features[met] = [med_val]
                    else:
                        print("Session dropped:", pid, cond, met, med_val)
                        ppg_features["session_valid"] = False
                else:
                    print("Session dropped - no valid epoch:", pid, cond, met)
                    ppg_features["session_valid"] = False

        else:
            # If any metrics - extracted as median from the entire session - does not fall in the valid healthy range, the whole session is considered as invalid
            # All the session is considered invalid if any of the desired set of metrics is not extracted
            upper_bound = {}
            lower_bound = {}
            for met in self.exp_dict["metrics"]:
                if (len(temp_met_list[met]) >= 3):
                    q3, q1 = np.percentile(temp_met_list[met], [75, 25])
                    metIQR = q3 - q1
                    # print(metIQR)
                    lower_bound[met] = q1 - 1.5 * metIQR
                    upper_bound[met] = q3 + 1.5 * metIQR
                    lower_bound[met] = min(lower_bound[met], self.exp_dict["metrics_range"][met][0])
                    upper_bound[met] = max(upper_bound[met], self.exp_dict["metrics_range"][met][1])
                    # print(upper_bound[met])
                    # print(lower_bound[met])

                    temp_met_list[met] = np.array(temp_met_list[met])
                    temp_met_list[met] = temp_met_list[met][(temp_met_list[met] > lower_bound[met]) & (temp_met_list[met] < upper_bound[met])]
                    if (len(temp_met_list[met]) >= 3):
                        ppg_features[met] = [np.median(temp_met_list[met])]
                        if (ppg_features[met][0] >= lower_bound[met]) and (ppg_features[met][0] <= upper_bound[met]):
                            # print("Valid epoch")
                            pass
                        else:
                            # print("invalid epoch")
                            print("Session dropped:", pid, cond, met, ppg_features[met])
                            ppg_features["session_valid"] = False
                    else:
                        if (len(temp_met_list[met]) > 0):
                            ppg_features[met] = [np.median(temp_met_list[met])]
                            if ((ppg_features[met][0] >= lower_bound[met]) and (ppg_features[met][0] <= upper_bound[met])):
                                pass
                            else:
                                print("Session dropped:", pid, cond, met, ppg_features[met])
                                ppg_features["session_valid"] = False
                        else:
                            print("Session dropped - not enough valid epochs:", pid, cond, met)
                            ppg_features["session_valid"] = False
                else:
                    if (len(temp_met_list[met]) > 0):
                        ppg_features[met] = [np.median(temp_met_list[met])]
                        if ((ppg_features[met][0] >= self.exp_dict["metrics_range"][met][0]) and (ppg_features[met][0] <= self.exp_dict["metrics_range"][met][1])):
                            pass
                        else:
                            print("Session dropped:", pid, cond, met, ppg_features[met])
                            ppg_features["session_valid"] = False
                    else:
                        print("Session dropped - not enough valid epochs:", pid, cond, met)                        
                        ppg_features["session_valid"] = False

        # print("temp_epochs_met")
        # print(temp_epochs_met)
        # exit()
        if ppg_features["session_valid"]:
            for epoch_num in temp_epochs_met:
                ppg_features_epoch["epoch_num"].append(int(epoch_num))
                ppg_features_epoch[epoch_num] = {}
                ppg_features_epoch[epoch_num]["SQI"] = SQI_epochs[int(epoch_num) - 1]
                
                # If any metrics for a specific epoch gets nil valid value, the epoch is considered invalid, 
                # irrespective if other metrics have valid values
                ppg_features_epoch[epoch_num]["epoch_valid"] = True

                if self.exp_dict["skip_iqr_checks"]:
                    for met in self.exp_dict["metrics"]:
                        if not np.isnan(temp_epochs_met[epoch_num][met]):
                            ppg_features_epoch[epoch_num][met] = temp_epochs_met[epoch_num][met]
                        else:
                            print("Epoch dropped:", pid, cond, met, temp_epochs_met[epoch_num][met])
                            ppg_features_epoch[epoch_num]["epoch_valid"] = False
                else:
                    # print(met, temp_epochs_met[epoch_num][met])
                    for met in self.exp_dict["metrics"]:
                        if met in lower_bound:
                            if (temp_epochs_met[epoch_num][met] >= lower_bound[met]) and \
                                (temp_epochs_met[epoch_num][met] <= upper_bound[met]): # and \
                                # (temp_epochs_met[epoch_num][met] >= self.exp_dict["metrics_range"][met][0]) and \
                                # (temp_epochs_met[epoch_num][met] <= self.exp_dict["metrics_range"][met][1]):
                                ppg_features_epoch[epoch_num][met] = temp_epochs_met[epoch_num][met]
                            else:
                                print("Epoch dropped:", pid, cond, met, temp_epochs_met[epoch_num][met], [lower_bound[met], upper_bound[met]])
                                ppg_features_epoch[epoch_num]["epoch_valid"] = False
                        else:
                            print("Epoch dropped:", pid, cond, met, temp_epochs_met[epoch_num][met], [lower_bound[met], upper_bound[met]])
                            ppg_features_epoch[epoch_num]["epoch_valid"] = False

            valid_epochs = []
            for epcs in temp_epochs_met:
                if ppg_features_epoch[epcs]["epoch_valid"]:
                    valid_epochs.append(True)
                else:
                    valid_epochs.append(False)
        
            # print("valid_epochs", valid_epochs)
            if sum(valid_epochs) < 3:
                print("Session dropped - not enough valid epochs:", pid, cond)
                ppg_features["session_valid"] = False


        if self.save_plot_flag:
            save_pth = os.path.join(self.ppg_plot_path, pid)
            if not os.path.exists(save_pth):
                os.makedirs(save_pth)

            fig, ax = plt.subplots(2, 1, figsize=(25, 16), layout = "tight")
            ln_sig1 = int(len(ppg_signals['PPG_Clean'])/fs_actual)
            x_axis1 = np.arange(0, ln_sig1, 1/fs_actual)
            mn_len1 = min(len(x_axis1), len(ppg_signals['PPG_Clean']))
            ax[0].plot(x_axis1[:mn_len1], ppg_signals['PPG_Clean'][:mn_len1])
            ax[0].plot(ppg_info['PPG_Peaks']/fs_actual, ppg_signals['PPG_Clean'][ppg_info['PPG_Peaks']], 'go')
            # ax[0].plot(ppg_info['PPG_Peaks']/fs_actual, ppg_signals['PPG_Clean'][ppg_info['PPG_Peaks'] == 0], 'ro')
            ax[0].set_xlabel("Time (seconds)")
            ax[0].set_ylabel("PPG Signal")
            # ax[1].plot(freqs_plot, pow_plot)
            ax[1].plot(SQI_epochs)
            ax[1].set_xlabel("Epochs")
            ax[1].set_ylabel("PPG SQA")
            # ax[1].set_title("PPG SQA = " + str(SQI_epochs))


            plt.savefig(os.path.join(save_pth, cond + "_" + "_" + desc + '_PPG.jpg'), dpi = 300)
            plt.close(fig)

        return ppg_features, ppg_features_epoch



    def process_data(self):

        for pid, conds in self.exp_dict["pids"].items():
            if self.exp_dict["mode"] == "debug":
                if pid not in self.exp_dict["debug_pids"]:
                    continue
            else:
                if pid in self.exp_dict["discard_pids"]:
                    continue
            if pid not in self.analysis_dict_nk:
                self.analysis_dict_nk[pid] = {}
            for cond, val in conds.items():
                if cond in self.exp_dict["conds"]:
                    if cond not in self.analysis_dict_nk[pid]:
                        self.analysis_dict_nk[pid][cond] = {}

                        fn = os.path.join(self.datapath, pid, val["path"])
                        _, _, ppg1, ppg2, _ = load_csv_data_all(fn)

                        print("Processing: ", pid, cond)
                        # PPG1
                        if self.opt_sensor == "best" or self.opt_sensor == "ppg1":
                            ppg1_features, ppg1_features_epoch = self.ppg_process(ppg1, fs=self.fs, pid=pid, cond=cond, desc="PPG Finger")
                            session1_valid =  ppg1_features["session_valid"]
                        else:
                            session1_valid = False
                        
                        # PPG2
                        if self.opt_sensor == "best" or self.opt_sensor == "ppg2":
                            ppg2_features, ppg2_features_epoch = self.ppg_process(ppg2, fs=self.fs, pid=pid, cond=cond, desc="PPG Ear")
                            session2_valid =  ppg2_features["session_valid"]
                        else:
                            session2_valid = False

                        # PPG
                        if (session1_valid or session2_valid):
                            self.analysis_dict_nk[pid][cond]["ppg_features"] = {}
                            self.analysis_dict_nk[pid][cond]["ppg_features_epoch"] = {}

                            if self.opt_sensor == "best":
                                if session1_valid and session2_valid:
                                    max_epoch = max(ppg1_features_epoch["epoch_num"][-1], ppg2_features_epoch["epoch_num"][-1])
                                elif session1_valid:
                                    max_epoch = ppg1_features_epoch["epoch_num"][-1]
                                elif session2_valid:
                                    max_epoch = ppg2_features_epoch["epoch_num"][-1]
                                else:
                                    print("Error, needs debugging... exiting")
                                    exit()
                            elif self.opt_sensor == "ppg1":
                                max_epoch = ppg1_features_epoch["epoch_num"][-1]
                            elif self.opt_sensor == "ppg2":
                                max_epoch = ppg2_features_epoch["epoch_num"][-1]
                            
                            self.analysis_dict_nk[pid][cond]["max_epoch"] = max_epoch

                            for met in self.exp_dict["metrics"]:
                                if self.opt_sensor == "best":
                                    if session1_valid and session2_valid:
                                        if ppg1_features["SQI"] > ppg2_features["SQI"]:
                                            self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg1_features[met]
                                        else:
                                            self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg2_features[met]
                                    elif session1_valid:
                                        self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg1_features[met]
                                    elif session2_valid:
                                        self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg2_features[met]
                                    else:
                                        print("Error, needs debugging... exiting")
                                        exit()

                                elif self.opt_sensor == "ppg1":
                                    self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg1_features[met]

                                elif self.opt_sensor == "ppg2":
                                    self.analysis_dict_nk[pid][cond]["ppg_features"][met] = ppg2_features[met]

                            for epoch_indx in range(max_epoch):
                                epoch_exists = False
                                if self.opt_sensor == "best":
                                    if str(epoch_indx + 1) in ppg1_features_epoch and str(epoch_indx + 1) in ppg2_features_epoch:
                                        ppg1_epoch_valid = ppg1_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                        ppg2_epoch_valid = ppg2_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                        if (ppg1_features_epoch[str(epoch_indx + 1)]["SQI"] > ppg2_features_epoch[str(epoch_indx + 1)]["SQI"]) and ppg1_epoch_valid:
                                            epoch_exists = True
                                            valid_sensor = "Finger"
                                            
                                        elif (ppg2_features_epoch[str(epoch_indx + 1)]["SQI"] > ppg1_features_epoch[str(epoch_indx + 1)]["SQI"]) and ppg2_epoch_valid:
                                            valid_sensor = "Ear"
                                            epoch_exists = True
                                        
                                        elif ppg2_epoch_valid:
                                            valid_sensor = "Ear"
                                            epoch_exists = True

                                        elif ppg1_epoch_valid:
                                            valid_sensor = "Finger"
                                            epoch_exists = True

                                        else:
                                            epoch_exists = False
                                    
                                    elif str(epoch_indx + 1) in ppg1_features_epoch:
                                        valid_sensor = "Finger"
                                        epoch_exists = ppg1_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                    
                                    elif str(epoch_indx + 1) in ppg2_features_epoch:
                                        valid_sensor = "Ear"
                                        epoch_exists = ppg2_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                    
                                    else:
                                        epoch_exists = False
                                
                                elif self.opt_sensor == "ppg1":
                                    if str(epoch_indx + 1) in ppg1_features_epoch:
                                        valid_sensor = "Finger"
                                        epoch_exists = ppg1_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                    else:
                                        epoch_exists = False
                                
                                elif self.opt_sensor == "ppg2":
                                    if str(epoch_indx + 1) in ppg2_features_epoch:
                                        valid_sensor = "Ear"
                                        epoch_exists = ppg2_features_epoch[str(epoch_indx + 1)]["epoch_valid"]
                                    else:
                                        epoch_exists = False
                                
                                else:
                                    epoch_exists = False
                                    print("Invalid choice for opt_sensor, exiting...")
                                    exit()

                                if epoch_exists:
                                    for met in self.exp_dict["metrics"]:
                                        if met not in self.analysis_dict_nk[pid][cond]["ppg_features_epoch"]:
                                            self.analysis_dict_nk[pid][cond]["ppg_features_epoch"][met] = {}
                                        if valid_sensor == "Finger":
                                            met_val = ppg1_features_epoch[str(epoch_indx + 1)][met]
                                        else:
                                            met_val = ppg2_features_epoch[str(epoch_indx + 1)][met]

                                        self.analysis_dict_nk[pid][cond]["ppg_features_epoch"][met][str(epoch_indx + 1)] = met_val

                        np.save(self.datadict, self.analysis_dict_nk)


    def make_data_tables(self):
        df_abs_dict = {}
        df_rel_dict = {}

        # print("AnalysisDict:", self.analysis_dict_nk[self.exp_dict["debug_pids"][0]])
        abs_diff = bool(self.exp_dict["absolute_difference_for_relative_metrics_change"])

        for met in self.exp_dict["metrics"]:
            df_abs_dict[met] = {}
            df_abs_dict[met]["pid"] = []
            df_abs_dict[met]["cond"] = []
            df_abs_dict[met]["metVal"] = []

            df_rel_dict[met] = {}
            df_rel_dict[met]["pid"] = []
            df_rel_dict[met]["cond"] = []
            df_rel_dict[met]["metVal"] = []

            for pid, val in self.exp_dict["pids"].items():
                # try:
                if pid not in self.analysis_dict_nk:
                    continue
                else:
                    if self.exp_dict["mode"] == "debug":
                        if pid not in self.exp_dict["debug_pids"]:
                            continue
                    else:
                        if pid in self.exp_dict["discard_pids"]: # change to PIDs, and change the sample dictionary, and sample data
                            continue

                for cond in self.exp_dict["conds"]:
                    if "ppg_features" in self.analysis_dict_nk[pid][cond]:
                        print("Processing: ", met, cond)

                        cond_met = self.analysis_dict_nk[pid][cond]["ppg_features"][met][0]
                        met_epoch_dict = self.analysis_dict_nk[pid][cond]["ppg_features_epoch"][met]
                        cond_met_epoch = []
                        cond_epoch_name = []

                        for epoch_key, epoch_val in met_epoch_dict.items():
                            cond_met_epoch.append(epoch_val)
                            cond_epoch_name.append(epoch_key)
                            # print("epoch_key, epoch_val:", [epoch_key, epoch_val])

                        for met_val in cond_met_epoch:
                            df_abs_dict[met]["pid"].append(pid) # change to PID everywhere
                            df_abs_dict[met]["cond"].append(cond)
                            df_abs_dict[met]["metVal"].append(met_val)

                        # print("cond_met", cond_met)
                        # print("cond_met_epoch", cond_met_epoch)
                        if cond == self.exp_dict["conds"][0]:
                            baseline_met = deepcopy(cond_met)

                        if (baseline_met != None) and (len(cond_met_epoch) >= 0):
                            # rel_met = np.round(100 * ((cond_met - baseline_met) / baseline_met), 2)
                            if abs_diff:
                                rel_met_epoch = np.abs(cond_met_epoch - baseline_met)
                            else:
                                rel_met_epoch = cond_met_epoch - baseline_met
                        else:
                            rel_met_epoch = None
                            # rel_met = None

                        if np.all(rel_met_epoch) != None:
                            # print("rel_met_epoch", rel_met_epoch)
                            # if cond != self.exp_dict["conds"][0]:
                            for rel_met_val in rel_met_epoch:
                                df_rel_dict[met]["pid"].append(pid)
                                df_rel_dict[met]["cond"].append(cond)
                                df_rel_dict[met]["metVal"].append(rel_met_val)


        save_path = os.path.join(self.save_pth, "Individual_Plots")
        if not os.path.exists(save_path):
            os.makedirs(save_path)


        np.save(os.path.join(self.save_pth, "df_abs_dict.npy"), df_abs_dict)
        np.save(os.path.join(self.save_pth, "df_rel_dict.npy"), df_rel_dict)

        with pd.ExcelWriter(os.path.join(self.save_pth, "df_abs_feat.xlsx"), mode='w', engine="xlsxwriter") as writer_abs_dict_df:
            for met in self.exp_dict["metrics"]:
                abs_dict = df_abs_dict[met]
                abs_dict_df = pd.DataFrame(data=abs_dict)
                abs_dict_df.to_excel(writer_abs_dict_df, sheet_name=met, index=False)

        with pd.ExcelWriter(os.path.join(self.save_pth, "df_rel_feat.xlsx"), mode='w', engine="xlsxwriter") as writer_rel_dict_df:
            for met in self.exp_dict["metrics"]:
                rel_dict = df_rel_dict[met]
                rel_dict_df = pd.DataFrame(data=rel_dict)
                rel_dict_df.to_excel(writer_rel_dict_df, sheet_name=met, index=False)



def main(argv=sys.argv):
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, dest='config', help='Config file for experiment')
    parser.add_argument('--opt', type=str, dest='opt', help='0 - process signals/  1 - make data tables', default="0")
    parser.add_argument('--datapath', type=str, dest='datapath', help='Root directory for data', default="data")
    parser.add_argument('--savepath', type=str, dest='savepath', help='Destination directory for saving analysis outcome', default="analysis")
    parser.add_argument('--datadict', type=str, dest='datadict', help='Filepath for data dictionary', default="")
    parser.add_argument('REMAIN', nargs='*')
    args_parser = parser.parse_args()

    Process_Signals_obj = Process_Signals(args_parser.config, args_parser.datapath, args_parser.savepath, args_parser.datadict)
    
    if Process_Signals_obj.status:
        opt = args_parser.opt
        if opt == "0":
            Process_Signals_obj.process_data()
        elif opt == "1":
            Process_Signals_obj.make_data_tables()
        else:
            print("Invalid analysis option")


if __name__ == "__main__":
    main()

