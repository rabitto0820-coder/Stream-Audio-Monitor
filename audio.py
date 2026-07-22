import time

import numpy as np
from scipy.signal import resample_poly

from aac import AACPreview
from audio_state import audio_state
from effects import (
    BassMonoPreview,
    LoudnessNormalizer,
    PhoneSpeakerPreview,
    SafetyLimiter,
    YouTubePlaybackNormalizer,
)
from loudness import LoudnessMeter
from youtube import YouTubeOpusPreview


opus_simulation = False
aac_simulation = False
mono_preview = False
bass_mono_preview = False
phone_speaker_preview = False
monitor_muted = False
bypass_effects = False
codec_delta_monitor = False

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

phone_speaker = PhoneSpeakerPreview(
    sample_rate=sample_rate
)

bass_mono = BassMonoPreview(
    sample_rate=sample_rate,
    channels=2,
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

    phone_speaker.configure(
        sample_rate=sample_rate
    )

    bass_mono.configure(
        sample_rate=sample_rate,
        channels=channels,
    )

    normalizer.reset()
    audio_state.normalizer_gain_db = 0.0
    youtube_normalizer.reset()
    audio_state.youtube_gain_db = 0.0

    audio_state.peak_db = -60.0
    audio_state.input_peak_db = -60.0
    audio_state.true_peak_db = -60.0
    audio_state.max_true_peak_db = -60.0
    audio_state.rms_db = -60.0

    audio_state.lufs_m = -70.0
    audio_state.lufs_s = -70.0
    audio_state.lufs_i = -70.0
    audio_state.lufs_measurement_seconds = 0.0
    audio_state.codec_preview_mode = "OFF"
    audio_state.codec_delta_active = False
    audio_state.codec_difference.fill(0.0)
    audio_state.codec_difference_active = False

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


def set_codec_delta_monitor(enabled):
    global codec_delta_monitor

    codec_delta_monitor = bool(enabled)


def set_mono_preview(enabled):
    global mono_preview

    mono_preview = bool(enabled)


def set_bass_mono_preview(enabled):
    global bass_mono_preview

    bass_mono_preview = bool(enabled)
    bass_mono.enabled = bass_mono_preview
    bass_mono.reset()


def set_phone_speaker_preview(enabled):
    global phone_speaker_preview

    phone_speaker_preview = bool(enabled)
    phone_speaker.enabled = phone_speaker_preview
    phone_speaker.reset()


def set_monitor_muted(enabled):
    global monitor_muted

    monitor_muted = bool(enabled)


def set_bypass_effects(enabled):
    global bypass_effects

    bypass_effects = bool(enabled)
    normalizer.reset()
    youtube_normalizer.reset()
    limiter.reset()
    bass_mono.reset()
    phone_speaker.reset()
    audio_state.normalizer_gain_db = 0.0
    audio_state.youtube_gain_db = 0.0


def reset_clip_counter():
    audio_state.clip_count = 0
    audio_state.clip_latched = False
    audio_state.clip_hold_until = 0.0


def reset_integrated_loudness():
    loudness_meter.reset_integrated()
    audio_state.lufs_i = -70.0
    audio_state.lufs_measurement_seconds = 0.0
    audio_state.max_true_peak_db = -60.0


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


def set_youtube_target(target_lufs):
    youtube_normalizer.set_target(target_lufs)
    audio_state.youtube_gain_db = 0.0


def _decibels(amplitude):
    if amplitude > 0:
        return 20.0 * np.log10(amplitude)

    return -60.0


def callback(indata, outdata, frames, time_info, status):
    if status:
        print(status)

    data = indata.copy()
    codec_reference = np.zeros_like(data)

    audio_state.input_peak_db = _decibels(
        float(np.max(np.abs(data)))
    )

    if bypass_effects:
        audio_state.codec_preview_mode = "BYPASS"

    elif opus_simulation:
        data = opus_filter(data)
        codec_reference = youtube_preview.last_reference
        audio_state.codec_preview_mode = (
            "REAL OPUS"
            if youtube_preview.real_codec_available
            else "OPUS APPROX"
        )

    elif aac_simulation:
        data = aac_preview.process(data)
        codec_reference = aac_preview.last_reference
        audio_state.codec_preview_mode = (
            "REAL AAC"
            if aac_preview.real_codec_available
            else "AAC APPROX"
        )

    else:
        audio_state.codec_preview_mode = "OFF"

    codec_active = (opus_simulation or aac_simulation) and not bypass_effects
    audio_state.codec_difference_active = codec_active

    if codec_active:
        reference_mono = np.mean(codec_reference, axis=1)
        codec_mono = np.mean(data, axis=1)
        # A fixed FFT size gives the graph the same full-width frequency
        # resolution regardless of the selected audio buffer size.
        reference_fft = np.abs(np.fft.rfft(reference_mono, n=1024))
        codec_fft = np.abs(np.fft.rfft(codec_mono, n=1024))
        difference_db = np.abs(
            20.0 * np.log10((codec_fft + 1e-8) / (reference_fft + 1e-8))
        )
        # 18 dB or more is displayed at full height.
        difference = np.clip(difference_db / 18.0, 0.0, 1.0)
        audio_state.codec_difference[:] = 0.0
        audio_state.codec_difference[:min(512, len(difference))] = difference[:512]
    else:
        audio_state.codec_difference.fill(0.0)

    delta_mode_active = codec_delta_monitor and codec_active
    audio_state.codec_delta_active = delta_mode_active

    if delta_mode_active:
        # Audition only the signal changed by the codec.
        data = (codec_reference - data) * 2.0

    (
        audio_state.lufs_m,
        audio_state.lufs_s,
        audio_state.lufs_i,
    ) = loudness_meter.process(data)
    audio_state.lufs_measurement_seconds += frames / sample_rate

    if bypass_effects or delta_mode_active:
        audio_state.youtube_gain_db = 0.0
        audio_state.normalizer_gain_db = 0.0
    else:
        data = youtube_normalizer.process(data, audio_state.lufs_i)
        audio_state.youtube_gain_db = youtube_normalizer.gain_db

        data = normalizer.process(data, audio_state.lufs_s)
        audio_state.normalizer_gain_db = normalizer.gain_db

        data = bass_mono.process(data)
        data = phone_speaker.process(data)

        data = limiter.process(data)

        if mono_preview and data.shape[1] >= 2:
            mono = np.mean(data, axis=1, keepdims=True)
            data = np.repeat(mono, data.shape[1], axis=1)

    if delta_mode_active:
        # Delta monitoring can be unexpectedly loud on transient material.
        data = np.clip(data, -0.99, 0.99)

    if monitor_muted:
        outdata.fill(0.0)
    else:
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
    audio_state.max_true_peak_db = max(
        audio_state.max_true_peak_db,
        audio_state.true_peak_db,
    )

    fft = np.abs(
        np.fft.rfft(mono, n=1024)
    )

    if np.max(fft) > 0:
        fft = fft / np.max(fft)

    audio_state.spectrum[:] = 0.0
    audio_state.spectrum[:min(512, len(fft))] = fft[:512]

    audio_state.last_audio = data
