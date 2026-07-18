import numpy as np

from effects import process
from audio_state import audio_state


def linear_to_db(value):
    """
    リニア値をdBFSへ変換
    """

    if value <= 1e-12:
        return -120.0

    return 20 * np.log10(value)


def callback(indata, outdata, frames, time_info, status):
    """
    sounddevice コールバック
    """

    if status:
        print(status)

    # エフェクト処理
    processed = process(indata.copy())

    # GUI・FFT用に最新の音声を保存
    audio_state.last_audio = processed.copy()

    # Peak / RMS 計算
    rms = np.sqrt(np.mean(processed ** 2))
    peak = np.max(np.abs(processed))

    audio_state.rms_db = linear_to_db(rms)
    audio_state.peak_db = linear_to_db(peak)

    # スピーカーへ出力
    outdata[:] = processed