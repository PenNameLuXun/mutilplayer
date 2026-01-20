import math
import av

from PySide6.QtCore import Qt, Signal,QTimer,QPoint
from PySide6.QtWidgets import QWidget, QGridLayout,QPushButton
from PySide6.QtGui import QGuiApplication
import subprocess
from .video_player import VideoPlayer


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

class ScreenPlayer(QWidget):
    def __init__(self, screen, videos, hwaccel):
        super().__init__()

        self.setWindowState(Qt.WindowNoState)
        self.setAttribute(Qt.WA_NativeWindow, True)

        self.panels =[]

        # 屏幕尺寸
        self.screen_w = screen.width
        self.screen_h = screen.height

        self.full_state = False

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
        layout.setContentsMargins(0, 0, 0, 0)

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
            r = i // cols
            c = i % cols
            panel = VideoPlayer(info["path"],info["config"], hwaccel,self)

            panel.request_fullscreen.connect(self.toggle_panel_fullscreen)

            layout.addWidget(panel, r, c)
            self.panels.append(panel)
            self.panel_positions[panel] = (r, c)

    def stop(self):
        for panel in self.panels:
            panel.stop()

    def toggle_full(self,do_full=False):
        self.full_state = do_full
        print("self.full_state:",self.full_state)
        if not self.full_state:
            self.exit_pseudo_fullscreen()
        else:
            self.enter_pseudo_fullscreen()

    def toggle_panel_fullscreen(self, panel: VideoPlayer,full_type:int):
        self.full_panel = panel
        self.full_type  = full_type
        print("full_type:",full_type)
        if self.full_type & FLAG_FULL_WINDOW:
            # 隐藏其他 panel
            for p in self.panels:
                if p is not panel:
                    p.hide()
            # 移除并重新加入，占满 grid
            self.layout.removeWidget(panel)
            self.layout.addWidget(panel, 0, 0, 1, -1)
            panel.raise_()
            panel.setFocus()
        else:
            panel = self.full_panel
            self.layout.removeWidget(panel)

            r, c = self.panel_positions[panel]
            self.layout.addWidget(panel, r, c)

            for p in self.panels:
                p.show()

        self.toggle_full(self.full_type & FLAG_FULL_SCREEN)


    # def enter_panel_fullscreen(self, panel: VideoPlayer,full_type:int):
    #     self.full_panel = panel
    #     self.full_type = full_type
    #     if self.full_type == 0:
    #         # 隐藏其他 panel
    #         for p in self.panels:
    #             if p is not panel:
    #                 p.hide()
    #         # 移除并重新加入，占满 grid
    #         self.layout.removeWidget(panel)
    #         self.layout.addWidget(panel, 0, 0, 1, -1)
    #         panel.raise_()
    #         panel.setFocus()
    #     elif self.full_type==1:
    #         self.toggle_full(True)
    #     elif self.full_type==2:
    #         self.toggle_full(False)

    # def exit_panel_fullscreen(self):
    #     panel = self.full_panel
    #     self.layout.removeWidget(panel)

    #     r, c = self.panel_positions[panel]
    #     self.layout.addWidget(panel, r, c)

    #     for p in self.panels:
    #         p.show()

    #     self.full_panel = None
        

    #     if self.full_type == 1:
    #         self.toggle_full(False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.full_panel:
            self.toggle_panel_fullscreen(self.full_panel,self.full_type&(~FLAG_FULL_SCREEN))
            event.accept()
            return
        super().keyPressEvent(event)


    def enter_pseudo_fullscreen(self):
        if self.windowFlags() & Qt.FramelessWindowHint:
            return
        
        screen = self.windowHandle().screen()

        if not screen:
            screen = QGuiApplication.primaryScreen()

        self._old_geometry = self.geometry()
        self._old_flags = self.windowFlags()

        # 1️⃣ 确保是普通窗口状态
        self.setWindowState(Qt.WindowNoState)

        # 2️⃣ 先 show 一次（非常关键）
        self.show()

        # 3️⃣ 延迟到事件循环后再操作 geometry
        def apply_fullscreen():
            geo = screen.geometry()

            # 去边框
            self.setWindowFlag(Qt.FramelessWindowHint, True)
            self.show()

            # ⚠️ 分两步，避免驱动误判
            # self.move(geo.topLeft())
            # self.resize(geo.size())
            self.setWindowState(Qt.WindowMaximized)

        QTimer.singleShot(20, apply_fullscreen)

    def exit_pseudo_fullscreen(self):
        if not (self.windowFlags() & Qt.FramelessWindowHint):
            return
        
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.setWindowState(Qt.WindowNoState)

        if hasattr(self, "_old_geometry"):
            self.setGeometry(self._old_geometry)

        self.show()



