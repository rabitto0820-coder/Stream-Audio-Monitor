"""Real-time safety limiter used by the monitor output."""

import numpy as np
from scipy.signal import butter, sosfilt


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


class YouTubePlaybackNormalizer:
    """Playback-gain preview for YouTube-style loudness normalization."""

    def __init__(self, target_lufs=-14.0):
        self.target_lufs = float(target_lufs)
        self.enabled = False
        self.gain_db = 0.0

    def reset(self):
        self.gain_db = 0.0

    def set_target(self, target_lufs):
        self.target_lufs = float(target_lufs)
        self.reset()

    def process(self, data, integrated_lufs):
        if not self.enabled or integrated_lufs <= -69.0:
            return data

        # This preview only turns down loud content.  It never boosts quiet
        # material and does not follow short-term loudness like a compressor.
        self.gain_db = float(
            np.clip(self.target_lufs - integrated_lufs, -20.0, 0.0)
        )
        return data * (10.0 ** (self.gain_db / 20.0))


class PhoneSpeakerPreview:
    """Approximate the bandwidth and mono playback of a small phone speaker."""

    def __init__(self, sample_rate=48000):
        self.sample_rate = int(sample_rate)
        self.enabled = False
        self.sos = None
        self.zi = None
        self.configure(sample_rate=sample_rate)

    def configure(self, sample_rate=None):
        if sample_rate is not None:
            self.sample_rate = int(sample_rate)

        nyquist = self.sample_rate / 2.0
        low_cut = 180.0
        high_cut = min(9000.0, nyquist * 0.90)
        self.sos = butter(
            2,
            [low_cut / nyquist, high_cut / nyquist],
            btype="bandpass",
            output="sos",
        )
        self.reset()

    def reset(self):
        self.zi = np.zeros((len(self.sos), 2), dtype=np.float64)

    def process(self, data):
        if not self.enabled or data.size == 0:
            return data

        # Small phone speakers are effectively mono and do not reproduce
        # deep bass or the highest treble. Level-match the result so the
        # listener judges the tonal change rather than a simple volume drop.
        mono = np.mean(data, axis=1)
        filtered, self.zi = sosfilt(self.sos, mono, zi=self.zi)

        input_rms = float(np.sqrt(np.mean(np.square(mono))))
        output_rms = float(np.sqrt(np.mean(np.square(filtered))))
        if input_rms > 1.0e-6 and output_rms > 1.0e-6:
            gain = min(input_rms / output_rms, 10.0 ** (8.0 / 20.0))
            filtered *= gain

        return np.repeat(filtered[:, np.newaxis], data.shape[1], axis=1)


class BassMonoPreview:
    """Keep stereo highs while folding the bass range to mono."""

    def __init__(self, sample_rate=48000, channels=2, cutoff_hz=150.0):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.cutoff_hz = float(cutoff_hz)
        self.enabled = False
        self.configure(sample_rate, channels)

    def configure(self, sample_rate=None, channels=None):
        if sample_rate is not None:
            self.sample_rate = int(sample_rate)
        if channels is not None:
            self.channels = int(channels)

        nyquist = self.sample_rate / 2.0
        cutoff = min(self.cutoff_hz, nyquist * 0.90)
        self.sos = butter(
            4,
            cutoff / nyquist,
            btype="low",
            output="sos",
        )
        self.reset()

    def reset(self):
        self.state = np.zeros((len(self.sos), 2, self.channels))

    def process(self, data):
        if not self.enabled or data.size == 0 or data.shape[1] < 2:
            return data

        low, self.state = sosfilt(
            self.sos,
            data,
            axis=0,
            zi=self.state,
        )
        high = data - low
        mono_low = np.mean(low, axis=1, keepdims=True)
        return high + np.repeat(mono_low, data.shape[1], axis=1)
