"""
Theme configuration manager for VDR Visualizer.
Handles light, dark, and specialized color schemes.
"""
from PySide6.QtGui import QColor

class Theme:
    def __init__(self, name: str, bg_app: str, bg_plot: str, fg_text: str, fg_dim: str, grid: tuple, crosshair: str, curves: list):
        self.name = name
        self.bg_app = bg_app
        self.bg_plot = bg_plot
        self.fg_text = fg_text
        self.fg_dim = fg_dim
        self.grid = grid
        self.crosshair = crosshair
        self.curves = curves

# Define the built-in themes
THEMES = {
    "Dark": Theme(
        name="Dark",
        bg_app="#1a1a2e",
        bg_plot="#16213e",
        fg_text="#e0e0e0",
        fg_dim="#888888",
        grid=(60, 60, 90, 100),
        crosshair="#aaaaaa",
        curves=[
            '#00D4FF', '#FF6B6B', '#51CF66', '#FFD43B', '#CC5DE8',
            '#FF922B', '#20C997', '#F06595', '#74C0FC', '#A9E34B'
        ]
    ),
    "Light": Theme(
        name="Light",
        bg_app="#f5f5f5",
        bg_plot="#ffffff",
        fg_text="#333333",
        fg_dim="#aaaaaa",
        grid=(200, 200, 200, 255),
        crosshair="#666666",
        curves=[
            '#005A9C', '#C9302C', '#449D44', '#EC971F', '#7952B3',
            '#D9534F', '#5BC0DE', '#E83E8C', '#0275D8', '#5CB85C'
        ]
    ),
    "Submarine": Theme(
        name="Submarine",
        bg_app="#001100",
        bg_plot="#000000",
        fg_text="#00ff00",
        fg_dim="#004400",
        grid=(0, 255, 0, 40),
        crosshair="#00ff00",
        curves=[
            '#00ff00', '#33ff33', '#66ff66', '#99ff99', '#ccffcc',
            '#aaff00', '#55ff00', '#00ff55', '#00ffaa', '#ebffeb'
        ]
    ),
    "Data Spy": Theme(
        name="Data Spy",
        bg_app="#0a1a10",
        bg_plot="#05120a",
        fg_text="#ccecd4",
        fg_dim="#2d5238",
        grid=(50, 90, 60, 100),
        crosshair="#88cc99",
        curves=[
            '#00D4FF', '#FF6B6B', '#51CF66', '#FFD43B', '#CC5DE8',
            '#FF922B', '#20C997', '#F06595', '#74C0FC', '#A9E34B'
        ]
    ),
    "Night Mode": Theme(
        name="Night Mode",
        bg_app="#1a0a0a",
        bg_plot="#120505",
        fg_text="#eed4d4",
        fg_dim="#522d2d",
        grid=(90, 50, 50, 100),
        crosshair="#cc8888",
        curves=[
            '#00D4FF', '#FF6B6B', '#51CF66', '#FFD43B', '#CC5DE8',
            '#FF922B', '#20C997', '#F06595', '#74C0FC', '#A9E34B'
        ]
    )
}

def get_theme(theme_name: str) -> Theme:
    """Return a Theme object by name. Falls back to Dark."""
    return THEMES.get(theme_name, THEMES["Dark"])
