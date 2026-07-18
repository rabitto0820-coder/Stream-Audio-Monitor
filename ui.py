from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
)

from PyQt6.QtCore import Qt, QTimer

from widgets import AudioMeter, SpectrumWidget
from audio_state import audio_state



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()


        self.setWindowTitle(
            "Stream Audio Monitor"
        )

        self.resize(
            900,
            600
        )


        self.setStyleSheet("""
            QMainWindow{
                background:#202124;
            }

            QLabel{
                color:white;
                font-size:12pt;
            }

            QFrame{
                background:#2b2b2b;
                border-radius:8px;
            }
        """)



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



        # タイトル

        title = QLabel(
            "🎧 Stream Audio Monitor"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet("""
            font-size:22pt;
            font-weight:bold;
        """)

        layout.addWidget(
            title
        )



        # Peak

        self.peak_meter = AudioMeter(
            "Peak"
        )

        layout.addWidget(
            self.peak_meter
        )



        # RMS

        self.rms_meter = AudioMeter(
            "RMS"
        )

        layout.addWidget(
            self.rms_meter
        )



        # Spectrumエリア

        spectrum = QFrame()

        spectrum_layout = QVBoxLayout()

        spectrum.setLayout(
            spectrum_layout
        )


        self.spectrum_widget = SpectrumWidget()

        spectrum_layout.addWidget(
            self.spectrum_widget
        )


        layout.addWidget(
            spectrum
        )



        # Status

        self.status = QLabel(
            "Status : Running"
        )

        layout.addWidget(
            self.status
        )



        # 更新タイマー

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.update_gui
        )

        self.timer.start(
            16
        )



    def update_gui(self):

        # Peak表示

        self.peak_meter.set_level(
            audio_state.peak_db
        )


        # RMS表示

        self.rms_meter.set_level(
            audio_state.rms_db
        )


        # FFT Spectrum表示

        self.spectrum_widget.set_spectrum(
            audio_state.spectrum
        )