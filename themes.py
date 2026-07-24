"""Visual skins for Stream Audio Monitor."""


THEMES = {
    "Stream Neon": {
        "window": "#030817",
        "panel": "#07122a",
        "control": "#0a1630",
        "hover": "#132953",
        "text": "#eef4ff",
        "border": "#284c85",
    },
    "Studio Dark": {
        "window": "#181818",
        "panel": "#242424",
        "control": "#303030",
        "hover": "#444444",
        "text": "#f1f1f1",
        "border": "#555555",
    },
    "Midnight Blue": {
        "window": "#101926",
        "panel": "#18263a",
        "control": "#243852",
        "hover": "#33506f",
        "text": "#e7f1ff",
        "border": "#52718f",
    },
    "Amber Console": {
        "window": "#191611",
        "panel": "#282116",
        "control": "#3a2f1c",
        "hover": "#524225",
        "text": "#ffe7a3",
        "border": "#806637",
    },
}


def theme_names():
    return list(THEMES)


def apply_theme(widget, name):
    theme = THEMES.get(
        name,
        THEMES["Studio Dark"]
    )

    widget.setStyleSheet(
        f"""
        QMainWindow {{
            background: {theme["window"]};
        }}

        QWidget#appShell {{
            background: qradialgradient(cx: 0.5, cy: 0.15, radius: 1.15,
                fx: 0.5, fy: 0.15, stop: 0 #0b1736, stop: 0.48 #050b1b,
                stop: 1 #020611);
        }}

        QFrame#appHeader {{
            background: rgba(4, 11, 31, 220);
            border: 1px solid #152d59;
            border-radius: 14px;
        }}

        QLabel#brandBadge {{
            color: #1ee4ff;
            font-size: 24pt;
            font-weight: 800;
            padding: 8px 12px;
            border: 1px solid #31d9ff;
            border-radius: 12px;
            background: #071430;
        }}

        QLabel#productTitle {{
            font-size: 23pt;
            font-weight: 700;
            color: #f5f7ff;
        }}

        QLabel#productSubtitle, QLabel#readyLabel {{
            color: #b7c8ef;
            font-size: 10pt;
        }}

        QFrame#neonCard {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #091837, stop: 1 #050b1d);
            border: 1px solid #1c4b87;
            border-radius: 16px;
        }}

        QFrame#cyanCard {{ border-color: #19d6ee; }}
        QFrame#purpleCard {{ border-color: #a555ff; }}
        QFrame#pinkCard {{ border-color: #ff4b8b; }}

        QLabel#cardTitle {{
            color: #29dbff;
            font-size: 15pt;
            font-weight: 700;
        }}

        QLabel#purpleTitle, QLabel#pinkTitle {{
            font-size: 15pt;
            font-weight: 700;
        }}
        QLabel#purpleTitle {{ color: #bd6aff; }}
        QLabel#pinkTitle {{ color: #ff5792; }}
        QLabel#cardDescription {{ color: #d9e4ff; font-size: 10.5pt; }}

        QLabel {{
            color: {theme["text"]};
            font-size: 12pt;
        }}

        QComboBox, QPushButton {{
            background: {theme["control"]};
            color: {theme["text"]};
            border: 1px solid {theme["border"]};
            border-radius: 8px;
            padding: 8px;
        }}

        QPushButton:hover {{
            background: {theme["hover"]};
        }}

        QPushButton#engageButton {{
            background: qradialgradient(cx: 0.5, cy: 0.42, radius: 0.68,
                fx: 0.5, fy: 0.42, stop: 0 #162b62, stop: 0.58 #111234,
                stop: 1 #060b20);
            color: #fbfbff;
            border: 3px solid #5d68ff;
            border-radius: 150px;
            font-size: 25pt;
            font-weight: 800;
            letter-spacing: 1px;
        }}

        QPushButton#engageButton:hover {{
            border-color: #ef66ff;
            background: #192558;
        }}

        QPushButton#accentButton {{
            color: #ff86b4;
            border-color: #ff4b8b;
            font-weight: 700;
        }}

        QCheckBox#accentButton {{
            color: #d8e5ff;
            background: #0b1730;
            border: 1px solid #38538a;
            border-radius: 8px;
            padding: 9px 12px;
            font-weight: 700;
        }}

        QCheckBox#accentButton:hover {{
            border-color: #a05cff;
            background: #101f42;
        }}

        QCheckBox#accentButton:checked {{
            color: #ffffff;
            background: #30215c;
            border: 1px solid #d460ff;
        }}

        QCheckBox#accentButton::indicator {{
            width: 14px;
            height: 14px;
        }}

        QCheckBox#accentButton::indicator:checked {{
            background: #45e5ff;
            border: 1px solid #d9fbff;
            border-radius: 7px;
        }}

        QPushButton#secondaryButton {{
            color: #b9c9f5;
            border-color: #354d82;
        }}

        QFrame#engageCard {{
            background: transparent;
            border: none;
        }}

        QCheckBox {{
            color: {theme["text"]};
        }}

        QFrame {{
            background: {theme["panel"]};
            border-radius: 8px;
        }}
        """
    )
