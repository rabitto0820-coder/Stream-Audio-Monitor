import numpy as np

GAIN = 2.0
LIMITER = True


def soft_limiter(audio):
    threshold = 0.95

    over = np.abs(audio) > threshold

    audio[over] = (
        np.sign(audio[over])
        * (
            threshold
            + np.tanh(
                (np.abs(audio[over]) - threshold) / (1.0 - threshold)
            )
            * (1.0 - threshold)
        )
    )

    return audio


def process(audio):

    audio = audio * GAIN

    if LIMITER:
        audio = soft_limiter(audio)

    return np.clip(audio, -1.0, 1.0)