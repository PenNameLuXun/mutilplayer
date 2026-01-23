import ctypes
from ctypes import wintypes
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint


def LOWORD(dword):
    return dword & 0xFFFF


def HIWORD(dword):
    return (dword >> 16) & 0xFFFF


RESIZE_BORDER = 8
TITLE_HEIGHT = 40

WM_NCHITTEST = 0x0084

HTCLIENT = 1
HTCAPTION = 2
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17


class FramelessDraggableWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._fullscreen = False
        self._normalGeometry = None

        self.setWindowState(Qt.WindowNoState)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setWindowFlags(Qt.Window |Qt.FramelessWindowHint |Qt.WindowDoesNotAcceptFocus)

    def nativeEvent(self, eventType, message):

        #print("eventType:",eventType,message)
        # Qt 6.6 官方要求
        if eventType != b"windows_generic_MSG":
            return super().nativeEvent(eventType,message)

        addr = int(message)   # ★ 关键一步
        msg = ctypes.cast(addr, ctypes.POINTER(wintypes.MSG)).contents


        #print("msg:",msg)

        if msg.message != WM_NCHITTEST:
            return False, 0

        if self._fullscreen:
            return True, HTCLIENT

        x = LOWORD(msg.lParam)
        y = HIWORD(msg.lParam)

        #pos = self.mapFromGlobal(QPoint(x, y))
        pos = self.mapFromGlobal(QCursor.pos())

        #print("pos:",pos,x,y,QCursor.pos(),self.mapFromGlobal(QCursor.pos()))

        w = self.width()
        h = self.height()
        m = int(RESIZE_BORDER * self.devicePixelRatioF())

        left   = pos.x() <= m
        right  = pos.x() >= w - m
        top    = pos.y() <= m
        bottom = pos.y() >= h - m

        if top and left:
            return True, HTTOPLEFT
        if top and right:
            return True, HTTOPRIGHT
        if bottom and left:
            return True, HTBOTTOMLEFT
        if bottom and right:
            return True, HTBOTTOMRIGHT
        if left:
            return True, HTLEFT
        if right:
            return True, HTRIGHT
        if top:
            return True, HTTOP
        if bottom:
            return True, HTBOTTOM

        if pos.y() <= TITLE_HEIGHT:
            return True, HTCAPTION

        return True, HTCLIENT
