import av
import numpy as np

class VideoDecoder:
    def __init__(self, path, hwaccel=None):
        options = {}
        if hwaccel:
            options["hwaccel"] = hwaccel

        self.container = av.open(path, options=options)
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"

        self.time_base = self.stream.time_base
        self.duration = self.stream.duration * self.time_base

        self.frame_iter = self.container.decode(self.stream)

    def read_frame(self):
        try:
            frame = next(self.frame_iter)
            img = frame.to_ndarray(format="rgb24")
            pts = float(frame.pts * self.time_base)
            return img, pts
        except StopIteration:
            return None, None

    def seek(self, seconds):
        ts = int(seconds / self.time_base)
        self.container.seek(ts, stream=self.stream)
        self.frame_iter = self.container.decode(self.stream)

    def get_video_size(path):
        container = av.open(path)
        stream = container.streams.video[0]
        return stream.width, stream.height
    
    def classify_videos(video_infos):
        portrait = []
        landscape = []
        square = []

        for info in video_infos:
            w, h = info["width"], info["height"]
            ratio = w / h

            if ratio < 0.8:
                portrait.append(info)
            elif ratio > 1.25:
                landscape.append(info)
            else:
                square.append(info)

        return portrait, landscape, square


