"""Small code-native outline icons, rendered sharply for either app theme."""

import math

import customtkinter as ctk
from PIL import Image, ImageDraw


class InterfaceIcons:
    def __init__(self):
        self.cache = {}

    def get(self, name, size=25):
        key = name, size
        if key not in self.cache:
            images = [self._draw(name, size, color) for color in ("#23669f", "#a1cbf6")]
            self.cache[key] = ctk.CTkImage(images[0], images[1], size=(size, size))
        return self.cache[key]

    @staticmethod
    def _draw(name, size, color):
        factor = 4
        image = Image.new("RGBA", (size * factor, size * factor), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        scale = size * factor / 32
        width = max(1, round(1.65 * scale))

        def points(values):
            return [(round(x * scale), round(y * scale)) for x, y in values]

        def line(values):
            draw.line(points(values), fill=color, width=width, joint="curve")

        def rect(box, radius=0):
            coordinates = tuple(round(v * scale) for v in box)
            draw.rounded_rectangle(coordinates, radius=round(radius * scale), outline=color, width=width)

        if name == "firmwares":
            rect((8, 8, 24, 24), 1.5)
            rect((11, 11, 21, 21))
            for position in (10, 14, 18, 22):
                line(((position, 3), (position, 8)))
                line(((position, 24), (position, 29)))
                line(((3, position), (8, position)))
                line(((24, position), (29, position)))
        elif name == "manuals":
            line(((16, 7), (12, 5), (3, 5), (3, 26), (12, 26), (16, 28), (20, 26), (29, 26), (29, 5), (20, 5), (16, 7), (16, 28)))
        elif name == "terminals":
            rect((3, 5, 29, 27), 2.5)
            line(((8, 11), (12, 15), (8, 19)))
            line(((16, 20), (23, 20)))
        elif name == "settings":
            outline = []
            for index in range(48):
                angle = math.tau * index / 48
                radius = 12.8 if index % 6 in (1, 2, 3) else 10
                outline.append((16 + radius * math.cos(angle), 16 + radius * math.sin(angle)))
            line(outline + [outline[0]])
            draw.ellipse(tuple(round(v * scale) for v in (11, 11, 21, 21)), outline=color, width=width)
        elif name == "back":
            line(((19, 6), (9, 16), (19, 26)))
            line(((9, 16), (28, 16)))
        elif name == "enter":
            line(((5, 16), (26, 16)))
            line(((17, 7), (26, 16), (17, 25)))
        return image.resize((size, size), Image.Resampling.LANCZOS)
