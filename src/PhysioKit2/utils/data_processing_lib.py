import numpy as np
from scipy.signal import butter, iirnotch	#, lfilter, periodogram

class lFilter(object):
	def __init__(self, lowcut, highcut, sample_rate, order=2):
		nyq = 0.5 * sample_rate
		low = lowcut / nyq
		high = highcut / nyq
		b, a = butter(order, [low, high], btype='band')
		self.coefA = a
		self.coefB = b
		self.order = len(self.coefA) - 1
		self.z = [0] * self.order

	def lfilt(self, data):
		y = (data * self.coefB[0]) + self.z[0]
		for i in range(0, self.order):
			if (i < self.order - 1):
				self.z[i] = (data * self.coefB[i+1]) + (self.z[i+1]) - (self.coefA[i+1] * y)
			else:
				self.z[i] = (data * self.coefB[i+1]) - (self.coefA[i+1] * y)
		return y


class lFilter_notch(object):
	def __init__(self, remove_freq, quality_factor, sample_rate):
		b, a = iirnotch(w0=remove_freq, Q=quality_factor, fs=sample_rate)
		self.coefA = a
		self.coefB = b
		self.order = len(self.coefA) - 1
		self.z = [0] * self.order

	def lfilt(self, data):
		y = (data * self.coefB[0]) + self.z[0]
		for i in range(0, self.order):
			if (i < self.order - 1):
				self.z[i] = (data * self.coefB[i+1]) + (self.z[i+1]) - (self.coefA[i+1] * y)
			else:
				self.z[i] = (data * self.coefB[i+1]) - (self.coefA[i+1] * y)
		return y


class lFilter_moving_average(object):
    def __init__(self, window_size):
        self.window_size = window_size
        self.values = []
        self.sum = 0

    def lfilt(self, value):
        self.values.append(value)
        self.sum += value
        if len(self.values) > self.window_size:
            self.sum -= self.values.pop(0)
        return float(self.sum) / len(self.values)


# def butter_bandpass_filter(data, lowcut, highcut, sample_rate, order=2):
#     b, a = butter_bandpass(lowcut, highcut, sample_rate, order=order)
#     y = lfilter(b, a, data)
#     return y
