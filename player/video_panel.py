from PySide6.QtWidgets import QWidget, QVBoxLayout
from .video_decoder import VideoDecoder
from .control_bar import ControlBar
from .video_widget import VideoWidget

class VideoPanel(QWidget):
    def __init__(self, path, hwaccel):
        super().__init__()
        layout = QVBoxLayout(self)

        decoder = VideoDecoder(path, hwaccel)
        video = VideoWidget(decoder)
        controls = ControlBar(video)

        layout.addWidget(video, 1)
        layout.addWidget(controls, 0)
