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
    def __init__(self, path, hwaccel, parent=None):
        super().__init__(parent)
        QOpenGLExtraFunctions.__init__(self)

        self.decoder = VideoDecoder(path, hwaccel)
        self.paused = False

        self._frame = None
        self._lock = threading.Lock()
        
        self.video_width = 0
        self.video_height = 0
        self._texture_id = None
        self._initialized = False 

        # 1. 核心缓冲区：存放解码好的帧 (frame, pts)
        self.frame_queue = queue.Queue(maxsize=5) 
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
        """ 生产者：不停解码存入队列 """
        while self.running:
            if self.paused or self.frame_queue.full():
                time.sleep(0.01)
                continue
                
            frame, pts = self.decoder.read_frame()
            if frame is not None:
                self.frame_queue.put((frame, pts))
            else:
                # 播放结束重置
                self.seek_to(0)

                #直接停止播放
                #self.pause()

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
                    time.sleep(sleep_time)
                    
            except IndexError:
                # 队列空了，等解码
                time.sleep(0.01)
    def seek_to(self, seconds):
        """外部跳转调用"""
        # 1. 停止当前渲染逻辑的判断
        with self._lock:
            # 2. 清空队列，防止播放跳转前的旧帧
            while not self.frame_queue.empty():
                try: self.frame_queue.get_nowait()
                except: break
            
            # 3. 解码器跳转
            self.decoder.seek(seconds)
            
            # 4. 重置时钟：关键！让 elapsed 重新对齐
            self.start_time = time.perf_counter() - seconds
            self._current_pts = seconds

    def play(self):
        self.paused = False
        #self.running=True
    
    def pause(self):
        self.paused = True
        #self.running = False


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