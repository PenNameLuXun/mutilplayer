import ctypes
from ctypes import wintypes
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QLayout,QGridLayout,QPushButton

def LOWORD(dword):
    return dword & 0xFFFF


def HIWORD(dword):
    return (dword >> 16) & 0xFFFF


RESIZE_BORDER = 8
TITLE_HEIGHT = 9

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

user32 = ctypes.WinDLL("user32", use_last_error=True)

SetWindowLongPtr = user32.SetWindowLongPtrW
GetWindowLongPtr = user32.GetWindowLongPtrW
if ctypes.sizeof(ctypes.c_void_p) == 8:
    LONG_PTR = ctypes.c_int64
else:
    LONG_PTR = ctypes.c_long
SetWindowLongPtr.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    LONG_PTR,
]
SetWindowLongPtr.restype = LONG_PTR

GetWindowLongPtr.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
]
GetWindowLongPtr.restype = LONG_PTR


GWL_STYLE   = -16
GWL_EXSTYLE = -20

WS_EX_APPWINDOW  = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080



class FramelessDraggableWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._fullscreen = False
        self._normalGeometry = None

        #self.setWindowState(Qt.WindowNoState)
        self.setAttribute(Qt.WA_NativeWindow, True)
        #self.setWindowFlags(Qt.Window |Qt.FramelessWindowHint |Qt.WindowDoesNotAcceptFocus)
        self.setWindowFlags(Qt.Window |Qt.FramelessWindowHint)
        #self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        #SetWindowLong(hwnd, GWL_EXSTYLE,GetWindowLong(hwnd, GWL_EXSTYLE) | WS_EX_APPWINDOW);

    def showEvent(self, e):
            super().showEvent(e)

            hwnd = int(self.winId())

            ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            ex_style &= ~WS_EX_TOOLWINDOW
            ex_style |= WS_EX_APPWINDOW
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, ex_style)

            user32.SetWindowPos(
                hwnd, None, 0, 0, 0, 0,
                0x0027
            )

    def nativeEvent(self, eventType, message):
        # Qt 6.6 官方要求
        if eventType != b"windows_generic_MSG":
            return super().nativeEvent(eventType,message)

        addr = int(message)   # ★ 关键一步
        msg = ctypes.cast(addr, ctypes.POINTER(wintypes.MSG)).contents


        #print("msg:",msg)

        if msg.message != WM_NCHITTEST:
            return super().nativeEvent(eventType,message)

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

        if self.drag_test(QCursor.pos()):
            return True, HTCAPTION

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

        return True, HTCLIENT
    
    def drag_test(self,pos):
        pass
