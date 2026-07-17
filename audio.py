import numpy as np
from effects import process, LIMITER


def linear_to_db(value):
    if value <= 1e-12:
        return -120.0
    return 20 * np.log10(value)


def meter(db):
    db = max(-60, min(0, db))
    length = int((db + 60) / 60 * 30)
    return "█" * length + "-" * (30 - length)


def callback(indata, outdata, frames, time_info, status):

    if status:
        print(status)

    processed = process(indata)

    rms = np.sqrt(np.mean(processed ** 2))
    peak = np.max(np.abs(processed))

    rms_db = linear_to_db(rms)
    peak_db = linear_to_db(peak)

    limiter_text = "ON " if LIMITER else "OFF"

    print(
        f"\rLimiter:{limiter_text}  "
        f"Peak [{meter(peak_db)}] {peak_db:6.2f} dBFS   "
        f"RMS [{meter(rms_db)}] {rms_db:6.2f} dBFS",
        end=""
    )

    outdata[:] = processed