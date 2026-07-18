"""Low-latency approximation of YouTube's Opus playback character.

This is a real-time preview, not a bit-perfect Opus encoder/decoder. It
models the bandwidth limit without introducing a block boundary click every
time the sounddevice callback runs.
"""

import numpy as np
from scipy.signal import butter, sosfilt


class YouTubeOpusPreview:
    """Stateful low-pass preview suitable for a real-time audio callback."""

    def __init__(self, sample_rate=48000, channels=2, bitrate_kbps=128):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.bitrate_kbps = int(bitrate_kbps)
        self._sos = None
        self._state = None
        self.reset()

    def configure(self, sample_rate, channels=2, bitrate_kbps=None):
        """Apply stream settings and reset filter memory for a new stream."""
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

        if bitrate_kbps is not None:
            self.bitrate_kbps = int(bitrate_kbps)

        self.reset()

    def reset(self):
        """Create a stable filter and clear its previous audio state."""
        cutoff = self._cutoff_frequency()
        nyquist = self.sample_rate / 2.0

        if cutoff >= nyquist * 0.99:
            self._sos = None
            self._state = None
            return

        self._sos = butter(
            6,
            cutoff / nyquist,
            btype="low",
            output="sos",
        )
        self._state = np.zeros((self._sos.shape[0], 2, self.channels))

    def process(self, data):
        """Return a bandwidth-limited preview while preserving filter state."""
        if self._sos is None:
            return data.copy()

        if data.ndim != 2 or data.shape[1] != self.channels:
            self.configure(self.sample_rate, data.shape[1])

        filtered, self._state = sosfilt(
            self._sos,
            data,
            axis=0,
            zi=self._state,
        )
        return filtered.astype(data.dtype, copy=False)

    def _cutoff_frequency(self):
        """Use conservative bandwidth limits for the selected Opus bitrate."""
        if self.bitrate_kbps <= 96:
            return 14000.0
        if self.bitrate_kbps <= 128:
            return 16000.0
        if self.bitrate_kbps <= 160:
            return 18000.0
        return 20000.0