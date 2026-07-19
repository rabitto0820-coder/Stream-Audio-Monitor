import time

import numpy as np
from scipy.signal import resample_poly

from aac import AACPreview
from audio_state import audio_state
from effects import (
    LoudnessNormalizer,
    SafetyLimiter,
    YouTubePlaybackNormalizer,
)
from loudness import LoudnessMeter
from youtube import YouTubeOpusPreview


opus_simulation = False
aac_simulation = False
mono_preview = False

sample_rate = 48000

loudness_meter = LoudnessMeter(
    sample_rate=sample_rate,
    channels=2
)

youtube_preview = YouTubeOpusPreview(
    sample_rate=sample_rate,
    channels=2
)

aac_preview = AACPreview(
    sample_rate=sample_rate,
    channels=2
)

limiter = SafetyLimiter(
    sample_rate=sample_rate,
    ceiling_db=-1.0
)

normalizer = LoudnessNormalizer(
    target_lufs=-14.0
)

youtube_normalizer = YouTubePlaybackNormalizer(
    target_lufs=-14.0
)


def configure_audio(new_sample_rate, channels=2):
    global sample_rate

    sample_rate = int(new_sample_rate)

    audio_state.sample_rate = sample_rate
    audio_state.correlation = 0.0

    loudness_meter.reset(
        sample_rate=sample_rate,
        channels=channels
    )

    youtube_preview.configure(
        sample_rate=sample_rate,
        channels=channels
    )

    aac_preview.configure(
        sample_rate=sample_rate,
        channels=channels
    )

    limiter.configure(
        sample_rate=sample_rate
    )

    normalizer.reset()
    audio_state.normalizer_gain_db = 0.0
    youtube_normalizer.reset()
    audio_state.youtube_gain_db = 0.0

    audio_state.peak_db = -60.0
    audio_state.input_peak_db = -60.0
    audio_state.true_peak_db = -60.0
    audio_state.rms_db = -60.0

    audio_state.lufs_m = -70.0
    audio_state.lufs_s = -70.0
    audio_state.lufs_i = -70.0
    audio_state.lufs_measurement_seconds = 0.0

    reset_clip_counter()


def opus_filter(data):
    return youtube_preview.process(data)


def set_opus_bitrate(bitrate_kbps):
    youtube_preview.configure(
        sample_rate=sample_rate,
        channels=youtube_preview.channels,
        bitrate_kbps=bitrate_kbps,
    )


def set_aac_simulation(enabled):
    global aac_simulation, opus_simulation

    aac_simulation = bool(enabled)

    if aac_simulation:
        opus_simulation = False


def set_mono_preview(enabled):
    global mono_preview

    mono_preview = bool(enabled)


def reset_clip_counter():
    audio_state.clip_count = 0
    audio_state.clip_latched = False
    audio_state.clip_hold_until = 0.0


def reset_integrated_loudness():
    loudness_meter.reset_integrated()
    audio_state.lufs_i = -70.0
    audio_state.lufs_measurement_seconds = 0.0


def set_limiter_enabled(enabled):
    limiter.enabled = bool(enabled)
    limiter.reset()


def set_limiter_ceiling(ceiling_db):
    limiter.configure(
        ceiling_db=ceiling_db
    )


def set_normalizer_enabled(enabled):
    normalizer.enabled = bool(enabled)
    normalizer.reset()
    audio_state.normalizer_gain_db = 0.0


def set_normalizer_target(target_lufs):
    normalizer.set_target(target_lufs)
    audio_state.normalizer_gain_db = 0.0


def set_youtube_normalizer_enabled(enabled):
    youtube_normalizer.enabled = bool(enabled)
    youtube_normalizer.reset()
    audio_state.youtube_gain_db = 0.0


def _decibels(amplitude):
    if amplitude > 0:
        return 20.0 * np.log10(amplitude)

    return -60.0


def callback(indata, outdata, frames, time_info, status):
    if status:
        print(status)

    data = indata.copy()

    audio_state.input_peak_db = _decibels(
        float(np.max(np.abs(data)))
    )

    if opus_simulation:
        data = opus_filter(data)

    elif aac_simulation:
        data = aac_preview.process(data)

    (
        audio_state.lufs_m,
        audio_state.lufs_s,
        audio_state.lufs_i,
    ) = loudness_meter.process(data)
    audio_state.lufs_measurement_seconds += frames / sample_rate

    data = youtube_normalizer.process(data, audio_state.lufs_i)
    audio_state.youtube_gain_db = youtube_normalizer.gain_db

    data = normalizer.process(data, audio_state.lufs_s)
    audio_state.normalizer_gain_db = normalizer.gain_db

    data = limiter.process(data)

    if mono_preview and data.shape[1] >= 2:
        mono = np.mean(data, axis=1, keepdims=True)
        data = np.repeat(mono, data.shape[1], axis=1)

    outdata[:] = data

    mono = np.mean(data, axis=1)

    if data.shape[1] >= 2:
        left = data[:, 0]
        right = data[:, 1]

        denominator = float(
            np.sqrt(
                np.sum(left ** 2)
                * np.sum(right ** 2)
            )
        )

        if denominator > 0:
            audio_state.correlation = float(
                np.sum(left * right) / denominator
            )
        else:
            audio_state.correlation = 0.0

    else:
        audio_state.correlation = 1.0

    audio_state.rms_db = _decibels(
        float(
            np.sqrt(
                np.mean(
                    np.square(mono)
                )
            )
        )
    )

    audio_state.peak_db = _decibels(
        float(
            np.max(
                np.abs(data)
            )
        )
    )

    clipped = bool(
        np.any(
            np.abs(data) >= 0.999
        )
    )

    if clipped:
        if not audio_state.clip_latched:
            audio_state.clip_count += 1

        audio_state.clip_latched = True
        audio_state.clip_hold_until = time.monotonic() + 1.5

    else:
        audio_state.clip_latched = False

    true_peak = 0.0

    for channel in range(data.shape[1]):
        oversampled = resample_poly(
            data[:, channel],
            4,
            1
        )

        true_peak = max(
            true_peak,
            float(
                np.max(
                    np.abs(oversampled)
                )
            )
        )

    audio_state.true_peak_db = _decibels(
        true_peak
    )

    fft = np.abs(
        np.fft.rfft(mono)
    )

    if np.max(fft) > 0:
        fft = fft / np.max(fft)

    audio_state.spectrum[:] = 0.0
    audio_state.spectrum[:min(512, len(fft))] = fft[:512]

    audio_state.last_audio = data
