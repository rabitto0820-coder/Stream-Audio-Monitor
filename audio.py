import numpy as np

from effects import process
from audio_state import audio_state
from analyzer import get_spectrum



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
    processed = process(
        indata.copy()
    )



    # 最新音声を保存
    audio_state.last_audio = (
        processed.copy()
    )



    # ==========================
    # FFT解析
    # ==========================

    freqs, spectrum = get_spectrum(
        processed,
        audio_state.sample_rate
    )


    # 振幅をdBへ変換
    spectrum_db = 20 * np.log10(
        spectrum + 1e-6
    )


    # -60dB～0dBを0～1へ変換
    spectrum_db = np.clip(
        (spectrum_db + 60) / 60,
        0,
        1
    )


    # GUI表示用へコピー

    length = min(
        len(audio_state.spectrum),
        len(spectrum_db)
    )


    audio_state.spectrum[:] = 0


    audio_state.spectrum[:length] = (
        spectrum_db[:length]
    )



    # ==========================
    # Peak / RMS計算
    # ==========================

    rms = np.sqrt(
        np.mean(
            processed ** 2
        )
    )


    peak = np.max(
        np.abs(processed)
    )


    audio_state.rms_db = linear_to_db(
        rms
    )


    audio_state.peak_db = linear_to_db(
        peak
    )



    # スピーカー出力

    outdata[:] = processed