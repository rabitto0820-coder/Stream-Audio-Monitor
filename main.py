import sys

import sounddevice as sd

from PyQt6.QtWidgets import QApplication

from audio import callback

from ui import MainWindow



stream = None



def start_stream(
    input_device,
    output_device,
    samplerate,
    blocksize
):

    global stream



    # 既存Stream停止

    if stream is not None:

        stream.stop()

        stream.close()



    print("====================")

    print("Audio Start")

    print(
        "Input:",
        input_device
    )

    print(
        "Output:",
        output_device
    )

    print(
        "Sample Rate:",
        samplerate
    )

    print(
        "Buffer:",
        blocksize
    )

    print("====================")



    stream = sd.Stream(

        device=(
            input_device,
            output_device
        ),

        samplerate=samplerate,

        channels=2,

        blocksize=blocksize,

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





app = QApplication(
    sys.argv
)



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