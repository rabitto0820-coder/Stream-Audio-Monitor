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



        painter.setBrush(
            QColor("#333333")
        )

        painter.drawRect(
            0,
            0,
            width,
            height
        )



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



        painter.setBrush(
            QColor("#00ff66")
        )


        painter.drawRect(
            0,
            0,
            int(width * ratio),
            height
        )



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


        # 表示用スムージングデータ

        self.display = np.zeros(
            512,
            dtype=np.float32
        )


        # ピーク保持

        self.peak = np.zeros(
            512,
            dtype=np.float32
        )


        self.setMinimumHeight(
            220
        )



    def set_spectrum(self, spectrum):

        if len(spectrum) != len(self.spectrum):
            return


        self.spectrum = spectrum.copy()


        # 上昇は速く
        # 下降はゆっくり

        self.display = (
            self.display * 0.75
            +
            self.spectrum * 0.25
        )


        # ピーク更新

        self.peak = np.maximum(
            self.peak * 0.96,
            self.display
        )


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



        painter.setPen(
            Qt.GlobalColor.white
        )

        painter.drawText(
            10,
            20,
            "Spectrum Analyzer"
        )



        bars = 64

        step = len(self.display) // bars


        bar_width = max(
            2,
            width // bars - 2
        )



        for i in range(bars):

            start = i * step

            end = start + step


            value = np.max(
                self.display[start:end]
            )


            peak_value = np.max(
                self.peak[start:end]
            )



            bar_height = int(
                value * (height - 50)
            )


            peak_height = int(
                peak_value * (height - 50)
            )



            x = int(
                i * width / bars
            )


            y = height - bar_height



            # 棒

            painter.setBrush(
                QColor("#00ff66")
            )


            painter.drawRect(
                x,
                y,
                bar_width,
                bar_height
            )



            # ピーク線

            painter.setBrush(
                QColor("#ffffff")
            )


            painter.drawRect(
                x,
                height - peak_height - 2,
                bar_width,
                2
            )



        # 周波数表示

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