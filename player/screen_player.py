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

class ScreenPlayer(FramelessDraggableWindow):
    def __init__(self, screen, videos, hwaccel,flag = 0):
        super().__init__(None,flag)

        self.panels =[]

        # 屏幕尺寸
        self.screen_w = screen.width
        self.screen_h = screen.height

        self.full_state = False
        self.is_full = False

        self._old_flags = None
        self._old_geometry = None

        self.full_panel = None            # 当前全屏的 panel
        self.full_type = None
        self.panel_positions = {}         # panel -> (row, col)
        self.layout:QGridLayout = None

        self.setGeometry(screen.x, screen.y+30,1200,720)
        #self.showFullScreen()

        layout = QGridLayout(self)

        self.layout = layout              # 保存 grid layout 引用
        

        layout.setSpacing(0)
        layout.setVerticalSpacing(0)
        layout.setHorizontalSpacing(0)
        layout.setContentsMargins(9, 9, 9, 9)

        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(40)
        self.title_bar.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.layout.addWidget(self.title_bar,0,0,1,-1)


        title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar.setLayout(title_bar_layout)

        self.min_btn = QPushButton("-",self)
        self.min_btn.setCheckable(True)
        self.min_btn.toggled.connect(self.min_window)
        self.min_btn.setFixedSize(30, 30)

        self.max_btn1 = QPushButton("[]",self)
        self.max_btn1.setCheckable(True)
        self.max_btn1.toggled.connect(self.toggle_full)
        self.max_btn1.setFixedSize(30, 30)
        

        title_bar_layout.addSpacerItem(QSpacerItem(1,1,QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed))
        title_bar_layout.addWidget(self.max_btn1)
        title_bar_layout.addWidget(self.min_btn)

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

            panel.request_fullscreen.connect(self.toggle_panel_fullscreen)

            layout.addWidget(panel, r , c)
            self.panels.append(panel)
            self.panel_positions[panel] = (r, c)

    def stop(self):
        for panel in self.panels:
            panel.stop()

    def toggle_full(self,do_full=False):
        self.full_state = do_full
        if not self.full_state:
            self.exit_pseudo_fullscreen()
        else:
            self.enter_pseudo_fullscreen()

    def min_window(self):
        self.showMinimized()

    def toggle_panel_fullscreen(self, panel: VideoPlayer,full_type:int):
        self.full_type  = full_type
        print("full_type:",full_type)
        try:
            if self.full_type & FLAG_FULL_WINDOW:
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

            #if panel == self.full_panel or not self.full_panel:
            #self.toggle_full(self.full_type & FLAG_FULL_SCREEN)
        finally:
            pass
            # 布局计算完成后，给一点点缓冲时间再恢复显示
            #QTimer.singleShot(100, lambda: self.setUpdatesEnabled(True))


    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.full_panel:
            self.toggle_full(False)
            event.accept()
            return
        super().keyPressEvent(event)


    def enter_pseudo_fullscreen(self):
        if self.is_full:
             return
        
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

            self.setGeometry(geo.adjusted(-9,-49,9,9))
            
            self.is_full = True

        QTimer.singleShot(20, apply_fullscreen)

    def exit_pseudo_fullscreen(self):
        if not self.is_full:
            return
        
        self.setWindowState(Qt.WindowNoState)

        if hasattr(self, "_old_geometry"):
            self.setGeometry(self._old_geometry)

        self.is_full = False
        self.show()


    def global_R(self,w:QWidget):
        return QRect(w.mapToGlobal(QPoint(0,0)),w.size())
    
    def drag_test(self,g_pos):
        return self.global_R(self.title_bar).contains(g_pos) and not self.global_R(self.max_btn1).contains(g_pos) and not self.global_R(self.min_btn).contains(g_pos)    



