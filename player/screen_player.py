import math
import av

from PySide6.QtWidgets import QWidget, QGridLayout,QPushButton
import subprocess
from .video_player import VideoPlayer

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

        self.panels =[]

        # 屏幕尺寸
        self.screen_w = screen.width
        self.screen_h = screen.height

        #self.setGeometry(screen.x, screen.y, self.screen_w, self.screen_h)
        # self.showFullScreen()

        # self.full_btn = QPushButton("FULL")
        # self.full_state = False
        # self.full_btn.clicked.connect(lambda: self.toggle_full())
        # self.full_btn.setFixedSize(30,30)
        # self.full_btn.show()
        # self.full_btn.raise_()

        self.setGeometry(screen.x, screen.y+30,1200,720)
        #self.showFullScreen()

        layout = QGridLayout(self)
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
            layout.addWidget(panel, r, c)
            self.panels.append(panel)

    def stop(self):
        for panel in self.panels:
            panel.stop()

    # def resizeEvent(self, event):
    #     # 每次窗口大小变动，重新定位按钮
    #     self.full_btn.move(self.width() - 60, 10) 
    #     self.full_btn.raise_()
    #     super().resizeEvent(event)

    def toggle_full(self):
        self.full_state = not self.full_state
        if self.full_state:
            self.showNormal()
        else:
            self.showFullScreen()
