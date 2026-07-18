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


        # FFT表示用データ
        self.spectrum = np.zeros(
            512,
            dtype=np.float32
        )


        # サンプルレート
        self.sample_rate = 48000


        # FFT計算用の最新音声
        self.last_audio = np.zeros(
            (2048, 2),
            dtype=np.float32
        )



# 全ファイル共通で使用する状態
audio_state = AudioState()