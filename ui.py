from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
)

from PyQt6.QtCore import Qt, QTimer

from widgets import AudioMeter
from audio_state import audio_state


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Stream Audio Monitor")
        self.resize(900, 600)

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

        self.setCentralWidget(central)

        layout = QVBoxLayout()

        layout.setSpacing(15)

        central.setLayout(layout)

        title = QLabel("🎧 Stream Audio Monitor")

        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title.setStyleSheet("""
            font-size:22pt;
            font-weight:bold;
        """)

        layout.addWidget(title)

        self.peak_meter = AudioMeter("Peak")

        layout.addWidget(self.peak_meter)

        self.rms_meter = AudioMeter("RMS")

        layout.addWidget(self.rms_meter)

        spectrum = QFrame()

        spectrum_layout = QVBoxLayout()

        spectrum.setLayout(spectrum_layout)

        spectrum_layout.addWidget(
            QLabel("Spectrum Analyzer (Next Version)")
        )

        layout.addWidget(spectrum)

        self.status = QLabel("Status : Running")

        layout.addWidget(self.status)

        self.timer = QTimer()

        self.timer.timeout.connect(self.update_gui)

        self.timer.start(16)

    def update_gui(self):

        self.peak_meter.set_level(audio_state.peak_db)

        self.rms_meter.set_level(audio_state.rms_db)