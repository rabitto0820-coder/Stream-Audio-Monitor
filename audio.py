import numpy as np

from effects import process, LIMITER


current_peak_db = -60.0
current_rms_db = -60.0


def linear_to_db(value):

    if value <= 1e-12:
        return -120.0

    return 20 * np.log10(value)


def callback(indata, outdata, frames, time_info, status):

    global current_peak_db
    global current_rms_db

    if status:
        print(status)

    processed = process(indata)

    rms = np.sqrt(np.mean(processed ** 2))
    peak = np.max(np.abs(processed))

    rms_db = linear_to_db(rms)
    peak_db = linear_to_db(peak)

    current_peak_db = rms_db
    current_rms_db = peak_db

    outdata[:] = processed