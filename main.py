import sys

import sounddevice as sd

from PyQt6.QtWidgets import QApplication

from audio import callback, configure_audio
from check_devices import validate_audio_settings
from ui import MainWindow


stream = None


def start_stream(
    input_device,
    output_device,
    samplerate,
    blocksize
):
    global stream

    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None

        print("====================")
        print("Audio Check")
        print("Input:", input_device)
        print("Output:", output_device)
        print("Sample Rate:", samplerate)

        valid, error = validate_audio_settings(
            input_device,
            output_device,
            samplerate
        )

        if not valid:
            print("====================")
            print("AUDIO SETTING ERROR")
            print(error)
            print("====================")
            return False

        print("Audio Check OK")
        print("====================")
        print("Audio Start")
        print("Buffer:", blocksize)
        print("====================")

        # 新しいストリーム用にLUFS・Peakなどのメーターをリセット
        configure_audio(samplerate, channels=2)

        stream = sd.Stream(
            device=(
                input_device,
                output_device
            ),
            samplerate=samplerate,
            channels=2,
            blocksize=blocksize,
            latency="high",
            callback=callback
        )

        stream.start()
        return True

    except Exception as error:
        print("====================")
        print("AUDIO ERROR")
        print(error)
        print("====================")

        stream = None
        return False


def stop_stream():
    global stream

    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass

        stream = None


print("======================================")
print(" Stream Audio Monitor")
print("======================================")
print("Version 1.2")

app = QApplication(sys.argv)

window = MainWindow(
    start_stream,
    stop_stream
)

window.show()

try:
    sys.exit(app.exec())
finally:
    stop_stream()