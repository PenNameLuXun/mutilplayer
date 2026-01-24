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





import av
import time
from PySide6.QtCore import QObject, Signal, Slot

class PyAVDecoder(QObject):
    # 信号：(view_id, frame_bytes, width, height, format)
    frame_ready = Signal(int, bytes, int, int, str)

    def __init__(self, view_id, video_path):
        super().__init__()
        self.view_id = view_id
        self.video_path = video_path
        self.running = True

        self.size =self.get_video_size(video_path)

    def get_video_size(self,path):
        container = av.open(path)
        stream = container.streams.video[0]
        return stream.width, stream.height

    def run(self):
        """使用 PyAV 进行解码的主循环"""
        try:
            # 打开容器
            container = av.open(self.video_path)
            # 找到第一个视频流
            stream = container.streams.video[0]
            # 自动跳过损坏的帧
            stream.thread_type = "AUTO" 
        except Exception as e:
            print(f"Error opening {self.video_path}: {e}")
            return

        # 获取帧率进行速度控制
        fps = float(stream.average_rate)
        frame_sleep = 1.0 / fps if fps > 0 else 0.04

        while self.running:
            # 循环播放处理：如果读取完毕，重新定位到开头
            try:
                for frame in container.decode(video=0):
                    if not self.running:
                        #print("break")
                        break

                    
                    
                    start_time = time.perf_counter()

                    #print("start_time:",start_time)

                    # --- 核心转换 ---
                    # OpenGL 最好处理 RGB 格式，PyAV 可以直接在转换时完成转换
                    # 我们转成 'rgb24' 对应 OpenGL 的 GL_RGB
                    #rgb_frame = frame.to_image() # 转换为 PIL Image
                    #rgb_frame = frame.to_ndarray(format="rgb24")
                    # 或者更高效的方法直接转为 numpy:
                    # array = frame.to_ndarray(format='rgb24')
                    
                    #print("start_time1:",start_time)
                    # 转换成字节流
                    img_data = frame.to_ndarray(format='rgb24')
                    #img_data = np.ascontiguousarray(img_data, dtype=np.uint8)
                    h, w = img_data.shape[:2]

                    #print("start_time2:",start_time)
                    
                    # 发射信号给 GUI 线程
                    self.frame_ready.emit(self.view_id, img_data.tobytes(), w, h, "RGB")

                    # 帧率同步
                    elapsed = time.perf_counter() - start_time
                    #print("time.sleep:",max(0, frame_sleep - elapsed))
                    time.sleep(max(0, frame_sleep - elapsed))
                    
                
                # 解码结束，重置到容器开头实现循环
                container.seek(0)
                
            except av.AVError:
                container.seek(0)
                continue
            except Exception as e:
                print(f"Decode error: {e}")
                break

        container.close()

    def stop(self):
        self.running = False


from concurrent.futures import ThreadPoolExecutor

class VideoPlayerManager:
    def __init__(self, window, max_threads=4):
        self.window = window
        self.executor = ThreadPoolExecutor(max_workers=max_threads)
        self.decoders = []

    def add_video(self, view_id, video_path):
        """添加一个视频任务到线程池"""
        decoder = PyAVDecoder(view_id, video_path)
        
        # 核心：将解码器的信号连接到窗口的上传槽函数
        # Qt.QueuedConnection 确保信号跨线程安全地进入主线程
        decoder.frame_ready.connect(self.window.sig_frame_ready)
        
        self.decoders.append(decoder)
        # 提交到线程池执行 run 方法
        self.executor.submit(decoder.run)

    def stop_all(self):
        for d in self.decoders:
            d.stop()
        self.executor.shutdown(wait=True)