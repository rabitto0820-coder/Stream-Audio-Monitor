"""Visual skins for Stream Audio Monitor."""


THEMES = {
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

        QLabel {{
            color: {theme["text"]};
            font-size: 12pt;
        }}

        QComboBox, QPushButton {{
            background: {theme["control"]};
            color: {theme["text"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 6px;
        }}

        QPushButton:hover {{
            background: {theme["hover"]};
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