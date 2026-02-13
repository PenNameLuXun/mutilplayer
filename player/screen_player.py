import math
import av

from PySide6.QtCore import Qt, Signal,QTimer,QPoint,QRect
from PySide6.QtWidgets import QWidget, QGridLayout,QPushButton,QSizePolicy,QHBoxLayout,QSpacerItem
from PySide6.QtGui import QGuiApplication
import subprocess
from .video_player import VideoPlayer

from .frameless_window import FramelessDraggableWindow
from PySide6.QtOpenGLWidgets import QOpenGLWidget


FLAG_FULL_WINDOW = 0b0001  # 1
FLAG_FULL_SCREEN = 0b0010  # 2

# ------------------------------------------------------------
# 工具函数：读取视频分辨率
# ------------------------------------------------------------
def get_video_size(path):
    container = av.open(path)
    stream = container.streams.video[0]
    return stream.width, stream.height


# ------------------------------------------------------------
# 按纵横比分类
# ------------------------------------------------------------
def classify_videos(video_infos):
    portrait = []   # 竖屏：高 > 宽
    landscape = []  # 横屏：宽 > 高
    square = []     # 接近正方形

    for info in video_infos:
        w = info["width"]
        h = info["height"]

        if h > w * 1.15:
            portrait.append(info)
        elif w > h * 1.15:
            landscape.append(info)
        else:
            square.append(info)

    return portrait, landscape, square
def probe_resolution(path):
    # """使用 ffprobe 获取视频分辨率"""
    # cmd = [
    #     "ffprobe", "-v", "error",
    #     "-select_streams", "v:0",
    #     "-show_entries", "stream=width,height",
    #     "-of", "csv=p=0",
    #     path
    # ]
    # out = subprocess.check_output(cmd).decode().strip()
    # w, h = out.split(",")
    return get_video_size(path)
    return int(w), int(h)

