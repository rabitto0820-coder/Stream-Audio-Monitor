"""Real-time safety limiter used by the monitor output."""

import numpy as np


class SafetyLimiter:
    """Peak limiter with instant attack and smooth release."""

    def __init__(self, sample_rate=48000, ceiling_db=-1.0, release_ms=100.0):
        self.sample_rate = int(sample_rate)
        self.ceiling_db = float(ceiling_db)
        self.release_ms = float(release_ms)
        self.enabled = False
        self.gain = 1.0

    def configure(self, sample_rate=None, ceiling_db=None):
        if sample_rate is not None:
            self.sample_rate = int(sample_rate)
        if ceiling_db is not None:
            self.ceiling_db = float(ceiling_db)
        self.reset()

    def reset(self):
        self.gain = 1.0

    @property
    def ceiling_amplitude(self):
        return 10.0 ** (self.ceiling_db / 20.0)

    def process(self, data):
        if not self.enabled or data.size == 0:
            return data

        ceiling = self.ceiling_amplitude
        input_peak = float(np.max(np.abs(data)))

        if input_peak > ceiling:
            self.gain = min(self.gain, ceiling / input_peak)
        else:
            release_samples = max(
                1.0,
                self.sample_rate * self.release_ms / 1000.0
            )
            release = 1.0 - np.exp(-len(data) / release_samples)
            self.gain += (1.0 - self.gain) * release

        return np.clip(data * self.gain, -ceiling, ceiling)