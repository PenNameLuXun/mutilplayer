import av
import numpy as np
import threading
class VideoDecoder:
    def __init__(self, path, hwaccel=None):
        options = {}
        if hwaccel:
            options["hwaccel"] = hwaccel

        self.container = av.open(path, options=options)
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"

        # self._prefetched_frame = None

        self.time_base = self.stream.time_base
        self.duration = self.stream.duration * self.time_base

        self.frame_iter = self.container.decode(self.stream)

        # # 获取平均帧率 (fps)
        # fps = self.stream.average_rate
        # if fps is None or fps == 0:
        #     self.frame_interval = 33 # 默认 30fps
        # else:
        #     self.frame_interval = int(1000 / float(fps)) # 计算每帧间隔毫秒数

    def read_frame(self):
        try:
            frame = next(self.frame_iter)
            img = frame.to_ndarray(format="rgb24")
            pts = float(frame.pts * self.time_base)
            return img, pts
        except StopIteration:
            return None, None

    def seek(self, seconds):
        self.want_ts = int(seconds / self.time_base)
        self.container.seek(self.want_ts, stream=self.stream)
        self.frame_iter = self.container.decode(self.stream)



    def get_video_size(path):
        container = av.open(path)
        stream = container.streams.video[0]
        return stream.width, stream.height


