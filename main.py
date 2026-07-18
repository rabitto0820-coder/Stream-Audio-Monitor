import sys
import sounddevice as sd

from PyQt6.QtWidgets import QApplication

from audio import callback
from ui import MainWindow


INPUT_DEVICE = 23
OUTPUT_DEVICE = 19

SAMPLERATE = 48000
CHANNELS = 2
BLOCKSIZE = 2048


print("======================================")
print(" Stream Audio Monitor")
print("======================================")
print("Version 1.0")


# 音声ストリーム開始
stream = sd.Stream(
    device=(INPUT_DEVICE, OUTPUT_DEVICE),
    samplerate=SAMPLERATE,
    channels=CHANNELS,
    blocksize=BLOCKSIZE,
    latency="low",
    callback=callback
)

stream.start()


# PyQt6起動
app = QApplication(sys.argv)

window = MainWindow()
window.show()


try:
    sys.exit(app.exec())

finally:
    stream.stop()
    stream.close()