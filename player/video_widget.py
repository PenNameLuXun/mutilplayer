from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap

class VideoWidget(QLabel):
    def __init__(self, decoder):
        super().__init__()
        self.decoder = decoder
        self.paused = False
        self.current_time = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        if self.paused:
            return

        frame, pts = self.decoder.read_frame()
        if frame is None:
            self.decoder.seek(0)
            return

        self.current_time = pts
        h, w, _ = frame.shape
        img = QImage(frame.data, w, h, 3*w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(img).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def toggle_pause(self):
        self.paused = not self.paused

    def seek(self, seconds):
        self.decoder.seek(seconds)
