import numpy as np

from effects import process


# ==========================
# GUI共有データ
# ==========================

current_peak_db = -60.0
current_rms_db = -60.0


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

    global current_peak_db
    global current_rms_db

    if status:
        print(status)

    # エフェクト処理
    processed = process(indata)

    # Peak/RMS計算
    rms = np.sqrt(np.mean(processed ** 2))
    peak = np.max(np.abs(processed))

    rms_db = linear_to_db(rms)
    peak_db = linear_to_db(peak)

    # GUIへ渡す
    current_peak_db = peak_db
    current_rms_db = rms_db

    # 出力
    outdata[:] = processed