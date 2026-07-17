import sounddevice as sd
import time

from audio import callback

INPUT_DEVICE = 23
OUTPUT_DEVICE = 19

SAMPLERATE = 48000
CHANNELS = 2
BLOCKSIZE = 2048

print("======================================")
print(" Stream Audio Monitor")
print("======================================")
print("Version 1.0")
print("Ctrl+Cで終了")

with sd.Stream(
    device=(INPUT_DEVICE, OUTPUT_DEVICE),
    samplerate=SAMPLERATE,
    channels=CHANNELS,
    blocksize=BLOCKSIZE,
    latency="low",
    callback=callback
):
    while True:
        time.sleep(1)