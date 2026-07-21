"""Offline analysis for PCM WAV files exported from a DAW."""

from pathlib import Path
import wave

import numpy as np
from scipy.signal import resample_poly

from loudness import LoudnessMeter


def analyze_wav(path, target_lufs=-14.0):
    """Return loudness and YouTube playback-gain estimates for one WAV file."""
    file_path = Path(path)

    with wave.open(str(file_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        total_frames = wav_file.getnframes()

        if channels < 1 or channels > 2:
            raise ValueError("Only mono or stereo WAV files are supported.")

        if sample_width not in (1, 2, 3, 4):
            raise ValueError("Unsupported WAV bit depth.")

        meter = LoudnessMeter(sample_rate=sample_rate, channels=channels)
        peak = 0.0
        true_peak = 0.0

        while True:
            raw = wav_file.readframes(16384)
            if not raw:
                break

            samples = _decode_pcm(raw, sample_width, channels)
            peak = max(peak, float(np.max(np.abs(samples))))
            true_peak = max(true_peak, _estimate_true_peak(samples))
            momentary, short_term, integrated = meter.process(samples)

    if total_frames == 0:
        raise ValueError("The WAV file contains no audio samples.")

    youtube_gain_db = min(0.0, float(target_lufs) - integrated)
    youtube_percent = 100.0 * (10.0 ** (youtube_gain_db / 20.0))
    true_peak_db = _decibels(true_peak)

    return {
        "name": file_path.name,
        "duration_seconds": total_frames / sample_rate,
        "sample_rate": sample_rate,
        "channels": channels,
        "peak_db": _decibels(peak),
        "true_peak_db": true_peak_db,
        "true_peak_headroom_db": -true_peak_db,
        "lufs_m": momentary,
        "lufs_s": short_term,
        "lufs_i": integrated,
        "youtube_gain_db": youtube_gain_db,
        "youtube_percent": youtube_percent,
        "youtube_advice": _youtube_advice(
            integrated,
            true_peak_db,
            youtube_gain_db,
        ),
        "youtube_readiness": _youtube_readiness(
            integrated,
            true_peak_db,
            youtube_gain_db,
            target_lufs,
        ),
    }


def compare_wavs(reference_path, preview_path):
    """Compare a source WAV with a codec or playback-preview WAV."""
    reference = analyze_wav(reference_path)
    preview = analyze_wav(preview_path)

    reference_bands = _spectral_band_levels(reference_path)
    preview_bands = _spectral_band_levels(preview_path)

    return {
        "reference": reference,
        "preview": preview,
        "duration_difference_seconds": (
            preview["duration_seconds"] - reference["duration_seconds"]
        ),
        "lufs_difference_db": preview["lufs_i"] - reference["lufs_i"],
        "peak_difference_db": preview["peak_db"] - reference["peak_db"],
        "presence_difference_db": (
            preview_bands["presence"] - reference_bands["presence"]
        ),
        "high_band_difference_db": (
            preview_bands["high"] - reference_bands["high"]
        ),
    }


def _spectral_band_levels(path):
    """Measure average spectral energy in useful music-comparison bands."""
    file_path = Path(path)
    chunk_size = 16384
    window = np.hanning(chunk_size).astype(np.float32)
    band_power = {"presence": 0.0, "high": 0.0}
    window_count = 0

    with wave.open(str(file_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()

        while True:
            raw = wav_file.readframes(chunk_size)
            if not raw:
                break

            samples = _decode_pcm(raw, sample_width, channels)
            if len(samples) < chunk_size:
                samples = np.pad(samples, ((0, chunk_size - len(samples)), (0, 0)))

            mono = np.mean(samples, axis=1) * window
            spectrum = np.abs(np.fft.rfft(mono)) ** 2
            frequencies = np.fft.rfftfreq(chunk_size, 1.0 / sample_rate)

            for name, low_hz, high_hz in (
                ("presence", 4000.0, 8000.0),
                ("high", 8000.0, 16000.0),
            ):
                mask = (frequencies >= low_hz) & (frequencies < high_hz)
                if np.any(mask):
                    band_power[name] += float(np.mean(spectrum[mask]))

            window_count += 1

    if window_count == 0:
        raise ValueError("The WAV file contains no audio samples.")

    return {
        name: _power_decibels(power / window_count)
        for name, power in band_power.items()
    }


def _decode_pcm(raw, sample_width, channels):
    if sample_width == 1:
        values = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        values = (values - 128.0) / 128.0
    elif sample_width == 2:
        values = np.frombuffer(raw, dtype="<i2").astype(np.float32)
        values /= 32768.0
    elif sample_width == 3:
        bytes_ = np.frombuffer(raw, dtype=np.uint8).reshape((-1, 3))
        values = (
            bytes_[:, 0].astype(np.int32)
            | (bytes_[:, 1].astype(np.int32) << 8)
            | (bytes_[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        values = values.astype(np.float32) / 8388608.0
    else:
        values = np.frombuffer(raw, dtype="<i4").astype(np.float32)
        values /= 2147483648.0

    return values.reshape((-1, channels))


def _decibels(amplitude):
    if amplitude <= 0.0:
        return -60.0

    return 20.0 * np.log10(amplitude)


def _estimate_true_peak(samples):
    """Return a 4x oversampled true-peak estimate for one PCM block."""
    oversampled = resample_poly(samples, 4, 1, axis=0)
    return float(np.max(np.abs(oversampled)))


def _youtube_advice(integrated_lufs, true_peak_db, youtube_gain_db):
    """Create a short, practical YouTube preparation note."""
    notes = []

    if true_peak_db > -1.0:
        notes.append(
            "True Peak is above -1.0 dBTP. Lower the master or use a limiter."
        )
    else:
        notes.append("True Peak has at least 1 dB of encoding headroom.")

    if youtube_gain_db < -0.1:
        notes.append(
            f"YouTube is expected to lower playback by {-youtube_gain_db:.1f} dB."
        )
    elif integrated_lufs < -14.5:
        notes.append("YouTube usually will not raise a quieter master.")
    else:
        notes.append("Playback loudness is close to the -14 LUFS reference.")

    return " ".join(notes)


def _youtube_readiness(
    integrated_lufs,
    true_peak_db,
    youtube_gain_db,
    target_lufs,
):
    """Return a simple, UI-friendly offline YouTube check result."""
    if true_peak_db > -1.0:
        return "TRUE_PEAK"

    if youtube_gain_db < -0.5:
        return "VOLUME_REDUCTION"

    if integrated_lufs < target_lufs - 3.0:
        return "QUIET"

    return "READY"


def _power_decibels(power):
    if power <= 0.0:
        return -120.0

    return 10.0 * np.log10(power)
