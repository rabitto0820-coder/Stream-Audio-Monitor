import numpy as np


def get_volume(audio):
    """音量(RMS)を計算"""
    return np.sqrt(np.mean(audio ** 2))


def get_spectrum(audio, sample_rate):
    """
    FFTスペクトラムを計算
    戻り値:
        freqs : 周波数(Hz)
        spectrum : 正規化された振幅
    """

    # モノラル化
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # FFT
    fft = np.fft.rfft(audio)

    spectrum = np.abs(fft)

    # 正規化
    if spectrum.max() > 0:
        spectrum = spectrum / spectrum.max()

    freqs = np.fft.rfftfreq(len(audio), d=1 / sample_rate)

    return freqs, spectrum