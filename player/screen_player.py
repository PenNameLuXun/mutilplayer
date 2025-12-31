import math
import av

from PySide6.QtWidgets import QWidget, QGridLayout
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

        # self.setGeometry(screen.x, screen.y, self.screen_w, self.screen_h)
        # self.showFullScreen()

        self.setGeometry(0,0,1200,720)

        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # 读取所有视频分辨率
        video_infos = []
        for video in videos:
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

        # 按最佳布局放置视频
        for i, info in enumerate(video_infos):
            r = i // cols
            c = i % cols
            panel = VideoPlayer(info["path"],info["config"], hwaccel)
            layout.addWidget(panel, r, c)
            self.panels.append(panel)

    def stop(self):
        for panel in self.panels:
            panel.stop()
