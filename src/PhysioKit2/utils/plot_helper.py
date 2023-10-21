from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.animation import TimedAnimation
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np

class FigCanvas(FigureCanvas):
    def __init__(self, channels, ch_colors, sq_flag, parent=None, width=13.8, height=7.5, dpi=100):
        global nChannels, sampling_rate, channel_types
        
        self.max_plot_time = 10 # 30 second time window
        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
        self.x_axis = np.linspace(0, self.max_plot_time, self.max_plot_time*sampling_rate)

        self.plot_signals = []
        self.axs = {}
        self.lines = {}

        self.sq_flag = sq_flag
        if self.sq_flag:
            self.sq_vecs = []
            self.sq_images = {}
        width = width/dpi
        height = height/dpi

        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        # self.fig = Figure(constrained_layout=True)

        for nCh in range(self.nChannels):
            self.plot_signals.append(10 * np.ones(self.max_plot_time * sampling_rate))
    
            if self.sq_flag and channel_types[nCh] == "ppg":
                self.sq_vecs.append(0.5 * np.ones((1, self.max_plot_time * 2))) # 1/0.5 as 0.5 is sq_resolution. 

            if self.nChannels == self.max_plot_channels:
                self.axs[str(nCh)] = self.fig.add_subplot(2, 2, nCh+1)
            else:
                self.axs[str(nCh)] = self.fig.add_subplot(self.nChannels, 1, nCh+1)

            (self.lines[str(nCh)],) = self.axs[str(nCh)].plot(self.x_axis, self.plot_signals[nCh], ch_colors[nCh], markersize=10, linestyle='solid')
            
            if self.sq_flag and channel_types[nCh] == "ppg":
                self.sq_images[str(nCh)] = self.axs[str(nCh)].imshow(
                    self.sq_vecs[nCh], clim=(0,1), cmap=plt.cm.RdYlGn, aspect='auto', alpha=0.5, extent=(0, self.max_plot_time, 0, 1)
                    )
            self.axs[str(nCh)].set_xlabel('Time (seconds)', fontsize=16)
            self.axs[str(nCh)].set_ylabel(channels[nCh], fontsize=16)
            self.axs[str(nCh)].set_xlim(0, self.max_plot_time)
            self.axs[str(nCh)].set_ylim(0, 1)
            self.axs[str(nCh)].yaxis.set_ticks_position('left')
            self.axs[str(nCh)].xaxis.set_ticks_position('bottom')

        super(FigCanvas, self).__init__(self.fig)



class PlotAnimation(TimedAnimation):
    def __init__(self, figCanvas: FigureCanvas, interval: int = 40) -> None:
        self.fig = figCanvas.fig
        self.sq_flag = figCanvas.sq_flag
        global nChannels, sampling_rate, anim_running, channel_types
        self.sampling_rate = sampling_rate

        self.exception_count = 0
        self.max_plot_channels = 4
        self.nChannels = min(nChannels, self.max_plot_channels)  #maximum number of channels for plaotting = 4
        self.channel_types = channel_types[:self.nChannels]
        self.ppg_sq_indices = list(np.where(np.array(channel_types) == "ppg")[0])

        self.max_plot_time = 10 # 30 second time window
        self.event_toggle = False
        self.measure_time = 0.2  # moving max_plot_time sample by 0.2 sec.
        self.max_frames_for_relimiting_axis = self.measure_time * sampling_rate

        self.count_frame = 0
        self.plot_signals = figCanvas.plot_signals
        self.sq_vecs = figCanvas.sq_vecs
        self.axs = figCanvas.axs
        self.lines = figCanvas.lines
        self.sq_images = figCanvas.sq_images
        anim_running = True

        super(PlotAnimation, self).__init__(self.fig, interval, blit=True)


    def new_frame_seq(self):
        return iter(range(int(self.max_plot_time * self.sampling_rate)))


    def _init_draw(self):
        lines = []
        sq_images = []
        for nCh in range(self.nChannels):
            lines.append(self.lines[str(nCh)])
            if self.channel_types[nCh] == "ppg":
                sq_images.append(self.sq_images[str(nCh)])
        lines = tuple(lines)
        sq_images = tuple(sq_images)
        return (lines, sq_images)


    def reset_draw(self):
        self.count_frame = 0 # self.max_plot_time * sampling_rate
        return

    def addSQData(self, value):
        for indx in range(len(self.ppg_sq_indices)):
            self.sq_vecs[self.ppg_sq_indices[indx]] = 1 - value[indx]
            # print(1 - value[indx])
        return

    def addData(self, value):
        self.count_frame += 1
        for nCh in range(self.nChannels):
            self.plot_signals[nCh] = np.roll(self.plot_signals[nCh], -1)
            self.plot_signals[nCh][-1] = value[nCh]
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
        global live_acquisition_flag, marker_event_status
        if live_acquisition_flag:   

            if self.count_frame >= self.max_frames_for_relimiting_axis:
                self.count_frame = 0
                # for nCh in range(self.nChannels):
                #     mx = np.max(self.plot_signals[nCh])
                #     mn = np.min(self.plot_signals[nCh])
                #     self.plot_signals[nCh] = (self.plot_signals[nCh] - mn)/(mx - mn)
                #     # self.axs[str(nCh)].set_ylim(np.min(self.plot_signals[nCh]), np.max(self.plot_signals[nCh]))

                self._drawn_artists = []
                for nCh in range(self.nChannels):
                    mx = np.max(self.plot_signals[nCh])
                    mn = np.min(self.plot_signals[nCh])
                    sig = (self.plot_signals[nCh] - mn)/(mx - mn)
                    self.lines[str(nCh)].set_ydata(sig)
                    if self.sq_flag and self.channel_types[nCh] == "ppg":
                        self.sq_images[str(nCh)].set_data(self.sq_vecs[nCh])
                        self._drawn_artists.append(self.sq_images[str(nCh)])
                    self._drawn_artists.append(self.lines[str(nCh)])

            if self.event_toggle:
                if marker_event_status:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, (5, 5)))
                else:
                    for nCh in range(self.nChannels):
                        self.lines[str(nCh)].set_linestyle((0, ()))
                self.event_toggle = False

            # self._drawn_artists = []
            # for nCh in range(self.nChannels):
            #     mx = np.max(self.plot_signals[nCh])
            #     mn = np.min(self.plot_signals[nCh])
            #     sig = (self.plot_signals[nCh] - mn)/(mx - mn)
            #     self.lines[str(nCh)].set_ydata(sig)
            #     if self.sq_flag and self.channel_types[nCh] == "ppg":
            #         self.sq_images[str(nCh)].set_data(self.sq_vecs[nCh])
            #         self._drawn_artists.append(self.sq_images[str(nCh)])
            #     self._drawn_artists.append(self.lines[str(nCh)])
        return