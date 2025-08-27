COLORS = {
    "light_light_gray": (236, 235, 234),
    "gray": (62, 68, 76),
    "light_gray": (159, 153, 152),
    "light_blue": (0, 190, 255),
    "dark_blue": (0, 81, 158),
    "light_light_blue": (204, 242, 255),
    "white": (255, 255, 255)
}

def rgb(name, alpha=1.0):
    r, g, b = COLORS[name]
    return f"rgba({r},{g},{b},{alpha})"
