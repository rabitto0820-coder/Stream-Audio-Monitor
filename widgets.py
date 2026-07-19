import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class AudioMeter(QWidget):
    def __init__(self, name):
        super().__init__()

        self.name = name
        self.level = -60.0
        self.hold_level = -60.0

        self.setMinimumHeight(50)

    def set_level(self, value):
        self.level = max(-60.0, min(0.0, float(value)))

        if self.level > self.hold_level:
            self.hold_level = self.level
        else:
            self.hold_level -= 0.3

        if self.hold_level < self.level:
            self.hold_level = self.level

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        width = self.width()
        height = self.height()

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#202124")
        )

        ratio = (self.level + 60.0) / 60.0
        ratio = max(0.0, min(1.0, ratio))

        if self.level > -3:
            color = QColor("#ff3333")
        elif self.level > -12:
            color = QColor("#ffd633")
        else:
            color = QColor("#00ff66")

        painter.fillRect(
            0,
            0,
            int(width * ratio),
            height,
            color
        )

        hold_ratio = (self.hold_level + 60.0) / 60.0
        hold_ratio = max(0.0, min(1.0, hold_ratio))

        painter.fillRect(
            int(width * hold_ratio) - 1,
            0,
            2,
            height,
            Qt.GlobalColor.white
        )

        painter.setPen(Qt.GlobalColor.white)

        painter.drawText(
            10,
            30,
            f"{self.name}: {self.level:.1f} dB"
        )


class CorrelationWidget(QWidget):
    """Stereo correlation meter: -1.00 is opposite phase, +1.00 is in phase."""

    def __init__(self):
        super().__init__()

        self.value = 0.0

        self.setMinimumHeight(70)

    def set_correlation(self, value):
        self.value = max(
            -1.0,
            min(
                1.0,
                float(value)
            )
        )

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        width = self.width()
        height = self.height()

        center = width // 2

        value_x = int(
            center
            +
            self.value
            *
            (width / 2 - 12)
        )

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#202124")
        )

        painter.fillRect(
            0,
            height // 2 - 4,
            center,
            8,
            QColor("#a83232")
        )

        painter.fillRect(
            center,
            height // 2 - 4,
            width - center,
            8,
            QColor("#237a42")
        )

        painter.setPen(Qt.GlobalColor.white)

        painter.drawLine(
            center,
            12,
            center,
            height - 12
        )

        painter.drawLine(
            value_x,
            8,
            value_x,
            height - 8
        )

        painter.drawText(
            10,
            20,
            "Stereo Correlation"
        )

        painter.drawText(
            10,
            height - 8,
            "-1"
        )

        painter.drawText(
            center - 5,
            height - 8,
            "0"
        )

        painter.drawText(
            width - 22,
            height - 8,
            "+1"
        )

        painter.drawText(
            width - 115,
            20,
            f"{self.value:+.2f}"
        )


class SpectrumWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.spectrum = np.zeros(
            512,
            dtype=np.float32
        )

        self.display = np.zeros(
            512,
            dtype=np.float32
        )

        self.peak = np.zeros(
            512,
            dtype=np.float32
        )

        self.setMinimumHeight(250)

    def set_spectrum(self, spectrum):
        if len(spectrum) != 512:
            return

        self.spectrum = spectrum.copy()

        self.display = (
            self.display * 0.8
            +
            self.spectrum * 0.2
        )

        self.peak = np.maximum(
            self.peak * 0.97,
            self.display
        )

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        width = self.width()
        height = self.height()

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#181818")
        )

        painter.setPen(QColor("#303030"))

        for db in [-60, -40, -20, -10, -3]:
            y = int(
                height
                -
                35
                -
                ((db + 60) / 60)
                *
                (height - 60)
            )

            painter.drawLine(
                0,
                y,
                width,
                y
            )

            painter.setPen(QColor("#aaaaaa"))

            painter.drawText(
                5,
                y - 3,
                f"{db} dB"
            )

            painter.setPen(QColor("#303030"))

        painter.setPen(Qt.GlobalColor.white)

        painter.drawText(
            10,
            20,
            "Spectrum Analyzer"
        )

        bars = 64

        for index in range(bars):
            spectrum_index = int(
                (index / bars)
                *
                len(self.display)
            )

            value = self.display[spectrum_index]

            if value > 0:
                db = 20 * np.log10(value)
            else:
                db = -60

            db = max(-60, min(0, db))

            ratio = (db + 60) / 60

            bar_height = int(
                ratio
                *
                (height - 60)
            )

            x = int(
                index
                *
                width
                /
                bars
            )

            bar_width = max(
                3,
                width // bars - 3
            )

            y = height - bar_height - 30

            if db > -6:
                color = QColor("#ff3333")
            elif db > -20:
                color = QColor("#ffd633")
            else:
                color = QColor("#00ff66")

            painter.fillRect(
                x,
                y,
                bar_width,
                bar_height,
                color
            )

        painter.setPen(QColor("#aaaaaa"))

        painter.drawText(
            10,
            height - 10,
            "20Hz"
        )

        painter.drawText(
            width // 2 - 20,
            height - 10,
            "1kHz"
        )

        painter.drawText(
            width - 60,
            height - 10,
            "20kHz"
        )