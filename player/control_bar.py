from PySide6.QtWidgets import QWidget, QPushButton, QSlider, QHBoxLayout
from PySide6.QtCore import Qt

class ControlBar(QWidget):
    def __init__(self, video):
        super().__init__()
        self.video = video

        layout = QHBoxLayout(self)

        self.btn_play = QPushButton("⏯")
        self.btn_back = QPushButton("⏪3s")
        self.btn_fwd = QPushButton("⏩3s")

        self.progress = QSlider(Qt.Horizontal)
        self.progress.setRange(0, 1000)

        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)

        self.btn_play.clicked.connect(video.toggle_pause)
        self.btn_back.clicked.connect(lambda: video.seek(video.current_time - 3))
        self.btn_fwd.clicked.connect(lambda: video.seek(video.current_time + 3))

        layout.addWidget(self.btn_back)
        layout.addWidget(self.btn_play)
        layout.addWidget(self.btn_fwd)
        layout.addWidget(self.progress)
        layout.addWidget(self.volume)
