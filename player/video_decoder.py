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
        self.last_frame = None

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
        # 如果 seek 缓存了帧，先返回缓存的
        if self.last_frame is not None:
            frame = self.last_frame
            self.last_frame = None
        else:
            try:
                frame = next(self.frame_iter)
                
            except StopIteration:
                return None, None
        img = frame.to_ndarray(format="rgb24")
        pts = float(frame.pts * self.time_base)
        return img, pts

    def seek(self, seconds,accre = False):
        self.want_ts = int(seconds / self.time_base)
        self.container.seek(self.want_ts, stream=self.stream)
        self.frame_iter = self.container.decode(self.stream)

        self.last_frame = None
        # 消耗不准确的帧，以抵达准确的位置
        if accre:
            for frame in self.frame_iter:
                if frame.pts is None:
                    continue
                if frame.pts >= self.want_ts:
                    self.last_frame = frame
                    break



    def get_video_size(path):
        container = av.open(path)
        stream = container.streams.video[0]
        return stream.width, stream.height


