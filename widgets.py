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
        self.hold_level = max(
            self.level,
            self.hold_level - 0.3
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()

        painter.fillRect(0, 0, width, height, QColor("#202124"))

        ratio = max(0.0, min(1.0, (self.level + 60.0) / 60.0))

        color = QColor("#00ff66")
        if self.level > -3:
            color = QColor("#ff3333")
        elif self.level > -12:
            color = QColor("#ffd633")

        painter.fillRect(
            0,
            0,
            int(width * ratio),
            height,
            color
        )

        hold_ratio = max(
            0.0,
            min(1.0, (self.hold_level + 60.0) / 60.0)
        )

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
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setMinimumHeight(70)

    def set_correlation(self, value):
        self.value = max(-1.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()

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
            width - 115,
            20,
            f"{self.value:+.2f}"
        )


class PhaseScopeWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = np.zeros((0, 2), dtype=np.float32)
        self.setMinimumHeight(220)

    def set_samples(self, samples):
        data = np.asarray(samples, dtype=np.float32)

        if data.ndim == 2 and data.shape[1] >= 2:
            self.samples = data[::8, :2].copy()
        else:
            self.samples = np.zeros((0, 2), dtype=np.float32)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()

        center_x = width / 2.0
        center_y = height / 2.0
        radius = min(width, height) * 0.42

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#181818")
        )

        painter.setPen(QColor("#303030"))

        painter.drawLine(
            0,
            int(center_y),
            width,
            int(center_y)
        )

        painter.drawLine(
            int(center_x),
            0,
            int(center_x),
            height
        )

        painter.drawEllipse(
            int(center_x - radius),
            int(center_y - radius),
            int(radius * 2),
            int(radius * 2)
        )

        painter.setPen(QColor("#aaaaaa"))

        painter.drawText(
            10,
            20,
            "Phase Scope (L / R)"
        )

        painter.setPen(QColor("#00ff88"))

        for left, right in self.samples:
            x = int(
                center_x
                +
                np.clip(left, -1.0, 1.0)
                *
                radius
            )

            y = int(
                center_y
                -
                np.clip(right, -1.0, 1.0)
                *
                radius
            )

            painter.drawPoint(x, y)


