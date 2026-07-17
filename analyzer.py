import numpy as np

def get_volume(audio):
    """音量(RMS)を計算"""
    return np.sqrt(np.mean(audio ** 2))