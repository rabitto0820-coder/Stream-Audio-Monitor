from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QComboBox,
    QPushButton,
    QHBoxLayout
)

from PyQt6.QtCore import Qt, QTimer

import sounddevice as sd

from widgets import AudioMeter, SpectrumWidget
from audio_state import audio_state

from settings import (
    save_settings,
    load_settings
)



class MainWindow(QMainWindow):

    def __init__(
        self,
        start_stream,
        stop_stream
    ):

        super().__init__()


        self.start_stream = start_stream
        self.stop_stream = stop_stream


        self.setWindowTitle(
            "Stream Audio Monitor"
        )


        self.resize(
            1000,
            750
        )



        self.setStyleSheet(
            """
            QMainWindow{
                background:#202124;
            }

            QLabel{
                color:white;
                font-size:12pt;
            }

            QComboBox{
                background:#333333;
                color:white;
                padding:5px;
            }

            QPushButton{
                background:#333333;
                color:white;
                padding:8px;
            }

            QFrame{
                background:#2b2b2b;
                border-radius:8px;
            }
            """
        )



        central = QWidget()

        self.setCentralWidget(
            central
        )


        layout = QVBoxLayout()

        layout.setSpacing(
            15
        )

        central.setLayout(
            layout
        )



        title = QLabel(
            "🎧 Stream Audio Monitor"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )


        title.setStyleSheet(
            """
            font-size:22pt;
            font-weight:bold;
            """
        )


        layout.addWidget(
            title
        )



        # ==========================
        # 設定パネル
        # ==========================

        setting_frame = QFrame()

        setting_layout = QHBoxLayout()

        setting_frame.setLayout(
            setting_layout
        )



        self.input_box = QComboBox()

        self.output_box = QComboBox()


        self.rate_box = QComboBox()

        self.buffer_box = QComboBox()



        self.input_devices = []

        self.output_devices = []



        self.rate_values = [
            44100,
            48000,
            96000
        ]


        for value in self.rate_values:

            self.rate_box.addItem(
                f"{value} Hz"
            )



        self.buffer_values = [
            256,
            512,
            1024,
            2048,
            4096
        ]


        for value in self.buffer_values:

            self.buffer_box.addItem(
                str(value)
            )



        self.load_devices()



        setting_layout.addWidget(
            QLabel("Input")
        )

        setting_layout.addWidget(
            self.input_box
        )



        setting_layout.addWidget(
            QLabel("Output")
        )

        setting_layout.addWidget(
            self.output_box
        )



        setting_layout.addWidget(
            QLabel("Rate")
        )

        setting_layout.addWidget(
            self.rate_box
        )



        setting_layout.addWidget(
            QLabel("Buffer")
        )

        setting_layout.addWidget(
            self.buffer_box
        )



        self.start_button = QPushButton(
            "Start"
        )


        self.stop_button = QPushButton(
            "Stop"
        )



        setting_layout.addWidget(
            self.start_button
        )

        setting_layout.addWidget(
            self.stop_button
        )



        self.start_button.clicked.connect(
            self.start_audio
        )


        self.stop_button.clicked.connect(
            self.stop_audio
        )



        layout.addWidget(
            setting_frame
        )



        # ==========================
        # Meter
        # ==========================


        self.peak_meter = AudioMeter(
            "Peak"
        )

        layout.addWidget(
            self.peak_meter
        )


        self.rms_meter = AudioMeter(
            "RMS"
        )

        layout.addWidget(
            self.rms_meter
        )



        self.spectrum = SpectrumWidget()

        layout.addWidget(
            self.spectrum
        )



        self.status = QLabel(
            "Status : Ready"
        )

        layout.addWidget(
            self.status
        )



        self.timer = QTimer()

        self.timer.timeout.connect(
            self.update_gui
        )


        self.timer.start(
            16
        )



    def load_devices(self):

        devices = sd.query_devices()



        for index, device in enumerate(devices):

            name = device["name"]



            if device["max_input_channels"] > 0:

                self.input_devices.append(
                    index
                )


                self.input_box.addItem(
                    f"{index} : {name}"
                )



            if device["max_output_channels"] > 0:

                self.output_devices.append(
                    index
                )


                self.output_box.addItem(
                    f"{index} : {name}"
                )



        saved = load_settings()


        if saved:


            if saved["input_device"] in self.input_devices:

                self.input_box.setCurrentIndex(
                    self.input_devices.index(
                        saved["input_device"]
                    )
                )



            if saved["output_device"] in self.output_devices:

                self.output_box.setCurrentIndex(
                    self.output_devices.index(
                        saved["output_device"]
                    )
                )



            if "samplerate" in saved:

                if saved["samplerate"] in self.rate_values:

                    self.rate_box.setCurrentIndex(
                        self.rate_values.index(
                            saved["samplerate"]
                        )
                    )



            if "blocksize" in saved:

                if saved["blocksize"] in self.buffer_values:

                    self.buffer_box.setCurrentIndex(
                        self.buffer_values.index(
                            saved["blocksize"]
                        )
                    )



    def start_audio(self):

        input_device = self.input_devices[
            self.input_box.currentIndex()
        ]


        output_device = self.output_devices[
            self.output_box.currentIndex()
        ]


        samplerate = self.rate_values[
            self.rate_box.currentIndex()
        ]


        blocksize = self.buffer_values[
            self.buffer_box.currentIndex()
        ]



        print("Input:", input_device)

        print("Output:", output_device)

        print("Rate:", samplerate)

        print("Buffer:", blocksize)



        save_settings(
            input_device,
            output_device,
            samplerate,
            blocksize
        )



        self.start_stream(
            input_device,
            output_device,
            samplerate,
            blocksize
        )


        self.status.setText(
            "Status : Running"
        )



    def stop_audio(self):

        self.stop_stream()


        self.status.setText(
            "Status : Stopped"
        )



    def update_gui(self):

        self.peak_meter.set_level(
            audio_state.peak_db
        )


        self.rms_meter.set_level(
            audio_state.rms_db
        )


        self.spectrum.set_spectrum(
            audio_state.spectrum
        )