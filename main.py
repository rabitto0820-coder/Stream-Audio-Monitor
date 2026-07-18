import sys
import sounddevice as sd

from PyQt6.QtWidgets import QApplication

from audio import callback
from ui import MainWindow


SAMPLERATE = 48000
CHANNELS = 2
BLOCKSIZE = 2048


stream = None



def start_stream(input_device, output_device):

    global stream


    if stream is not None:

        stream.stop()
        stream.close()


    stream = sd.Stream(
        device=(
            input_device,
            output_device
        ),
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        blocksize=BLOCKSIZE,
        latency="low",
        callback=callback
    )


    stream.start()



def stop_stream():

    global stream


    if stream is not None:

        stream.stop()
        stream.close()

        stream = None





print("======================================")
print(" Stream Audio Monitor")
print("======================================")
print("Version 1.0")



app = QApplication(sys.argv)



window = MainWindow(
    start_stream,
    stop_stream
)


window.show()



try:

    sys.exit(
        app.exec()
    )


finally:

    stop_stream()