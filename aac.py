"""Low-latency AAC-style preview approximation for real-time monitoring."""

import numpy as np
from scipy.signal import butter, sosfilt


class AACPreview:
    def __init__(self, sample_rate=48000, channels=2):
        self.sample_rate = sample_rate
        self.channels = channels

        self.configure(
            sample_rate,
            channels
        )

    def configure(self, sample_rate, channels=2):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

        cutoff = min(
            18000.0,
            self.sample_rate * 0.45
        )

        self.sos = butter(
            4,
            cutoff / (self.sample_rate / 2.0),
            btype="low",
            output="sos",
        )

        self.state = np.zeros(
            (
                self.sos.shape[0],
                2,
                self.channels
            )
        )

    def process(self, data):
        filtered, self.state = sosfilt(
            self.sos,
            data,
            axis=0,
            zi=self.state,
        )

        return (
            np.round(filtered * 16384.0)
            /
            16384.0
        ).astype(data.dtype)