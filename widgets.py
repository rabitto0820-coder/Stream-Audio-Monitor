from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

import numpy as np



class AudioMeter(QWidget):

    def __init__(self, name):
        super().__init__()

        self.name = name
        self.level = -60

        self.setMinimumHeight(50)


    def set_level(self, value):

        self.level = value
        self.update()


    def paintEvent(self, event):

        painter = QPainter(self)

        width = self.width()
        height = self.height()


        # 背景
        painter.setBrush(QColor("#333333"))

        painter.drawRect(
            0,
            0,
            width,
            height
        )


        # -60dB～0dBを0～1へ変換
        ratio = (self.level + 60) / 60

        ratio = max(0, min(1, ratio))


        # メーター
        painter.setBrush(QColor("#00ff66"))

        painter.drawRect(
            0,
            0,
            int(width * ratio),
            height
        )


        # 文字
        painter.setPen(Qt.GlobalColor.white)

        painter.drawText(
            10,
            30,
            f"{self.name}: {self.level:.1f} dB"
        )





class SpectrumWidget(QWidget):

    def __init__(self):
        super().__init__()

        self.spectrum = np.zeros(512)

        self.setMinimumHeight(200)



    def set_spectrum(self, spectrum):

        self.spectrum = spectrum.copy()

        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)

        width = self.width()
        height = self.height()


        # 背景
        painter.setBrush(QColor("#111111"))

        painter.drawRect(
            0,
            0,
            width,
            height
        )


        if len(self.spectrum) == 0:
            return


        painter.setPen(
            QColor("#00ff66")
        )


        points = len(self.spectrum)


        for i in range(points - 1):

            x1 = int(
                i * width / points
            )

            x2 = int(
                (i + 1) * width / points
            )


            y1 = int(
                height -
                self.spectrum[i] * height
            )

            y2 = int(
                height -
                self.spectrum[i + 1] * height
            )


            painter.drawLine(
                x1,
                y1,
                x2,
                y2
            )


        painter.setPen(
            Qt.GlobalColor.white
        )

        painter.drawText(
            10,
            20,
            "Spectrum Analyzer"
        )