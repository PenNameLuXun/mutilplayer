import os
import threading
import ctypes
import numpy as np

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

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_frame)
        self.timer.start(30)

        self.program = None
        self.vao = None
        self.vbo = None
        self.ebo = None

    def _grab_frame(self):
        if self.paused:
            return

        frame, _ = self.decoder.read_frame()
        if frame is None:
            self.decoder.seek(0)
            return

        with self._lock:
            # 必须是 C 连续数组，且类型正确
            self._frame = np.ascontiguousarray(frame, dtype=np.uint8)

        if self._initialized:
            self.update()

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