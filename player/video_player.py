import sys,time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QSlider, QLabel, QApplication)
from PySide6.QtCore import Qt, Signal,QTimer

from .video_panel import VideoPanel  # 确保路径正确

# 假设你的 VideoPanel 和 VideoDecoder 已经在之前的代码中定义好了
# 这里通过一个包装类将它们组合起来

class VideoPlayer(QWidget):
    def __init__(self, path, config,hwaccel=None):
        super().__init__()
        #self.setWindowTitle("Gemini Video Player")
        #self.resize(1000, 700)

        self.setContentsMargins(0,0,0,0)

        # 1. 初始化渲染组件
        
        self.video_panel = VideoPanel(path, config,hwaccel)
        
        # 获取视频总时长 (用于进度条最大值)
        self.duration = float(self.video_panel.decoder.duration)
        self.current_pts = 0.0

        # 2. 创建 UI 控件
        self.play_btn = QPushButton("S")
        self.prev_btn = QPushButton("<")
        self.next_btn = QPushButton(">")
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(self.duration * 1000))  # 以毫秒为单位提高精度
        
        self.time_label = QLabel("00:00 / 00:00")

        # 3. 布局管理
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.video_panel, stretch=1) # 视频占主要空间

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.prev_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.next_btn)
        control_layout.addWidget(self.slider)
        control_layout.addWidget(self.time_label)
        
        main_layout.addLayout(control_layout)

        # 4. 信号连接
        self.play_btn.clicked.connect(self.toggle_play)
        self.prev_btn.clicked.connect(lambda: self.seek_relative(-3))
        self.next_btn.clicked.connect(lambda: self.seek_relative(3))
        
        # 进度条拖动信号
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderMoved.connect(self.on_slider_Moved)
        self.slider.sliderReleased.connect(self.on_slider_released)

        # UI 更新定时器 (只需要 10Hz 左右，没必要太快)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_ui_state)
        self.ui_timer.start(100) # 100ms 更新一次进度条

        self.is_dragging = False # 防止进度条自动跳动干扰拖拽

    # ==========================================================
    # 核心控制逻辑
    # ==========================================================

    def update_ui_state(self):
        """定时更新进度条和时间文字"""
        if self.is_dragging:
            return
        
        current_pts = self.video_panel.current_second()
        # 更新进度条
        self.slider.blockSignals(True)
        self.slider.setValue(current_pts*1000)
        self.slider.blockSignals(False)
        
        # 更新时间标签
        cur_str = self.format_time(current_pts)
        total_str = self.format_time(self.duration)
        self.time_label.setText(f"{cur_str} / {total_str}")

        self.play_btn.setText("P" if self.video_panel.paused else "S")

    def stop(self):
        self.video_panel.stop()

    def toggle_play(self):
        self.video_panel.toggle()
        self.update_ui_state()

    def seek_relative(self, delta):
        target = max(0, min(self.duration, self.video_panel.current_second() + delta))
        self.video_panel.seek_to(target,True)

    def on_slider_pressed(self):
        self.is_dragging = True
    
    def on_slider_Moved(self,value):
        if self.is_dragging:
            self.seek_to(value)

    def on_slider_released(self):
        target = self.slider.value()
        self.seek_to(target,True)
        self.is_dragging = False
    
    def seek_to(self,value,accurate = False):
        target = value / 1000.0
        self.video_panel.seek_to(target,accurate)

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"