from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt


class AudioMeter(QWidget):
    """
    Peak/RMS共通メーター
    """

    def __init__(self, title="Meter"):
        super().__init__()

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(22)

        self.db_label = QLabel("-60.0 dBFS")
        self.db_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(self.title)
        layout.addWidget(self.bar)
        layout.addWidget(self.db_label)

        self.setLayout(layout)

        self.set_level(-60.0)

    def set_level(self, db):

        db = max(-60.0, min(0.0, db))

        value = int((db + 60.0) / 60.0 * 100)

        self.bar.setValue(value)

        self.db_label.setText(f"{db:.1f} dBFS")

        if db < -18:
            color = "#2ecc71"      # 緑
        elif db < -6:
            color = "#f1c40f"      # 黄
        else:
            color = "#e74c3c"      # 赤

        self.bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #555;
                border-radius: 5px;
                background-color: #222;
            }}

            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)