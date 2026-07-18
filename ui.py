from PyQt6.QtCore import QTimer

from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

import audio


class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Stream Audio Monitor")

        self.resize(700, 400)

        central = QWidget()

        self.setCentralWidget(central)

        layout = QVBoxLayout()

        central.setLayout(layout)

        title = QLabel("Stream Audio Monitor")

        layout.addWidget(title)

        layout.addWidget(QLabel("Peak"))

        self.peak = QProgressBar()

        self.peak.setRange(0, 100)

        layout.addWidget(self.peak)

        layout.addWidget(QLabel("RMS"))

        self.rms = QProgressBar()

        self.rms.setRange(0, 100)

        layout.addWidget(self.rms)

        layout.addWidget(QLabel("Spectrum Analyzer (Coming Soon)"))

        self.timer = QTimer()

        self.timer.timeout.connect(self.update_gui)

        self.timer.start(16)

    def update_gui(self):

        peak = int(max(0, min(100, (audio.current_peak_db + 60) / 60 * 100)))

        rms = int(max(0, min(100, (audio.current_rms_db + 60) / 60 * 100)))

        self.peak.setValue(peak)

        self.rms.setValue(rms)