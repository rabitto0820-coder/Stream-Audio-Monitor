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

        painter.setBrush(
            QColor("#333333")
        )

        painter.drawRect(
            0,
            0,
            width,
            height
        )



        # dBを0〜1へ変換

        ratio = (
            self.level + 60
        ) / 60


        ratio = max(
            0,
            min(
                1,
                ratio
            )
        )



        # メーター

        painter.setBrush(
            QColor("#00ff66")
        )


        painter.drawRect(
            0,
            0,
            int(width * ratio),
            height
        )



        # 文字

        painter.setPen(
            Qt.GlobalColor.white
        )


        painter.drawText(
            10,
            30,
            f"{self.name}: {self.level:.1f} dB"
        )







class SpectrumWidget(QWidget):

    def __init__(self):

        super().__init__()


        self.spectrum = np.zeros(
            512,
            dtype=np.float32
        )


        self.setMinimumHeight(
            220
        )



    def set_spectrum(self, spectrum):

        self.spectrum = spectrum.copy()

        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)


        width = self.width()
        height = self.height()



        # 背景

        painter.setBrush(
            QColor("#111111")
        )

        painter.drawRect(
            0,
            0,
            width,
            height
        )



        if len(self.spectrum) == 0:
            return



        # タイトル

        painter.setPen(
            Qt.GlobalColor.white
        )

        painter.drawText(
            10,
            20,
            "Spectrum Analyzer"
        )



        # 棒グラフ設定

        bars = 64

        step = len(self.spectrum) // bars


        bar_width = max(
            2,
            width // bars - 2
        )



        for i in range(bars):

            start = i * step
            end = start + step


            value = np.max(
                self.spectrum[start:end]
            )


            bar_height = int(
                value * (height - 40)
            )


            x = i * (
                width / bars
            )


            y = height - bar_height



            painter.setBrush(
                QColor("#00ff66")
            )


            painter.drawRect(
                int(x),
                y,
                bar_width,
                bar_height
            )



        # 周波数目盛り

        painter.setPen(
            QColor("#aaaaaa")
        )


        painter.drawText(
            10,
            height - 10,
            "20Hz"
        )


        painter.drawText(
            width // 2 - 30,
            height - 10,
            "1kHz"
        )


        painter.drawText(
            width - 60,
            height - 10,
            "20kHz"
        )