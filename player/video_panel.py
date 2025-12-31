# from PySide6.QtWidgets import QWidget, QVBoxLayout
# from .video_decoder import VideoDecoder
# from .control_bar import ControlBar
# from .video_widget import VideoWidget

# class VideoPanel(QWidget):
#     def __init__(self, path, hwaccel):
#         super().__init__()
#         layout = QVBoxLayout(self)

#         decoder = VideoDecoder(path, hwaccel)
#         video = VideoWidget(decoder)
#         controls = ControlBar(video)

#         layout.addWidget(video, 1)
#         #layout.addWidget(controls, 0)


from PySide6.QtOpenGLWidgets import QOpenGLWidget
from .video_decoder import VideoDecoder

from PySide6.QtCore import QTimer
from PySide6.QtOpenGL import QOpenGLTexture
import numpy as np

# video_panel.py
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer
from OpenGL.GL import *
import numpy as np

class VideoPanel(QOpenGLWidget):
    def __init__(self, path, hwaccel, parent=None):
        """
        decoder: 自己封装的解码器对象，必须提供:
            - read_frame() -> (frame: numpy RGBA, pts)
            - seek(seconds)
        """
        super().__init__(parent)
        self.decoder = VideoDecoder(path, hwaccel)
        self.paused = False
        self.frame = None  # 当前帧 (numpy RGBA)
        self.current_time = 0

        # 定时器控制播放
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 控制刷新约33ms => ~30fps

    def update_frame(self):
        if self.paused:
            return

        frame, pts = self.decoder.read_frame()
        if frame is None:
            # 视频播完，循环播放
            self.decoder.seek(0)
            return

        self.frame = frame
        self.current_time = pts
        self.update()  # 触发 paintGL

    def initializeGL(self):
        glClearColor(0, 0, 0, 1)
        glEnable(GL_TEXTURE_2D)

        # 初始化纹理对象
        self.texture_id = glGenTextures(1)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if self.frame is None:
            return

        # 上传帧到纹理
        h, w, _ = self.frame.shape
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, self.frame)

        # 计算缩放矩形保持比例 + 居中
        panel_w, panel_h = self.width(), self.height()
        scale = min(panel_w / w, panel_h / h)
        disp_w, disp_h = w * scale, h * scale
        x, y = (panel_w - disp_w) / 2, (panel_h - disp_h) / 2

        # 绘制纹理矩形
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glBegin(GL_QUADS)
        # 左下角
        glTexCoord2f(0.0, 0.0)
        glVertex2f(x, y)
        # 右下角
        glTexCoord2f(1.0, 0.0)
        glVertex2f(x + disp_w, y)
        # 右上角
        glTexCoord2f(1.0, 1.0)
        glVertex2f(x + disp_w, y + disp_h)
        # 左上角
        glTexCoord2f(0.0, 1.0)
        glVertex2f(x, y + disp_h)
        glEnd()
        glBindTexture(GL_TEXTURE_2D, 0)

    # 控制接口
    def toggle_pause(self):
        self.paused = not self.paused

    def seek(self, seconds):
        self.decoder.seek(seconds)

