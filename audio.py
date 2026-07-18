import numpy as np

from audio_state import audio_state



def callback(
    indata,
    outdata,
    frames,
    time,
    status
):

    if status:
        print(status)


    # 音をそのまま出力
    outdata[:] = indata


    # コピー
    data = indata.copy()


    # ステレオ → モノラル
    mono = np.mean(
        data,
        axis=1
    )


    # RMS計算
    volume = np.sqrt(
        np.mean(
            mono ** 2
        )
    )


    # dB変換
    if volume > 0:
        rms_db = 20 * np.log10(volume)
    else:
        rms_db = -60.0


    # FFT
    fft = np.abs(
        np.fft.rfft(
            mono
        )
    )


    # FFT正規化
    if np.max(fft) > 0:

        fft = fft / np.max(fft)



    # AudioStateへ保存

        # AudioStateへ保存

    audio_state.rms_db = rms_db

    audio_state.peak_db = rms_db


    # True Peak計算
    true_peak = np.max(
        np.abs(data)
    )

    if true_peak > 0:
        true_peak_db = 20 * np.log10(true_peak)
    else:
        true_peak_db = -60.0


    audio_state.true_peak_db = true_peak_db


    audio_state.last_audio = data


        # Spectrum用512ポイントへ縮小

    if len(fft) >= 512:

        audio_state.spectrum[:] = fft[:512]

    else:

        audio_state.spectrum[:] = 0

        audio_state.spectrum[:len(fft)] = fft
    