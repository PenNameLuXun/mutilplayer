from PySide6.QtGui import (
    QOpenGLFunctions,
    QPainter,
    QColor,
)
from PySide6.QtOpenGL import QOpenGLWindow
from PySide6.QtCore import Qt, QRect, QPoint

from PySide6.QtOpenGL import QOpenGLWindow,QOpenGLShader, QOpenGLShaderProgram
from PySide6.QtGui import QMatrix4x4, QVector3D,QWindow
from OpenGL.GL import *
import numpy as np
import os

class GLWindow(QOpenGLWindow):
    def __init__(self):
        super().__init__()
        self.program = None
        self.texture = None
        self.vbo = None
        self.vao = None
        self.proj_matrix_loc = None
        self.cam_matrix_loc = None
        self.world_matrix_loc = None
        self.uniforms_dirty = True

        # 摄像机 / 变换状态
        self.eye = QVector3D(0.0, 0.0, 5.0)
        self.r = 0.0

    def initializeGL(self):
        # 创建并编译着色器
        self.program = QOpenGLShaderProgram(self)
        self.program.addShaderFromSourceCode(
            QOpenGLShader.Vertex,
            """
            #version 330 core
            layout(location = 0) in vec3 vertex;
            uniform mat4 projMatrix;
            uniform mat4 camMatrix;
            uniform mat4 worldMatrix;
            void main() {
                gl_Position = projMatrix * camMatrix * worldMatrix * vec4(vertex, 1.0);
            }
            """
        )
        self.program.addShaderFromSourceCode(
            QOpenGLShader.Fragment,
            """
            #version 330 core
            out vec4 fragColor;
            void main() {
                fragColor = vec4(0.6, 0.7, 0.9, 1.0);
            }
            """
        )
        self.program.link()

        # 获取 uniform 位置
        self.proj_matrix_loc = self.program.uniformLocation("projMatrix")
        self.cam_matrix_loc = self.program.uniformLocation("camMatrix")
        self.world_matrix_loc = self.program.uniformLocation("worldMatrix")

        # 顶点数组（一个简单三角形示例）
        vertices = np.array([
            -0.5, -0.5, 0.0,
             0.5, -0.5, 0.0,
             0.0,  0.5, 0.0,
        ], dtype=np.float32)

        # 创建 VAO + VBO
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        pos_attrib = self.program.attributeLocation("vertex")
        glEnableVertexAttribArray(pos_attrib)
        glVertexAttribPointer(pos_attrib, 3, GL_FLOAT, GL_FALSE, 0, None)

        glBindVertexArray(0)

        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w: int, h: int):
        aspect = w / max(h, 1)
        proj = QMatrix4x4()
        proj.perspective(45.0, aspect, 0.1, 100.0)
        self.program.bind()
        self.program.setUniformValue(self.proj_matrix_loc, proj)
        self.program.release()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.program.bind()

        # 摄像机矩阵
        cam = QMatrix4x4()
        cam.lookAt(self.eye, QVector3D(0, 0, 0), QVector3D(0, 1, 0))
        self.program.setUniformValue(self.cam_matrix_loc, cam)

        # 世界变换（这里不做旋转）
        world = QMatrix4x4()
        self.program.setUniformValue(self.world_matrix_loc, world)

        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, 3)
        glBindVertexArray(0)

        self.program.release()



# import sys
# import numpy as np
# from PyQt5.QtWidgets import QApplication
# from PyQt6.QtGui import QOpenGLWindow, QOpenGLShaderProgram, QOpenGLShader, QMatrix4x4, QVector3D
# from OpenGL.GL import *
from PySide6.QtCore import Signal, Slot, Qt, QSize

import sys
import numpy as np
from PySide6.QtCore import Signal, Slot, Qt, QSize
# from PySide6.QtGui import QOpenGLWindow, QMatrix4x4, QVector3D, QSurfaceFormat
# from PySide6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
# from PySide6.QtWidgets import QApplication

# 如果你安装了 PyOpenGL，保留这个引用
# 如果没有，PySide6 其实自带了 OpenGL 包装，但混用 PyOpenGL 比较常见且方便
from OpenGL.GL import *
import ctypes

