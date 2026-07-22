"""Shared real-time data between the audio engine and the GUI."""

import numpy as np


class AudioState:
    def __init__(self):
        self.input_peak_db = -60.0
        self.peak_db = -60.0
        self.true_peak_db = -60.0
        self.max_true_peak_db = -60.0

        self.lufs_m = -70.0
        self.lufs_s = -70.0
        self.lufs_i = -70.0
        self.lufs_measurement_seconds = 0.0
        self.normalizer_gain_db = 0.0
        self.youtube_gain_db = 0.0
        self.codec_preview_mode = "OFF"

        self.rms_db = -60.0

        # Stereo correlation: +1.0 is in phase, -1.0 is opposite phase.
        self.correlation = 0.0

        self.clip_count = 0
        self.clip_latched = False
        self.clip_hold_until = 0.0

        self.spectrum = np.zeros(
            512,
            dtype=np.float32
        )

        # Codec Difference Spectrum: 0.0 means no audible spectral change.
        self.codec_difference = np.zeros(
            512,
            dtype=np.float32
        )
        self.codec_difference_active = False

        self.sample_rate = 48000

        self.last_audio = np.zeros(
            (2048, 2),
            dtype=np.float32
        )


audio_state = AudioState()
