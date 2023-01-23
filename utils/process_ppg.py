# Python script tp process the raw PPG data acquired using correponding Android App
# Example Usage: python .\process_ppg.py <path to CSV file>
## Author(s): Jitesh Joshi (PhD Student, UCL Computer Science)

import numpy as np
import os, csv
import matplotlib.pyplot as plt
from scipy.signal import butter, lfilter, periodogram
from scipy.interpolate import interp1d
import heartpy as hp
import pandas as pd


def butter_bandpass(lowcut, highcut, sample_rate, order=2):
    nyq = 0.5 * sample_rate
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, sample_rate, order=2):
    b, a = butter_bandpass(lowcut, highcut, sample_rate, order=order)
    y = lfilter(b, a, data)
    return y


def get_clean_segment(ppg_sig, std_n=2.0):
	filtered_clean = [[]]
	start = False
	mean_filtered = np.mean(ppg_sig)
	std_filtered = np.std(ppg_sig)
	min_val = mean_filtered - std_n*std_filtered
	max_val = mean_filtered + std_n*std_filtered
	# print('len(filtered):', len(ppg_sig))
	# print('mean_filtered:', mean_filtered)
	# print('std_filtered:', std_filtered)
	# print('min_val:', min_val)
	# print('max_val:', max_val)
	for dt in list(ppg_sig):
		if dt >= min_val and dt <= max_val:
			if not start:
				start = True
			filtered_clean[-1].append(dt)
		else:
			if start:
				start = False
				filtered_clean.append([])

	# print('Number of segments', len(filtered_clean))
	final_filtered = []
	max_length = 0
	for segs in filtered_clean:
		if len(segs) > max_length:
			final_filtered = segs
			max_length = len(segs)
	filtered_clean = np.array(final_filtered)
	# print('max length of clean signal', max_length)

	return filtered_clean


def get_filtered_ppg(t_seconds, raw_signal, sample_rate=30.0):

	discard_len = 5.0 #seconds

	f, Pxx_den = periodogram(raw_signal, sample_rate, 'flattop', scaling='spectrum')
	lowcut_ppg = 1.6
	highcut_ppg = 3.0
	lowcut_resp = 0.15
	highcut_resp = 0.3
	order = 2

	Pxx_den_PPG = Pxx_den[np.bitwise_and(f>=lowcut_ppg, f<=highcut_ppg)]
	f_PPG = f[np.bitwise_and(f>=lowcut_ppg, f<=highcut_ppg)]
	max_power_freq_ppg = f_PPG[np.argmax(Pxx_den_PPG)]
	# print("Freq with max power:", max_power_freq_ppg)

	# Adaptive bandpass filtering
	lowcut_ppg = max_power_freq_ppg - 0.8
	highcut_ppg = max_power_freq_ppg + 0.8

	filtered_PPG = butter_bandpass_filter(raw_signal, lowcut_ppg, highcut_ppg, sample_rate, order=order)
	# filtered_resp = butter_bandpass_filter(raw_signal, lowcut_resp, highcut_resp, sample_rate, order=order)

	# filtered_PPG = filtered_PPG[t_seconds>discard_len]
	# # filtered_resp = filtered_resp[t_seconds>discard_len]
	# t_seconds = t_seconds[t_seconds>discard_len]

	# filtered_PPG = get_clean_segment(filtered_PPG)

	return t_seconds, filtered_PPG

def load_PPG_signal(filepath):
	try:
		with open(filepath, newline='') as csvfile:
			txt_data = csv.reader(csvfile, delimiter=',')
			print()
	except:
		if os.path.exists(filepath):
			print("Error reading the file", filepath)
			return []
		else:
			print("Specified file not found", filepath)
			return []

	raw_signal_1 = np.array([], dtype=np.double)
	raw_signal_2 = np.array([], dtype=np.double)
	raw_signal_3 = np.array([], dtype=np.double)
	tElapsed = np.array([], dtype=np.double)
	for i in range(len(txt_data)):
		tElapsed = np.append(tElapsed, np.double(txt_data[i][0])/1000.0)  # milliseconds to seconds
		raw_signal_1 = np.append(raw_signal_1, np.double(txt_data[i][0]))
		raw_signal_2 = np.append(raw_signal_2, np.double(txt_data[i][0]))
		raw_signal_3 = np.append(raw_signal_3, np.double(txt_data[i][0]))
	return tElapsed, raw_signal_1, raw_signal_2, raw_signal_3

