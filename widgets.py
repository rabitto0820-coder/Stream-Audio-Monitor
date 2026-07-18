import tkinter as tk


class LevelMeter(tk.Canvas):
    def __init__(self, parent, width=300, height=30):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg="black",
            highlightthickness=0
        )

        self.width = width
        self.height = height
        self.level = 0

        self.draw_meter()


    def set_level(self, value):
        self.level = max(0, min(1, value))
        self.draw_meter()


    def draw_meter(self):
        self.delete("all")

        fill_width = int(self.width * self.level)

        self.create_rectangle(
            0,
            0,
            self.width,
            self.height,
            fill="gray20",
            outline=""
        )

        self.create_rectangle(
            0,
            0,
            fill_width,
            self.height,
            fill="lime",
            outline=""
        )