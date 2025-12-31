from PySide6.QtWidgets import QWidget, QGridLayout
from .video_panel import VideoPanel
import math

class ScreenPlayer(QWidget):
    def __init__(self, screen, videos, hwaccel):
        super().__init__()
        self.setGeometry(screen.x, screen.y, screen.width, screen.height)
        self.showFullScreen()

        layout = QGridLayout(self)
        n = len(videos)
        rows = int(math.sqrt(n))
        cols = math.ceil(n / rows)

        for i, path in enumerate(videos):
            r, c = divmod(i, cols)
            layout.addWidget(VideoPanel(path, hwaccel), r, c)
