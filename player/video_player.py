import sys,time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QSlider, QLabel, QApplication,QFrame)
from PySide6.QtCore import Qt, Signal,QTimer

from .video_panel import VideoPanel  # 确保路径正确

# 假设你的 VideoPanel 和 VideoDecoder 已经在之前的代码中定义好了
# 这里通过一个包装类将它们组合起来

class VideoPlayer(QWidget):
    def __init__(self, path, config, hwaccel=None):
        super().__init__()
        self.setMouseTracking(True) # 开启鼠标追踪
        self.setContentsMargins(0, 0, 0, 0)
        
        # 1. 初始化视频渲染组件
        self.video_panel = VideoPanel(path, config, hwaccel)
        self.duration = float(self.video_panel.decoder.duration)
        
        # 2. 创建悬浮控制栏容器
        self.control_widget = QFrame(self)
        self.setup_ui()
        self.setup_styles()
        
        # 3. 布局设置 (叠加布局)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_panel)
        
        # 控制栏初始状态
        self.control_widget.hide() 
        
        # 定时器
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_ui_state)
        self.ui_timer.start(100)
        
        self.is_dragging = False

    def setup_ui(self):
        """创建符合图示风格的 UI 布局"""
        # 这里的布局让 control_widget 内部横向排列
        h_layout = QHBoxLayout(self.control_widget)
        h_layout.setContentsMargins(15, 0, 15, 0)
        h_layout.setSpacing(15)

        # 播放/暂停按钮 (用字符模拟图标)
        self.play_btn = QPushButton("ll") # 暂停样式
        self.play_btn.setFixedSize(30, 30)
        
        # 当前时间
        self.cur_time_label = QLabel("00:00")
        
        # 进度条
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(self.duration * 1000))
        
        # 总时长
        self.total_time_label = QLabel(self.format_time(self.duration))
        
        # 倍速和音量
        self.speed_btn = QLabel("倍速")
        self.vol_btn = QPushButton("🔈")
        self.vol_btn.setFixedSize(30, 30)

        # 按顺序添加
        h_layout.addWidget(self.play_btn)
        h_layout.addWidget(self.cur_time_label)
        h_layout.addWidget(self.slider, stretch=1) # 进度条拉伸
        h_layout.addWidget(self.total_time_label)
        h_layout.addWidget(self.speed_btn)
        h_layout.addWidget(self.vol_btn)

        # 信号连接
        self.play_btn.clicked.connect(self.toggle_play)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderMoved.connect(self.on_slider_Moved)
        self.slider.sliderReleased.connect(self.on_slider_released)

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
        self.cur_time_label.setText(cur_str)
        self.total_time_label.setText(total_str)
        self.play_btn.setText("ll" if not self.video_panel.paused else "▶")

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
    


    def setup_styles(self):
        """设置 QSS 样式表，实现半透明黑底和白色细进度条"""
        self.setStyleSheet("""
            QWidget { font-family: "Microsoft YaHei"; color: white; }
            
            /* 控制栏外壳 */
            QFrame {
                background-color: rgba(30, 30, 30, 180); 
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
            }

            /* 按钮样式 */
            QPushButton {
                background: transparent;
                border: none;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover { color: #ccc; }

            /* 进度条样式 (模仿图示) */
            QSlider::groove:horizontal {
                height: 3px;
                background: rgba(255, 255, 255, 60);
            }
            QSlider::sub-page:horizontal {
                background: white;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
        """)

    def resizeEvent(self, event):
        """当窗口大小改变时，重新计算控制栏的位置"""
        super().resizeEvent(event)
        # 将控制栏放在底部居中，左右留间距
        bar_width = self.width() - 40
        bar_height = 30
        self.control_widget.setGeometry(20, self.height() - bar_height - 20, bar_width, bar_height)

    # ================= 交互逻辑 =================

    def enterEvent(self, event):
        """鼠标进入显示控制栏"""
        self.control_widget.show()
        self.control_widget.raise_()

    def leaveEvent(self, event):
        """鼠标离开隐藏控制栏"""
        # 如果正在拖动进度条，不隐藏
        if not self.is_dragging:
            self.control_widget.hide()