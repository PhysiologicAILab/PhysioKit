import os
import platform

OS_NAME = ''
try:
    OS_NAME = platform.platform().lower()
except:
    pass

LIVE_ACQUISITION_FLAG = False
HOLD_ACQUISITION_THREAD = True
NCHANNELS = 4                   #default
CHANNEL_TYPES = ["eda", "resp", "ppg", "ppg"]
MARKER_EVENT_STATUS = False
SAMPLING_RATE = 250             #default
CSVFILE_HANDLE = None
ANIM_RUNNING = False
TEMP_FILENAME = ""
