import sys
import sounddevice as sd

from PyQt6.QtWidgets import QApplication

from ui import MainWindow
from audio import callback


# ========= Audio Settings =========

INPUT_DEVICE = 23
OUTPUT_DEVICE = 19

SAMPLERATE = 48000
CHANNELS = 2
BLOCKSIZE = 2048

# ==================================


def create_stream():

    return sd.Stream(
        device=(INPUT_DEVICE, OUTPUT_DEVICE),
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        blocksize=BLOCKSIZE,
        latency="low",
        callback=callback
    )


def main():

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    stream = create_stream()

    try:

        stream.start()

        sys.exit(app.exec())

    finally:

        stream.stop()
        stream.close()


if __name__ == "__main__":
    main()