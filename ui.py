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
            900,
            700
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



        # ======================
        # デバイス選択
        # ======================

        device_frame = QFrame()

        device_layout = QHBoxLayout()

        device_frame.setLayout(
            device_layout
        )



        self.input_box = QComboBox()

        self.output_box = QComboBox()



        self.input_devices = []

        self.output_devices = []



        self.load_devices()



        device_layout.addWidget(
            QLabel("Input")
        )

        device_layout.addWidget(
            self.input_box
        )


        device_layout.addWidget(
            QLabel("Output")
        )

        device_layout.addWidget(
            self.output_box
        )



        self.start_button = QPushButton(
            "Start"
        )


        self.stop_button = QPushButton(
            "Stop"
        )


        device_layout.addWidget(
            self.start_button
        )

        device_layout.addWidget(
            self.stop_button
        )



        self.start_button.clicked.connect(
            self.start_audio
        )


        self.stop_button.clicked.connect(
            self.stop_audio
        )



        layout.addWidget(
            device_frame
        )



        # ======================
        # メーター
        # ======================


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



        # ======================
        # Spectrum
        # ======================

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
                    name
                )



            if device["max_output_channels"] > 0:

                self.output_devices.append(
                    index
                )

                self.output_box.addItem(
                    name
                )



    def start_audio(self):

        input_device = self.input_devices[
            self.input_box.currentIndex()
        ]


        output_device = self.output_devices[
            self.output_box.currentIndex()
        ]


        self.start_stream(
            input_device,
            output_device
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