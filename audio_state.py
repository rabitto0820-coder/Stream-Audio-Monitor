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
        self.codec_delta_active = False

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

        # Runtime audio issues are written by the audio callback and read by
        # the GUI timer.  Keeping this state here avoids touching Qt widgets
        # from the real-time audio thread.
        self.runtime_error_count = 0
        self.runtime_error_message = ""

        self.sample_rate = 48000

        self.last_audio = np.zeros(
            (2048, 2),
            dtype=np.float32
        )

    def reset_runtime_error(self):
        """Clear runtime audio diagnostics when a new stream starts."""
        self.runtime_error_message = ""

    def report_runtime_error(self, message):
        """Store a new callback warning without repeatedly reporting it."""
        message = str(message).strip()
        if not message or message == self.runtime_error_message:
            return

        self.runtime_error_message = message
        self.runtime_error_count += 1


audio_state = AudioState()
