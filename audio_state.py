"""
GUIとAudio Engineで共有するデータ
"""

import numpy as np


class AudioState:

    def __init__(self):

        # Peak(dBFS)
        self.peak_db = -60.0

        # RMS(dBFS)
        self.rms_db = -60.0

        # FFT表示用
        self.spectrum = np.zeros(512, dtype=np.float32)

        # サンプルレート
        self.sample_rate = 48000

        # 入力信号（FFT計算用）
        self.last_audio = np.zeros((2048, 2), dtype=np.float32)


audio_state = AudioState()