class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = np.zeros((0, 2), dtype=np.float32)
        self.setMinimumHeight(180)

    def set_samples(self, samples):
        data = np.asarray(samples, dtype=np.float32)

        if data.ndim == 2 and data.shape[1] >= 2:
            self.samples = data[:, :2].copy()
        else:
            self.samples = np.zeros((0, 2), dtype=np.float32)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()

        half_height = height // 2

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#181818")
        )

        painter.setPen(QColor("#303030"))

        painter.drawLine(
            0,
            half_height // 2,
            width,
            half_height // 2
        )

        painter.drawLine(
            0,
            half_height + half_height // 2,
            width,
            half_height + half_height // 2
        )

        painter.setPen(QColor("#aaaaaa"))

        painter.drawText(
            10,
            20,
            "Waveform  L / R"
        )

        if len(self.samples) < 2:
            return

        for channel, offset, color in (
            (0, 0, QColor("#00d8ff")),
            (1, half_height, QColor("#00ff88")),
        ):
            painter.setPen(color)

            previous = None

            for index, value in enumerate(
                self.samples[:, channel]
            ):
                x = int(
                    index
                    *
                    (width - 1)
                    /
                    (len(self.samples) - 1)
                )

                y = int(
                    offset
                    +
                    half_height / 2
                    -
                    np.clip(value, -1.0, 1.0)
                    *
                    (half_height * 0.42)
                )

                if previous is not None:
                    painter.drawLine(
                        previous[0],
                        previous[1],
                        x,
                        y
                    )

                previous = (x, y)


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

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()

        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor("#181818")
        )

        painter.setPen(Qt.GlobalColor.white)

        painter.drawText(
            10,
            20,
            "Spectrum Analyzer"
        )

        bars = 64

        for index in range(bars):
            spectrum_index = int(
                index
                *
                len(self.display)
                /
                bars
            )

            value = self.display[spectrum_index]

            db = (
                20 * np.log10(value)
                if value > 0
                else -60
            )

            db = max(-60, min(0, db))

            ratio = (db + 60) / 60

            bar_height = int(
                ratio
                *
                (height - 40)
            )

            x = int(index * width / bars)
            bar_width = max(3, width // bars - 3)

            color = QColor("#00ff66")

            if db > -6:
                color = QColor("#ff3333")
            elif db > -20:
                color = QColor("#ffd633")

            painter.fillRect(
                x,
                height - bar_height - 10,
                bar_width,
                bar_height,
                color
            )


class CodecDifferenceWidget(QWidget):
    """Shows only the frequency ranges changed by the active codec preview."""

    def __init__(self):
        super().__init__()
        self.difference = np.zeros(512, dtype=np.float32)
        self.average = np.zeros(512, dtype=np.float32)
        self.display = np.zeros(512, dtype=np.float32)
        self.peak_hold = np.zeros(512, dtype=np.float32)
        self.active = False
        self.sample_rate = 48000
        self.setMinimumHeight(250)

    def set_difference(self, difference, active, sample_rate=48000):
        if len(difference) != 512:
            return

        self.active = bool(active)
        self.sample_rate = int(sample_rate)
        if not self.active:
            self.difference.fill(0.0)
            self.average.fill(0.0)
            self.display.fill(0.0)
            self.peak_hold.fill(0.0)
        else:
            self.difference = difference.copy()
            # About 0.7 seconds of averaging at the 60 fps GUI update rate.
            self.average = self.average * 0.97 + self.difference * 0.03
            # Fall slowly so that brief, meaningful changes remain visible.
            self.display = np.maximum(
                self.average,
                self.display - 0.009,
            )
            self.peak_hold = np.maximum(self.peak_hold, self.display)
            self.peak_hold = np.maximum(0.0, self.peak_hold - 0.0025)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        width, height = self.width(), self.height()
        painter.fillRect(0, 0, width, height, QColor("#181818"))

        painter.setPen(QColor("#f0d060"))
        title = "Codec Difference Spectrum"
        if self.active and float(np.max(self.display)) >= 0.03:
            index = int(np.argmax(self.display))
            frequency_hz = index * self.sample_rate / 1024.0
            if frequency_hz >= 1000.0:
                frequency_text = f"{frequency_hz / 1000.0:.1f} kHz"
            else:
                frequency_text = f"{frequency_hz:.0f} Hz"
            title += f"  |  strongest: {frequency_text}"
        painter.drawText(10, 20, title)
        painter.setPen(QColor("#a0a0a0"))
        note = "Opus/AAC OFF - no codec change to display" if not self.active else "Smoothed codec change by frequency"
        painter.drawText(10, 40, note)

        usable_height = height - 55
        # Match Spectrum Analyzer's 64-bar layout. Each bar samples the
        # difference at the same relative frequency position.
        bars = 64
        for bar in range(bars):
            index = min(
                len(self.display) - 1,
                int(bar * len(self.display) / bars),
            )
            value = float(np.clip(self.display[index], 0.0, 1.0))
            bar_height = int(value * usable_height)
            x = int(bar * width / bars)
            bar_width = max(3, width // bars - 3)

            color = QColor("#00c85a")
            if value > 0.66:
                color = QColor("#ff4d4d")
            elif value > 0.33:
                color = QColor("#ffd633")

            painter.fillRect(
                x,
                height - bar_height - 10,
                bar_width,
                bar_height,
                color
            )

            hold_y = height - int(
                np.clip(self.peak_hold[index], 0.0, 1.0) * usable_height
            ) - 10
            painter.fillRect(
                x,
                hold_y,
                bar_width,
                2,
                QColor("#f4f4f4"),
            )
