from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt


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