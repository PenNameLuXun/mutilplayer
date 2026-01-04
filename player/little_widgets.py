import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QSlider, QLabel, QFrame)
from PySide6.QtCore import Qt, QPoint, QTimer,QEvent

# ==========================================================
# 1. 自定义弹出层基类
# ==========================================================
class PopUpContainer(QFrame):
    def __init__(self, parent:QWidget=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("PopUpContainer")
        self.setStyleSheet("""
            #PopUpContainer {
                background-color: rgba(60, 60, 60, 220);
                border-radius: 10px;
            }
            QPushButton { color: white; border: none; padding: 8px; font-size: 11px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 40); }
            /* 倍速选中颜色 */
            .selected { color: #00FF99; } 
        """)
        self.hide()
        self.time = QTimer(self)
        self.time.setInterval(2000)
        self.time.timeout.connect(self.need_hide)

        # 将parent的顶层widget的事件转给self处理一下
        if parent:
            top = parent.topLevelWidget().window()
            print("top:",top)
            if top:
                top.installEventFilter(self)

    def show_right(self):
        target_widget = self.parentWidget()
        if target_widget:
            global_pos = target_widget.mapToGlobal(QPoint(0, 0))
            # 放置在按钮上方（减去菜单高度和一点间距）
            self.adjustSize()
            x = global_pos.x() + (target_widget.width() - self.width()) // 2
            y = global_pos.y() - self.height() - 5
            self.move(x, y)

    def eventFilter(self, watched, event:QEvent):
        if self.parentWidget() and  self.parentWidget().topLevelWidget().window() == watched:
            if event.type()==QEvent.Type.Move:
                self.show_right()
            elif event.type()==QEvent.Type.Hide:
                self.need_hide()
        return super().eventFilter(watched, event)

    def need_hide(self):
        self.hide()
        self.time.stop()

    def leaveEvent(self, event):
        self.time.start()
        super().leaveEvent(event)

    def enterEvent(self, event):
        self.time.stop()
        return super().enterEvent(event)
    
    def showEvent(self, event):
        self.time.start()
        return super().showEvent(event)

# ==========================================================
# 2. 具体弹出内容：倍速菜单
# ==========================================================
class SpeedMenu(PopUpContainer):
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.speeds = ["3倍", "2倍", "1.5倍", "1倍"]
        self.btns = []
        for s in self.speeds:
            btn = QPushButton(s)
            if s == "1倍": btn.setProperty("class", "selected")
            btn.clicked.connect(lambda checked=False, val=s: callback(val))
            layout.addWidget(btn)
            self.btns.append(btn)

# ==========================================================
# 3. 具体弹出内容：音量条
# ==========================================================
class VolumeMenu(PopUpContainer):
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.setFixedSize(40, 150)
        layout = QVBoxLayout(self)
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.setStyleSheet("""
            QSlider::groove:vertical { background: rgba(255,255,255,50); width: 4px; border-radius: 2px; }
            QSlider::handle:vertical { background: white; height: 12px; width: 12px; margin: 0 -4px; border-radius: 6px; }
            QSlider::add-page:vertical { background: white; border-radius: 2px; }
        """)
        self.slider.valueChanged.connect(callback)
        layout.addWidget(self.slider, alignment=Qt.AlignHCenter)
