import av
import numpy as np
import threading
class VideoDecoder:
    def __init__(self, path, hwaccel=None):
        options = {}
        if hwaccel:
            options["hwaccel"] = hwaccel

        self.container = av.open(path, options=options)

        # 视频流设置
        self.v_stream = self.container.streams.video[0]
        self.v_stream.thread_type = "AUTO"
        self.time_base = self.v_stream.time_base
        self.duration = float(self.container.duration / av.time_base)

        # 音频流设置
        self.a_stream = None
        self.resampler = None
        if len(self.container.streams.audio) > 0:
            self.a_stream = self.container.streams.audio[0]
            # 创建重采样器：转为 s16, 44100Hz, 双声道
            self.resampler = av.AudioResampler(
                format='s16',
                layout='stereo',
                rate=44100
            )

        # 改用 demux() 以便同时获取音视频包
        self.packet_gen = self.container.demux(self.v_stream, self.a_stream)
        self.last_frame = None

    def read_packet(self):
        try:
            for packet in self.packet_gen:
                if packet.dts is None: continue
                
                for frame in packet.decode():
                    if packet.stream.type == 'video':
                        img = frame.to_ndarray(format="rgb24")
                        pts = float(frame.pts * self.time_base)
                        return "video", img, pts
                    
                    elif packet.stream.type == 'audio':
                        # 1. 重采样
                        resampled_frames = self.resampler.resample(frame)
                        if resampled_frames:
                            # 2. 修正：使用 to_ndarray().tobytes() 获取字节流
                            # 因为我们重采样为了 's16' 和 'stereo'，ndarray 会是一个 (N, 2) 的数组或交织平铺的数组
                            audio_data = b"".join([f.to_ndarray().tobytes() for f in resampled_frames])
                            
                            pts = float(frame.pts * self.a_stream.time_base)
                            return "audio", audio_data, pts
            return None, None, None
        except Exception as e:
            print(f"Decode error: {e}")
            return None, None, None

    def seek(self, seconds, accre=False):
        target_ts = int(seconds / av.time_base) # av.seek 使用微秒
        self.container.seek(target_ts)
        # 重新生成 packet_gen
        self.packet_gen = self.container.demux(self.v_stream, self.a_stream)


    # def read_frame(self):
    #     # 如果 seek 缓存了帧，先返回缓存的
    #     if self.last_frame is not None:
    #         frame = self.last_frame
    #         self.last_frame = None
    #     else:
    #         try:
    #             frame = next(self.frame_iter)
                
    #         except StopIteration:
    #             return None, None
    #     img = frame.to_ndarray(format="rgb24")
    #     pts = float(frame.pts * self.time_base)
    #     return img, pts

    # def seek(self, seconds,accre = False):
    #     self.want_ts = int(seconds / self.time_base)
    #     self.container.seek(self.want_ts, stream=self.stream)
    #     self.frame_iter = self.container.decode(self.stream)

    #     self.last_frame = None
    #     # 消耗不准确的帧，以抵达准确的位置
    #     if accre:
    #         for frame in self.frame_iter:
    #             if frame.pts is None:
    #                 continue
    #             if frame.pts >= self.want_ts:
    #                 self.last_frame = frame
    #                 break



    def get_video_size(path):
        container = av.open(path)
        stream = container.streams.video[0]
        return stream.width, stream.height


