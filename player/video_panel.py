import os
import threading
import ctypes
import numpy as np
import time,queue

from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QOpenGLContext, QOpenGLExtraFunctions
from PySide6.QtCore import QTimer, Qt
from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader

# 导入 PyOpenGL
try:
    from OpenGL import GL
except ImportError:
    raise ImportError("请安装 PyOpenGL: pip install PyOpenGL")

from .video_decoder import VideoDecoder

class VideoPanel(QOpenGLWidget, QOpenGLExtraFunctions):
    def __init__(self, path, config,hwaccel, parent=None):
        super().__init__(parent)
        QOpenGLExtraFunctions.__init__(self)

        self.cfg = config
        print("self.cfg:",self.cfg,hasattr(self.cfg,"play_sections"))
        self.decoder = VideoDecoder(path, hwaccel)
        self.paused = False

        self._frame = None
        self._lock = threading.Lock()
        self.seek_lock = threading.Lock()
        self.pending_seek = None
        
        self.video_width = 0
        self.video_height = 0
        self._texture_id = None
        self._initialized = False 

        # 1. 核心缓冲区：存放解码好的帧 (frame, pts)
        self.frame_queue = queue.Queue(maxsize=8) 
        self.running = True
        self.paused = False
        
        # 2. 状态变量
        self._frame = None
        self._current_pts = 0
        self.start_time = 0

        # 3. 启动后台解码线程
        self.decode_thread = threading.Thread(target=self._decode_loop, daemon=True)
        self.decode_thread.start()

        # 4. 启动渲染轮询线程 (或者使用精准的间隔控制)
        self.render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self.render_thread.start()

        self.program = None
        self.vao = None
        self.vbo = None
        self.ebo = None

    def _decode_loop(self):
        while self.running:
            if self.paused or self.frame_queue.full():
                time.sleep(0.005)
                continue


            # 0. 处理来自UI线程或其他线程的 seek 请求
            with self.seek_lock:
                if self.pending_seek is not None:
                    target = self.pending_seek
                    self.pending_seek = None

                    self.decoder.seek(target)

                    # 清空旧帧
                    while not self.frame_queue.empty():
                        self.frame_queue.get_nowait()

                    # 重置时钟
                    self.start_time = time.perf_counter() - target
                    self._current_pts = target

                    continue  # 非常重要：重新进入循环

            # 1. 检查是否需要跳转到下一个区间
            jump_target = self.next_time()
            if jump_target != -1:
                self.seek_to(jump_target)
                # 跳转后立即继续循环，确保逻辑重新判定
                continue
                
            # 2. 读取帧
            frame, pts = self.decoder.read_frame()
            
            if frame is not None:
                # 3. 关键防御：如果读到的帧 PTS 明显早于当前目标区间（seek 误差产生）
                # 我们需要找到当前应该处于的 start_time
                target_start = self.get_current_section_start(pts)
                if pts < target_start - 0.1:
                    continue # 丢弃该帧，继续读下一帧

                self.frame_queue.put((frame, pts))
            else:
                # 视频结束：安全地回到最初的起点
                sections = self.cfg.get("play_sections", [])
                if sections and len(sections) > 0:
                    # 获取第一个区间的 start_time，如果没有则默认为 0
                    first_start = sections[0].get("start_time", 0)
                    self.seek_to(first_start)
                else:
                    # 如果根本没有 play_sections，就回到视频最开始
                    self.seek_to(0)

    def get_current_section_start(self, pts):
        """辅助函数：找到给定 PTS 应该对应的区间起点"""
        for sec in self.cfg.get("play_sections", []):
            start = float(sec["start_time"])
            duration = float(sec["duration"])
            end = start + duration if duration != -1 else float('inf')
            if pts <= end + 0.1:
                return start
        return 0.0

    def _render_loop(self):
        """ 消费者：根据 PTS 同步时钟 """

        # 初始时先不设置 start_time，等到真正拿到第一帧再开始计时
        self.start_time = None
        #self.start_time = time.perf_counter()
        
        while self.running:
            if self.paused:
                time.sleep(0.01)
                continue

            try:
                # 查看队列里的下一帧，但不取出
                frame, pts = self.frame_queue.queue[0]

                # 如果是第一帧，或者 seek 之后，初始化时钟
                if self.start_time is None:
                    self.start_time = time.perf_counter() - pts
                
                # 计算视频播放到现在的物理时间
                elapsed = time.perf_counter() - self.start_time
                
                # --- 同步核心逻辑 ---
                if elapsed >= pts:
                    # 时间到了，取出并更新画面
                    self.frame_queue.get()
                    with self._lock:
                        self._frame = np.ascontiguousarray(frame, dtype=np.uint8)
                        self._current_pts = pts
                    self.update() # 触发 paintGL
                else:
                    # 时间还没到，休眠一小会儿再检查
                    sleep_time = max(0.001, (pts - elapsed) / 2)
                    #print("in sleep...",sleep_time)
                    time.sleep(sleep_time)
                    
            except IndexError:
                # 队列空了，等解码
                time.sleep(0.01)

    def seek_to(self, seconds):
        self.request_seek(seconds)

    def request_seek(self, seconds):
        with self.seek_lock:
            self.pending_seek = seconds

    def current_second(self):
        # 单位：秒)
        return int(self._current_pts)
    def current_ms(self):
        # 更新进度条 (单位：毫秒)
        return int(self._current_pts * 1000)
    
    def next_time(self):
        if "play_sections" not in self.cfg or not self.cfg["play_sections"]:
            return -1
        
        # 使用真实的浮点 PTS，增加 0.1s 的容差
        curr_pts = self._current_pts 
        sections = self.cfg["play_sections"]
        
        for i, one_section in enumerate(sections):
            start = float(one_section["start_time"])
            duration = float(one_section["duration"])
            # 计算结束时间
            if duration == -1:
                end = float(self.decoder.duration)
            else:
                end = start + duration

            # 逻辑 1：如果你还没到这个区间的开始点（且不在之前的区间内）
            if curr_pts < start - 0.1:
                return start
            
            # 逻辑 2：如果你正处于这个区间内，正常播放
            if start - 0.1 <= curr_pts <= end + 0.1:
                return -1
            
            # 逻辑 3：如果你已经超过了这个区间，循环会进入下一个 i 检查下一个区间
        
        # 逻辑 4：如果你超过了所有区间，回到第一个区间
        return float(sections[0]["start_time"])
                    
    
    def play(self):
        self.paused = False
    
    def pause(self):
        self.paused = True

    def toggle(self):
        self.paused = not self.paused


    def stop(self):
        """强制停止所有线程"""
        self.running = False
        # 唤醒可能阻塞在队列上的线程
        try:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait()
        except:
            pass
        
        # 等待线程结束
        if hasattr(self, 'decode_thread') and self.decode_thread.is_alive():
            self.decode_thread.join(timeout=1.0)
        if hasattr(self, 'render_thread') and self.render_thread.is_alive():
            self.render_thread.join(timeout=1.0)
        print("VideoPanel threads stopped.")

    def initializeGL(self):
        # 即使改用 GL，保留此行以防 Qt 内部需要
        self.initializeOpenGLFunctions()

        self._init_shader()
        self._init_geometry()
        
        # 使用 GL 生成纹理
        self._texture_id = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture_id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        self._initialized = True

    def paintGL(self):
        if not self._initialized or self._texture_id is None:
            return

        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        with self._lock:
            if self._frame is None: return
            frame = self._frame
        
        if frame is None:
            return

        h, w, _ = frame.shape

        self.program.bind()
        # 传入 uniform
        self.program.setUniformValue("videoSize", float(w), float(h))
        self.program.setUniformValue("widgetSize", float(self.width()), float(self.height()))

        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texture_id)

        # 纹理上传
        if w != self.video_width or h != self.video_height:
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D, 0, GL.GL_RGB,
                w, h, 0,
                GL.GL_RGB, GL.GL_UNSIGNED_BYTE, frame
            )
            self.video_width, self.video_height = w, h
        else:
            GL.glTexSubImage2D(
                GL.GL_TEXTURE_2D, 0, 0, 0, w, h,
                GL.GL_RGB, GL.GL_UNSIGNED_BYTE, frame
            )

        GL.glBindVertexArray(self.vao)
        GL.glDrawElements(GL.GL_TRIANGLES, 6, GL.GL_UNSIGNED_INT, None)
        GL.glBindVertexArray(0)

        self.program.release()

    def _init_shader(self):
        self.program = QOpenGLShaderProgram(self)
        vs_src = self._load_shader("video.vert")
        fs_src = self._load_shader("video.frag")

        self.program.addShaderFromSourceCode(QOpenGLShader.Vertex, vs_src)
        self.program.addShaderFromSourceCode(QOpenGLShader.Fragment, fs_src)

        if not self.program.link():
            raise RuntimeError(f"Link Error: {self.program.log()}")

    def _init_geometry(self):
        # 顶点：Pos(x,y), Tex(u,v)
        vertices = np.array([
            -1.0,  1.0,  0.0, 0.0,
            -1.0, -1.0,  0.0, 1.0,
             1.0, -1.0,  1.0, 1.0,
             1.0,  1.0,  1.0, 0.0,
        ], dtype=np.float32)

        indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

        # 全部改用 GL 接口，避免 PySide 属性丢失问题
        self.vao = GL.glGenVertexArrays(1)
        self.vbo = GL.glGenBuffers(1)
        self.ebo = GL.glGenBuffers(1)

        GL.glBindVertexArray(self.vao)

        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)

        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)

        # Pos: index 0
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(0))
        GL.glEnableVertexAttribArray(0)

        # TexCoord: index 1
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 16, ctypes.c_void_p(8))
        GL.glEnableVertexAttribArray(1)

        GL.glBindVertexArray(0)

    def _load_shader(self, name):
        curr_dir = os.path.dirname(__file__)
        path = os.path.join(curr_dir, "..", "shaders", name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        
        # 默认备用 Shader
        if "vert" in name:
            return """
            attribute vec2 pos;
            attribute vec2 tex;
            varying vec2 v_tex;
            void main() {
                gl_Position = vec4(pos, 0.0, 1.0);
                v_tex = tex;
            }
            """
        return """
        uniform sampler2D tex;
        varying vec2 v_tex;
        void main() {
            gl_FragColor = texture2D(tex, v_tex);
        }
        """
    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)


    def destroy(self, /, destroyWindow = ..., destroySubWindows = ...):
        self.stop()
        return super().destroy(destroyWindow, destroySubWindows)