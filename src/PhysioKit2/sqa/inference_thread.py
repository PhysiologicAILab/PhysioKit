import os
import json
import numpy as np
import time

import torch
from scipy import signal
from PySide6.QtCore import Signal, QThread, Signal
from importlib.resources import files

from PhysioKit2.sqa.model.sqa_ppg import Model as sqPPG

class sqaPPGInference(QThread):
    """
        The class to infer signal quality for BVP signal
    """
    update_sq_vec = Signal(list)

    def __init__(self, model_config, fs, nCh, axis, parent):
        super(sqaPPGInference, self).__init__(parent=parent)

        # Get cpu, gpu or mps device for inference.
        device = ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using {device} device")
        self.device = torch.device(device)

        if os.path.exists(model_config):
            with open(model_config) as json_file:
                self.model_config = json.load(json_file)
            json_file.close()
        else:
            print("Config file does not exists", model_config)
            print("Exiting the code.")
            exit()

        self.nCh = nCh
        self.fs = fs
        self.axis = axis
        self.target_fs = self.model_config["data"]["target_fs"]
        self.seq_len = self.model_config["data"]["window_len_sec"]
        self.total_samples = int((self.seq_len) * self.target_fs)
        self.sq_resolution = self.model_config["data"]["sq_resolution_sec"]

        self.stop_flag = False
        self.win_samples = self.fs * self.seq_len
        self.step_samples = self.fs * self.sq_resolution
        self.count_step = 0
        self.count_init_window = 0
        self.init_window_filled = False
        self.process_flag = False
        self.model_loaded = False

        if self.nCh == 1:
            self.bvp_vec_1 = np.zeros(self.win_samples)
        elif self.nCh ==2:
            self.bvp_vec_1 = np.zeros(self.win_samples)
            self.bvp_vec_2 = np.zeros(self.win_samples)
        else:
            print("Currenly the application only handles 2 PPG channels for signal quality")
            return


    def stop(self):
        self.stop_flag = True
        self.terminate()
        print("Signal quality assessment thread terminated...")


    def add_sq_data(self, sig_vals):
        sig_val_1, sig_val_2 = sig_vals 
        self.bvp_vec_1 = np.roll(self.bvp_vec_1, -1)
        self.bvp_vec_1[-1] = sig_val_1

        if self.nCh > 1:
            self.bvp_vec_2 = np.roll(self.bvp_vec_2, -1)
            self.bvp_vec_2[-1] = sig_val_2

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

            if not self.model_loaded:
                self.sqPPG_model = sqPPG(self.model_config).to(self.device)
                ckpt_path = files('PhysioKit2.sqa.ckpt').joinpath(self.model_config["ckpt_name"])
                if os.path.exists(ckpt_path):
                    checkpoint = torch.load(ckpt_path, map_location=self.device)
                    self.sqPPG_model.load_state_dict(checkpoint['model_state_dict'])
                    # optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                else:
                    print("No checkpoint found, existing...")
                    # exit()
                    return -1

                # self.sos = signal.butter(0, (0.5, 5.0), 'bandpass', fs=self.target_fs, output='sos')
                self.sqPPG_model.eval()
                
                self.model_loaded = True

            elif self.process_flag:
                self.process_flag = False

                with torch.no_grad():
                    bvp_vec_1 = self.bvp_vec_1.reshape(1, -1)
                    bvp_vec_1 = signal.resample(bvp_vec_1, self.total_samples, axis=self.axis)

                    min_r_ppg = np.min(bvp_vec_1)
                    max_r_ppg = np.max(bvp_vec_1)
                    bvp_vec_1 = (bvp_vec_1 - min_r_ppg)/ (max_r_ppg - min_r_ppg)

                    input_vec = torch.tensor(bvp_vec_1, dtype=torch.float)
                    input_vec = input_vec.unsqueeze(1)

                    input_vec = input_vec.to(self.device)        
                    sqa_vec_1 = self.sqPPG_model(input_vec)
                    sqa_vec_1 = sqa_vec_1.cpu().numpy().squeeze(1)

                    if self.nCh > 1:
                        bvp_vec_2 = self.bvp_vec_2.reshape(1, -1)
                        bvp_vec_2 = signal.resample(bvp_vec_2, self.total_samples, axis=self.axis)

                        min_r_ppg = np.min(bvp_vec_2)
                        max_r_ppg = np.max(bvp_vec_2)
                        bvp_vec_2 = (bvp_vec_2 - min_r_ppg)/ (max_r_ppg - min_r_ppg)

                        input_vec = torch.tensor(bvp_vec_2, dtype=torch.float)
                        input_vec = input_vec.unsqueeze(1)

                        input_vec = input_vec.to(self.device)        
                        sqa_vec_2 = self.sqPPG_model(input_vec)
                        sqa_vec_2 = sqa_vec_2.cpu().numpy().squeeze(1)

                        sq_vec = [sqa_vec_1, sqa_vec_2]
                    else:
                        sq_vec = [sqa_vec_1]

                    # print(sq_vec)
                    self.update_sq_vec.emit(sq_vec) # emit
            
            else:
                time.sleep(self.sq_resolution)