TITLE_BAR_HEIGHT = 30
class ScreenPlayer(FramelessDraggableWindow):
    def __init__(self, screen, videos, hwaccel,flag = 0):
        super().__init__(None,flag)

        self.panels =[]

        # 屏幕尺寸
        self.screen_w = screen.width
        self.screen_h = screen.height

        self.full_screen = False
        self.full_window = False

        self._old_flags = None
        self._old_geometry = None

        self.full_panel = None            # 当前全屏的 panel
        
        self.panel_positions = {}         # panel -> (row, col)
        self.layout:QGridLayout = None

        self.setGeometry(screen.x, screen.y+30,1200,720)

        layout = QGridLayout(self)

        self.layout = layout              # 保存 grid layout 引用
        

        layout.setSpacing(0)
        layout.setVerticalSpacing(0)
        layout.setHorizontalSpacing(0)
        layout.setContentsMargins(9, 9, 9, 9)

        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(TITLE_BAR_HEIGHT)
        self.title_bar.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.layout.addWidget(self.title_bar,0,0,1,-1)


        title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar.setLayout(title_bar_layout)

        self.min_btn = QPushButton("-",self)
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.setFixedSize(30, TITLE_BAR_HEIGHT)

        self.max_btn = QPushButton("M",self)
        self.max_btn.setCheckable(True)
        self.max_btn.toggled.connect(lambda b: self.toggle_fullscreen(None,b))
        self.max_btn.setFixedSize(30, TITLE_BAR_HEIGHT)

        self.close_btn = QPushButton("X",self)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setFixedSize(30, TITLE_BAR_HEIGHT)
        

        title_bar_layout.addSpacerItem(QSpacerItem(1,1,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed))
        title_bar_layout.addWidget(self.min_btn)
        title_bar_layout.addWidget(self.max_btn)
        title_bar_layout.addWidget(self.close_btn)

        title_bar_layout.setContentsMargins(0,0,0,0)


        # 读取所有视频分辨率
        video_infos = []
        for video in videos["video"]:
            print("video:",video)
            path = video["path"]
            vw, vh = probe_resolution(path)
            video_infos.append({
                "path": path,
                "w": vw,
                "h": vh,
                "ar": vw / vh,
                "config":video
            })

        n = len(video_infos)
        if n == 0:
            return

        # 枚举所有 rows / cols 组合，寻找面积最大方案
        best = None

        for cols in range(1, n + 1):
            rows = math.ceil(n / cols)

            cell_w = self.screen_w / cols
            cell_h = self.screen_h / rows

            total_area = 0.0

            for info in video_infos:
                scale = min(
                    cell_w / info["w"],
                    cell_h / info["h"]
                )
                disp_w = info["w"] * scale
                disp_h = info["h"] * scale
                total_area += disp_w * disp_h

            if best is None or total_area > best["area"]:
                best = {
                    "rows": rows,
                    "cols": cols,
                    "area": total_area
                }

        rows = best["rows"]
        cols = best["cols"]


        if  "cols" in videos:
            cols = videos["cols"]

        # 按最佳布局放置视频
        for i, info in enumerate(video_infos):
            r = i // cols+ 1
            c = i % cols
            panel = VideoPlayer(info["path"],info["config"], hwaccel,self,flag)

            panel.request_fullwindow.connect(self.toggle_fullwindow)
            panel.request_fullscreen.connect(self.toggle_fullscreen)

            layout.addWidget(panel, r , c)
            self.panels.append(panel)
            self.panel_positions[panel] = (r, c)

    def stop(self):
        for panel in self.panels:
            panel.stop()

    def toggle_fullscreen(self, panel: VideoPlayer,do_full=False):
        if self.full_screen == do_full:
            return
        
        self.full_screen = do_full
        if not self.full_screen:
            self.exit_pseudo_fullscreen()
        else:
            self.enter_pseudo_fullscreen()

    # def min_window(self):
    #     self.showMinimized()

    def toggle_fullwindow(self, panel: VideoPlayer,full_window:int):
        if self.full_window == full_window:
            return
        
        self.full_window = full_window
        
        if full_window:
            print("toggle_fullwindow....:",full_window)
            self.full_panel = panel
            # 隐藏其他 panel
            for p in self.panels:
                if p is not panel:
                    p.hide()
            # 移除并重新加入，占满 grid
            self.layout.removeWidget(panel)
            self.layout.addWidget(panel, 1, 0, 1, -1)
            panel.raise_()
            #panel.setFocus()
        else:
            self.layout.removeWidget(panel)

            r, c = self.panel_positions[panel]
            self.layout.addWidget(panel, r, c)

            for p in self.panels:
                p.show()

        



    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.full_panel:
            self.toggle_fullwindow(self.full_panel,False)
            event.accept()
            return
        super().keyPressEvent(event)


    def enter_pseudo_fullscreen(self):
        
        screen = self.windowHandle().screen()

        if not screen:
            screen = QGuiApplication.primaryScreen()

        self._old_geometry = self.geometry()
        self._old_flags = self.windowFlags()

        # 2️⃣ 先 show 一次（非常关键）
        self.show()

        # 3️⃣ 延迟到事件循环后再操作 geometry
        def apply_fullscreen():
            geo = screen.geometry()
            self.show()
            self.setGeometry(geo.adjusted(-9,-TITLE_BAR_HEIGHT-9,9,9))
            self.full_screen = True

            self.update_ui()
            

        QTimer.singleShot(20, apply_fullscreen)

    def exit_pseudo_fullscreen(self):
        
        self.setWindowState(Qt.WindowNoState)

        if hasattr(self, "_old_geometry"):
            self.setGeometry(self._old_geometry)

        self.show()

        self.full_screen = False

        self.update_ui()


    def update_ui(self):
        self.max_btn.blockSignals(True)
        self.max_btn.setChecked(self.full_screen)
        self.max_btn.blockSignals(False)



    def global_R(self,w:QWidget):
        return QRect(w.mapToGlobal(QPoint(0,0)),w.size())
    

    def drag_ignore_widgets(self):
        return [self.min_btn,self.max_btn,self.close_btn]
    
    def drag_test(self,g_pos):
        if self.global_R(self.title_bar).contains(g_pos):
            for w in self.drag_ignore_widgets():
                if self.global_R(w).contains(g_pos):
                    return False
            return True
        return False  
    
    def resize_margin(self):
        return self.layout.contentsMargins().top()



