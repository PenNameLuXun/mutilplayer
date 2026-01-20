import sys,time
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QSlider, QLabel, QApplication,QFrame)
from PySide6.QtCore import Qt, Signal,QTimer,QPoint

from PySide6.QtGui import QCursor,QKeyEvent

from .video_panel import VideoPanel  # 确保路径正确

from .little_widgets import SpeedMenu,VolumeMenu

# 假设你的 VideoPanel 和 VideoDecoder 已经在之前的代码中定义好了
# 这里通过一个包装类将它们组合起来

class VideoPlayer(QWidget):
    request_fullscreen = Signal(object)  # 把自己传出去
    def __init__(self, path, config, hwaccel=None,parent=None):
        super().__init__(parent)
        self.setMouseTracking(True) # 开启鼠标追踪
        self.setContentsMargins(0, 0, 0, 0)
        
        # 1. 初始化视频渲染组件
        self.video_panel = VideoPanel(path, config, hwaccel)
        self.duration = float(self.video_panel.decoder.duration)
        
        # 2. 创建悬浮控制栏容器
        self.control_widget = QFrame(self)

        # 确保小部件可以接受键盘焦点
        self.setFocusPolicy(Qt.StrongFocus)

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
        self.play_btn.setObjectName("play_btn")
        
        # 当前时间
        self.cur_time_label = QLabel("00:00")
        
        # 进度条
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, int(self.duration * 1000))
        
        # 总时长
        self.total_time_label = QLabel(self.format_time(self.duration))
        
        # 倍速和音量
        self.speed_btn = QPushButton("倍速",self)
        self.speed_btn.setMouseTracking(True)
        self.speed_btn.enterEvent = lambda e: self.show_popup(self.speed_menu, self.speed_btn)
        #self.speed_btn.leaveEvent = lambda e: self.hide_popup(self.speed_menu, self.speed_btn)
        self.speed_btn.setFixedSize(30, 30)
        
        self.vol_btn = QPushButton("🔈",self)
        self.vol_btn.enterEvent = lambda e: self.show_popup(self.volume_menu, self.vol_btn)
        #self.vol_btn.leaveEvent = lambda e: self.hide_popup(self.volume_menu, self.vol_btn)
        self.vol_btn.setFixedSize(30, 30)


        self.max_btn = QPushButton("FULL",self)
        self.max_btn.clicked.connect(self.on_fullscreen_clicked)
        self.max_btn.setFixedSize(30, 30)

        # 初始化弹出组件
        self.speed_menu = SpeedMenu(self.speed_btn, self.on_speed_change)
        self.volume_menu = VolumeMenu(self.vol_btn, self.on_volume_change)

        # 按顺序添加
        h_layout.addWidget(self.play_btn)
        h_layout.addWidget(self.cur_time_label)
        h_layout.addWidget(self.slider, stretch=1) # 进度条拉伸
        h_layout.addWidget(self.total_time_label)
        h_layout.addWidget(self.speed_btn)
        h_layout.addWidget(self.vol_btn)
        h_layout.addWidget(self.max_btn)
        h_layout.setSpacing(3)

        # 信号连接
        self.play_btn.clicked.connect(self.toggle_play)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderMoved.connect(self.on_slider_Moved)
        self.slider.sliderReleased.connect(self.on_slider_released)

    # ==========================================================
    # 核心控制逻辑
    # ==========================================================

    def on_fullscreen_clicked(self):
        self.request_fullscreen.emit(self)


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
                font-size:11px;
            }

            /* 按钮样式 */
            QPushButton {
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#play_btn{font-size: 18px;}
                           
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
        # 1. 正在拖动进度条时不隐藏
        if self.is_dragging:
            return

        # 2. 获取当前鼠标的全局位置
        mouse_pos = QCursor.pos()

        # 3. 检查鼠标是否在倍速菜单或音量菜单的区域内
        # mapFromGlobal 将全局坐标转为小部件内部坐标，看是否在 rect() 范围内
        in_speed_menu = self.speed_menu.isVisible() and \
                        self.speed_menu.rect().contains(self.speed_menu.mapFromGlobal(mouse_pos))
        
        in_volume_menu = self.volume_menu.isVisible() and \
                        self.volume_menu.rect().contains(self.volume_menu.mapFromGlobal(mouse_pos))

        # 如果鼠标进入了这些子插件，则不隐藏控制栏
        if in_speed_menu or in_volume_menu:
            return

        self.control_widget.hide()

    def show_popup(self, menu, target_widget):
        """计算位置并显示弹出层"""
        # 获取按钮在全球屏幕中的位置
        global_pos = target_widget.mapToGlobal(QPoint(0, 0))
        # 放置在按钮上方（减去菜单高度和一点间距）
        menu.adjustSize()
        x = global_pos.x() + (target_widget.width() - menu.width()) // 2
        y = global_pos.y() - menu.height() - 5
        menu.move(x, y)
        menu.show()

    def hide_popup(self, menu, target_widget):
        menu.hide()
        pass

    def on_speed_change(self, val):
        print(f"切换倍速: {val}")
        # 这里调用你解码器的 set_speed 方法
        # 同时更新按钮文字和颜色样式
        self.speed_btn.setText(val)
        self.speed_menu.hide()

    def on_volume_change(self, val):
        # 调整音量逻辑
        pass


    # 重写键盘按下事件
    def keyPressEvent(self, event: QKeyEvent):
        # 左方向键：后退 3 秒
        if event.key() == Qt.Key_Left:
            self.seek_relative(-3)
            # 这里的 seek_relative 是你之前定义的函数
            # 它调用了 self.video_panel.seek_to(target, True)
            event.accept()
            
        # 右方向键：前进 3 秒
        elif event.key() == Qt.Key_Right:
            self.seek_relative(3)
            event.accept()
            
        # 空格键：切换播放/暂停（可选，增加体验）
        elif event.key() == Qt.Key_Space:
            self.toggle_play()
            event.accept()
            
        else:
            super().keyPressEvent(event)