class VideoGLWindow(QOpenGLWindow):
    # 【关键修改 1】定义信号：参数为 (图像数据bytes, 宽, 高, 格式)
    sig_frame_ready = Signal(int,bytes, int, int, str)

    sig_stop = Signal()

    def __init__(self):
        super().__init__()

        #self.setAttribute(Qt.WA_NativeWindow, True)
        #self.setWindowFlags(Qt.Window |Qt.FramelessWindowHint |Qt.WindowDoesNotAcceptFocus)
        self.setFlags(Qt.Window | Qt.FramelessWindowHint)

        self.program = None
        self.texture_id = None
        self.vbo = None
        self.vao = None
        
        # 矩阵位置
        self.proj_matrix_loc = None
        self.cam_matrix_loc = None
        self.world_matrix_loc = None
        self.tex_uniform_loc = None
        
        self.eye = QVector3D(0.0, 0.0, 2.0)

        self._initialized = False
        self._frame_vaild = None

        # 【关键修改 2】连接信号到槽函数
        # Qt.QueuedConnection 确保槽函数一定在接收者所在的线程（主线程）执行
        self.sig_frame_ready.connect(self.upload_texture_slot, Qt.QueuedConnection)

    def initializeGL(self):
        # 即使改用 GL，保留此行以防 Qt 内部需要
        #self.initializeOpenGLFunctions()

        self._init_shader()
        self._init_geometry()
        
        # 使用 GL 生成纹理
        self._texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        glClearColor(0.0, 0.0, 0.0, 1.0)
        self._initialized = True

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
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        self.ebo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        # Pos: index 0
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # TexCoord: index 1
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)

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

    # def resizeGL(self, w, h):
    #     glViewport(0, 0, w, h)
    #     aspect = w / max(h, 1)
    #     proj = QMatrix4x4()
    #     proj.perspective(45.0, aspect, 0.1, 100.0)
        
    #     self.program.bind()
    #     self.program.setUniformValue(self.proj_matrix_loc, proj)
    #     self.program.release()

    def paintGL(self):
        if not self.isExposed():
            return
        
        if not self._initialized or self.texture_id is None:
            return
        
        # 这里的 glClear, glBindVertexArray 等必须在主线程执行
        # 如果后台线程正在 makeCurrent，这里就会报 1282 错误
        glClearColor(0.1, 0.1, 0.1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        if self.texture_id is None:
            return

        self.program.bind()
        
        cam = QMatrix4x4()
        cam.lookAt(self.eye, QVector3D(0, 0, 0), QVector3D(0, 1, 0))
        self.program.setUniformValue(self.cam_matrix_loc, cam)
        
        world = QMatrix4x4()
        self.program.setUniformValue(self.world_matrix_loc, world)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        if self._frame_vaild:
            self.program.setUniformValue("videoTexture", 0)


        #print("self.vao:",self.vao)
        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)

        self.program.release()

    # 【关键修改 3】提供给外部调用的线程安全接口
    def push_frame(self, img_data, width, height, fmt="RGB"):
        """
        供视频解码线程调用。
        将 numpy 数组转换为 bytes 并发射信号，绝对不触碰 OpenGL。
        """
        # 确保数据是 bytes 类型，防止跨线程内存引用问题
        if hasattr(img_data, 'tobytes'):
            data_bytes = img_data.tobytes()
        else:
            data_bytes = img_data
        
        # 发射信号
        self.sig_frame_ready.emit(data_bytes, width, height, fmt)

    # 【关键修改 4】槽函数：在主线程执行纹理上传
    @Slot(int,bytes, int, int, str)
    def upload_texture_slot(self, view_id, data_bytes, width, height, fmt):
        if not self.isExposed():
            return

        # 此时已经在主线程，可以安全地操作 OpenGL
        self.makeCurrent()
        
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        gl_fmt = GL_RGB
        if fmt == "BGR": gl_fmt = GL_BGR
        elif fmt == "RGBA": gl_fmt = GL_RGBA
        elif fmt == "BGRA": gl_fmt = GL_BGRA

        # 上传纹理
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, gl_fmt, GL_UNSIGNED_BYTE, data_bytes)
        
        glBindTexture(GL_TEXTURE_2D, 0)

        self._frame_vaild = True
        
        # 触发 paintGL 进行绘制
        self.update()

    def toggle_player_fullscreen(self):
        if self.visibility() != QWindow.FullScreen:
            # 获取当前屏幕的硬件尺寸
            screen = self.screen()
            self.setFlags(Qt.Window | Qt.FramelessWindowHint)
            self.setGeometry(screen.geometry())
            self.show()
        else:
            self.setFlags(Qt.Window) # 还原边框
            self.showNormal()