def get_ppg_measures_batch(datapath, outdir, sample_rate=30.0):

	csv_fpath = os.path.join(outdir, 'PPG_features.csv')
	csvfile = open(csv_fpath, 'w', newline='')
	fp_writer = csv.writer(csvfile, delimiter=',')
	header = ['sub_id', 'label', 'bpm', 'ibi', 'sdnn', 'sdsd', 'rmssd', 'pnn20', 'pnn50', 'hr_mad', 'sd1', 'sd2', 's', 'sd1/sd2', 'breathingrate']
	fp_writer.writerow(header)
	csvfile.close()
	
	pklfilepath = os.path.join(outdir, 'PPG_features.pkl')
	# pklfile = open(pklfilepath, 'wb')
	data_dict = {}

	sub_ids = []
	fn_list = []
	cnt = 0
	for path, dirs, files in os.walk(datapath):
		if cnt == 0:
			if 'RawPPG' in dirs:
				ppg_dir = dirs[dirs.index('RawPPG')]
			else:
				print('RawPPG directory within data directory not found')
		elif cnt == 1:
			sub_ids = dirs
		elif cnt >= 2:
			fn_list.append(files)
		cnt += 1

	# print('sub_ids', sub_ids)
	# print('fn_list', fn_list)
	for i in range(len(sub_ids)):
		sub_id = sub_ids[i]
		for fn in fn_list[i]:
			if os.path.splitext(fn)[-1] == '.csv' and fn.split('_')[0] == 'ppgSignal':
				print('Processing:', sub_id, ':', fn)
				data_dict[sub_id + '_' + fn] = {}
				filepath = os.path.join(datapath, ppg_dir, sub_id, fn)
				raw_signal, tElapsed = load_PPG_signal(filepath)
				# Re-sample the signal here before  filtering
				
				filtered = get_filtered_ppg(raw_signal, sample_rate=sample_rate)

				if len(filtered) > 30*sample_rate:
					start_indx = int(((len(filtered)//2) - (15*sample_rate)))
					end_indx = int(((len(filtered)//2) + (15*sample_rate)))
					filtered = filtered[start_indx: end_indx]

				csvfile = open(csv_fpath, 'a+', newline='')
				fp_writer = csv.writer(csvfile, delimiter=',')

				label = fn.split('_')[1]
				vals = []
				vals.append(sub_id)
				vals.append(label)
				try:
					wd, m = hp.process(filtered, sample_rate=sample_rate)
					for measure in m.keys():
						vals.append(str(m[measure]))
				except:
					vals = ['']*15
					wd = {}
					m = {}
			
				m['exertion_level'] = label
				m['sub_id'] = sub_id
				data_dict[sub_id + '_' + fn]['wd'] = wd
				data_dict[sub_id + '_' + fn]['m'] = m
				fp_writer.writerow(vals)
				csvfile.close()

	df = pd.DataFrame(data_dict)
	df.to_pickle(pklfilepath)


def load_dataframe(filepath):

	df = pd.read_pickle(filepath)
	params = ['sub_id', 'exertion_level', 'bpm', 'ibi', 'sdnn', 'sdsd', 'rmssd',
			'pnn20', 'pnn50', 'hr_mad', 'sd1', 'sd2', 's', 'sd1/sd2', 'breathingrate']

	feature_dict = {}
	for pr in params:
		feature_dict[pr] = []

	params_dict = df.iloc[1, :]
	for fdict in params_dict:
		for key in fdict.keys():
			feature_dict[key].append(fdict[key])

	ppg_df = pd.DataFrame(feature_dict, columns=params)

	return df, ppg_df
# if __name__ == "__main__":
#    main(sys.argv[1:])




