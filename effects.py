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


class LoudnessNormalizer:
    """Slow gain rider that moves Short-term LUFS toward a target."""

    def __init__(self, target_lufs=-14.0):
        self.target_lufs = float(target_lufs)
        self.enabled = False
        self.gain_db = 0.0

    def reset(self):
        self.gain_db = 0.0

    def set_target(self, target_lufs):
        self.target_lufs = float(target_lufs)
        self.reset()

    def process(self, data, measured_lufs):
        if not self.enabled or measured_lufs <= -69.0:
            return data

        desired_gain = np.clip(self.target_lufs - measured_lufs, -12.0, 12.0)
        self.gain_db += np.clip(desired_gain - self.gain_db, -0.05, 0.05)

        return data * (10.0 ** (self.gain_db / 20.0))