class MultiVideoWindow(VideoGLWindow): # 继承你之前的类
    def __init__(self, max_views=4):
        super().__init__()
        self.max_views = max_views
        # 存储多个画面的数据 {index: texture_id}
        self.textures = {} 
        # 存储每个画面的宽和高
        self.frame_info = {} 

        self.video_width = 0
        self.video_height = 0

    def initializeGL(self):

        print("MultiVideoWindow initializeGL....")
        super().initializeGL()
        # 初始化时预生成多个纹理ID
        for i in range(self.max_views):
            tex_id = int(glGenTextures(1))
            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            self.textures[i] = tex_id
            self.frame_info[i] = (False,0, 0,None,"RGB")

    @Slot(int, bytes, int, int, str)
    def upload_texture_slot(self, view_id, data_bytes, width, height, fmt):
        # if view_id not in self.textures:
        #     return

        # # 只缓存
        # self.frame_info[view_id] = (True, width, height, data_bytes, fmt)

        # # 请求重绘
        # self.update()
        if view_id not in self.textures: return

        self.makeCurrent() # 必须在操作 GL 前调用
        
        # 1. 获取该通道缓存的状态
        # 我们需要存储宽高来判断是否需要用 SubImage2D
        valid, old_w, old_h, _, old_fmt = self.frame_info.get(view_id, (False, 0, 0, None, "RGB"))
        
        glBindTexture(GL_TEXTURE_2D, self.textures[view_id])
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        gl_fmt = GL_BGR if fmt == "BGR" else GL_RGB

        # 2. 性能分水岭：如果是第一次或分辨率变了，执行 glTexImage2D (买新房)
        if not valid or old_w != width or old_h != height:
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, gl_fmt, GL_UNSIGNED_BYTE, data_bytes)
        else:
            # 3. 绝大多数情况下执行 glTexSubImage2D (换家具)，效率极高
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height, gl_fmt, GL_UNSIGNED_BYTE, data_bytes)

        # 4. 存储状态，注意：这里不再把 data_bytes 存进内存字典，避免内存爆涨
        # 我们只存宽高给 Shader 用
        self.frame_info[view_id] = (True, width, height, None, fmt)
        
        self.update()

    def paintGL(self):
        # glClearColor(0, 0, 0, 1)
        # glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # self.program.bind()

        # # cam = QMatrix4x4()
        # # cam.lookAt(self.eye, QVector3D(0,0,0), QVector3D(0,2,0))
        # # world = QMatrix4x4()

        # # self.program.setUniformValue(self.cam_matrix_loc, cam)
        # # self.program.setUniformValue(self.world_matrix_loc, world)

        # glBindVertexArray(self.vao)

        # # 2. 计算网格
        # cols = 2 if self.max_views > 1 else 1
        # rows = (self.max_views + cols - 1) // cols


        


        # # win_w = self.width()
        # # win_h = self.height()
        # # cell_w = win_w // cols
        # # cell_h = win_h // rows

        # current_cell_num = self.max_views


        # dpr = self.devicePixelRatio()
        # fb_w = int(self.width() * dpr)
        # fb_h = int(self.height() * dpr)



        # # 一行多少个
        # cols:int = 3

        # #一列多少个 整数
        # col_n =  (current_cell_num + cols - 1) // cols


        # cell_w = fb_w/cols
        # cell_h = fb_h/col_n

        # for i in range(self.max_views):
        #     valid, vw, vh, data, fmt = self.frame_info.get(i, (False,0,0,None,None))
        #     if not valid:
        #         continue

        #     cell_i = i//cols

        #     #grid_y = cell_i*cell_h
        #     grid_y = (col_n - 1 - cell_i) * cell_h   # OpenGL 左下角
        #     grid_x = (i%cols)*cell_w



        #     # ---- 这里就是 glViewport 的正确位置 ----
        #     self.program.setUniformValue("videoSize", float(vw), float(vh))
        #     self.program.setUniformValue("widgetSize", float(cell_w), float(cell_h))
        #     # if i == 2:
        #     #     print("cell:",cell_i,grid_x,grid_y,cell_w,cell_h,self.size())
        #     glViewport(int(grid_x), int(grid_y), int(cell_w), int(cell_h))

            
        #     glActiveTexture(GL_TEXTURE0)
        #     glBindTexture(GL_TEXTURE_2D, self.textures[i])

        #     gl_fmt = GL_BGR if fmt == "BGR" else GL_RGB

        #     glTexImage2D(
        #         GL_TEXTURE_2D, 0, GL_RGB,
        #         vw, vh, 0,
        #         gl_fmt, GL_UNSIGNED_BYTE, data
        #     )

        #     # 设置 viewport + draw
        #     glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        # glBindVertexArray(0)
        # self.program.release()

        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.program.bind()
        glBindVertexArray(self.vao)

        dpr = self.devicePixelRatio()
        fb_w, fb_h = int(self.width() * dpr), int(self.height() * dpr)

        cols = 3
        col_n = (self.max_views + cols - 1) // cols
        cell_w, cell_h = fb_w / cols, fb_h / col_n

        for i in range(self.max_views):
            # 从缓存读取该画面的属性
            valid, vw, vh, _, _ = self.frame_info.get(i, (False, 0, 0, None, None))
            if not valid: continue

            # 计算网格坐标 (OpenGL y轴从底向上)
            row_idx = i // cols
            grid_y = (col_n - 1 - row_idx) * cell_h 
            grid_x = (i % cols) * cell_w

            # --- 设置 Shader 需要的三个关键 Uniform ---
            # 1. 视口大小（当前格子的像素宽和高）
            glViewport(int(grid_x), int(grid_y), int(cell_w), int(cell_h))
            
            # 2. 传递给你的 Shader 进行比例计算
            self.program.setUniformValue("videoSize", float(vw), float(vh))
            self.program.setUniformValue("widgetSize", float(cell_w), float(cell_h))

            # 3. 纹理绑定
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.textures[i])
            #self.program.setUniformValue("tex", 0)

            glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)

        glBindVertexArray(0)
        self.program.release()

    def stop(self):
        pass

    def closeEvent(self, event):
        self.sig_stop.emit()
        super().closeEvent(event)


    def destroy(self, /, destroyWindow = ..., destroySubWindows = ...):
        self.sig_stop.emit()
        return super().destroy(destroyWindow, destroySubWindows)


