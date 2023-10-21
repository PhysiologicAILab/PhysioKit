import os
import argparse
import json
import numpy as np
import time

import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from scipy import signal

from PhysioKit2.sqa.model.sqa_ppg import Model as sqPPG
from importlib.resources import files

class sqaPPGInference(object):
    """
        The class to infer signal quality for BVP signal
    """
    def __init__(self, model_config, debug=False) -> None:

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

        self.debug = debug
        self.target_fs = self.model_config["data"]["target_fs"]
        self.seq_len = self.model_config["data"]["window_len_sec"]
        self.total_samples = int((self.seq_len) * self.target_fs)

        self.sq_resolution = self.model_config["data"]["sq_resolution_sec"]

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

    def run_inference(self, bvp_vec, axis=0):
        with torch.no_grad():
            if self.debug:
                t0 = time.time()
            # bvp_vec = signal.sosfilt(self.sos, bvp_vec) # bvp_vec needs to be filtered in the same range            
            bvp_vec = signal.resample(bvp_vec, self.total_samples, axis=axis)

            min_r_ppg = np.min(bvp_vec)
            max_r_ppg = np.max(bvp_vec)
            bvp_vec = (bvp_vec - min_r_ppg)/ (max_r_ppg - min_r_ppg)
            # print("bvp_vec.shape", bvp_vec.shape)

            input_vec = torch.tensor(bvp_vec, dtype=torch.float)
            input_vec = input_vec.unsqueeze(1)
            # print("input_vec.shape", input_vec.shape)
            # exit()

            input_vec = input_vec.to(self.device)        

            # print("input_vec.shape", input_vec.shape)
            sqa_vec = self.sqPPG_model(input_vec)
            sqa_vec = sqa_vec.cpu().numpy().squeeze(1)
            # print("sqa_vec.shape", sqa_vec.shape)

            if self.debug:
                elapsed_time = time.time() - t0
                print("elapsed time:", elapsed_time)
                return bvp_vec, sqa_vec, elapsed_time
            else:
                return sqa_vec
            


def main(args_parser):
    testObj = sqaPPGInference(args_parser.model_config, debug=True)
    bvp_vec = np.random.rand(1, 10*64)
    # print(bvp_vec.shape)
    # exit()
    bvp_vec, sqa_vec, elapsed_time = testObj.run_inference(bvp_vec, axis=1)

    fig, ax = plt.subplots(2, 1)
    ax[0].plot(bvp_vec.T)
    ax[1].plot(sqa_vec.T)
    plt.suptitle("Time Elapsed: " + str(elapsed_time))
    plt.show()
    plt.close(fig)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--model_config', type=str, dest='model_config', help='Config file for model')
    parser.add_argument('REMAIN', nargs='*')
    args_parser = parser.parse_args()

    main(args_parser)