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

        # Peak Holdライン
        hold_ratio = max(
            0,
            min(
                1,
                (self.hold_level + 60) / 60
            )
        )

        painter.setBrush(
            Qt.GlobalColor.white
        )

        painter.drawRect(
            int(width * hold_ratio) - 1,
            0,
            2,
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

        if len(spectrum) != 512:
            return


        self.spectrum = spectrum.copy()


        # スムージング
        self.display = (
            self.display * 0.8
            +
            self.spectrum * 0.2
        )


        # ピーク保持
        self.peak = np.maximum(
            self.peak * 0.97,
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



        # dBグリッド

        painter.setPen(
            QColor("#303030")
        )


        db_lines = [
            -60,
            -40,
            -20,
            -10,
            -3
        ]


        for db in db_lines:

            y = int(
                height - 35 -
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



            painter.setPen(
                QColor("#aaaaaa")
            )


            painter.drawText(
                5,
                y - 3,
                f"{db} dB"
            )


            painter.setPen(
                QColor("#303030")
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


        for i in range(bars):

            index = int(
                (i / bars)
                *
                len(self.display)
            )


            value = self.display[index]


            peak = self.peak[index]



            # dB変換

            if value > 0:

                db = 20 * np.log10(value)

            else:

                db = -60



            db = max(
                -60,
                min(
                    0,
                    db
                )
            )



            ratio = (
                db + 60
            ) / 60



            bar_height = int(
                ratio *
                (height - 60)
            )



            x = int(
                i *
                width /
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



            painter.setBrush(
                color
            )


            painter.drawRect(
                x,
                y,
                bar_width,
                bar_height
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
            width // 2 - 20,
            height - 10,
            "1kHz"
        )


        painter.drawText(
            width - 60,
            height - 10,
            "20kHz"
        )        