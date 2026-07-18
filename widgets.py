from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

import numpy as np



class AudioMeter(QWidget):

    def __init__(self, name):
        super().__init__()

        self.name = name
        self.level = -60
        # Peak Hold
        self.hold_level = -60
        self.setMinimumHeight(50)



    def set_level(self, value):

        self.level = value
        # Peak Hold更新
        if value > self.hold_level:
            self.hold_level = value
        else:
            self.hold_level -= 0.3

        if self.hold_level < value:
            self.hold_level = value
        self.update()



    def paintEvent(self, event):

        painter = QPainter(self)

        width = self.width()
        height = self.height()



        # 背景

        painter.setBrush(
            QColor("#202124")
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



        # レベル色

        if self.level > -3:
            color = QColor("#ff3333")

        elif self.level > -12:
            color = QColor("#ffd633")

        else:
            color = QColor("#00ff66")



        painter.setBrush(color)


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


        self.display = np.zeros(
            512,
            dtype=np.float32
        )


        self.peak = np.zeros(
            512,
            dtype=np.float32
        )


        self.setMinimumHeight(
            250
        )



    def set_spectrum(self, spectrum):

        if len(spectrum) != len(self.spectrum):
            return


        self.spectrum = spectrum.copy()


        # スムージング

        self.display = (
            self.display * 0.75
            +
            self.spectrum * 0.25
        )



        # ピーク保持

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
            QColor("#181818")
        )

        painter.drawRect(
            0,
            0,
            width,
            height
        )



        # グリッド

        painter.setPen(
            QColor("#303030")
        )


        for y in range(
            40,
            height - 30,
            40
        ):

            painter.drawLine(
                0,
                y,
                width,
                y
            )



        for x in range(
            0,
            width,
            width // 8
        ):

            painter.drawLine(
                x,
                25,
                x,
                height - 30
            )



        # タイトル

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
            3,
            width // bars - 3
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
                value * (height - 60)
            )


            peak_height = int(
                peak_value * (height - 60)
            )



            x = int(
                i * width / bars
            )


            y = height - bar_height - 25



            # 高さによる色変化

            if value > 0.75:

                color = QColor("#ff3333")

            elif value > 0.45:

                color = QColor("#ffd633")

            else:

                color = QColor("#00ff66")



            painter.setBrush(
                color
            )


            painter.drawRect(
                x,
                y,
                bar_width,
                bar_height
            )



            # ピーク表示

            painter.setBrush(
                QColor("#ffffff")
            )


            painter.drawRect(
                x,
                height - peak_height - 27,
                bar_width,
                2
            )



        # 周波数表示

        painter.setPen(
            QColor("#aaaaaa")
        )


        painter.drawText(
            10,
            height - 8,
            "20Hz"
        )


        painter.drawText(
            width // 2 - 25,
            height - 8,
            "1kHz"
        )


        painter.drawText(
            width - 60,
            height - 8,
            "20kHz"
        )