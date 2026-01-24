import sys
import json
import signal
import argparse  # 导入参数解析模块
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from screeninfo import get_monitors
from player.screen_player import ScreenPlayer
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QSurfaceFormat

from player.player_window import VideoGLWindow,GLWindow,MultiVideoWindow
from player.video_decoder import VideoPlayerManager,PyAVDecoder


MY_FLAG = 1
MY_FLAGE_COUNT = 9
def main():
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(description="Multi-screen Video Player")
    parser.add_argument(
        "-f", "--file", 
        type=str, 
        default="config.json", 
        help="Path to the configuration JSON file (default: config.json)"
    )
    args = parser.parse_args()

    # 2. 加载配置
    config_path = args.file
    if not os.path.exists(config_path):
        print(f"[ERROR] Configuration file not found: {config_path}")
        return

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse JSON: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Unexpected error loading config: {e}")
        return

    # 3. 初始化 Qt 环境
    #QApplication.setAttribute(Qt.AA_NativeWindows)
    # 强制启用软件/硬件合成优化
    QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    # 减少渲染层级冲突
    #QApplication.setAttribute(Qt.AA_NativeWindows)
    app = QApplication(sys.argv)

    # 处理 Ctrl+C
    signal.signal(signal.SIGINT, lambda *args: app.quit())

    # 定时器确保 Python 能捕获信号
    timer = QTimer()
    timer.start(500) 
    timer.timeout.connect(lambda: None) 

    monitors = get_monitors()
    players = []

    # 4. 根据配置启动播放器
    if "screens" not in cfg:
        print("[ERROR] No 'screens' defined in config.")
        return

    max_id = 0
    #print("max_id = ",max_id)
    





    if MY_FLAG==1:
        fmt = QSurfaceFormat()
        fmt.setDepthBufferSize(24)
        fmt.setVersion(3, 3)  # 请求 OpenGL 3.3 核心
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        QSurfaceFormat.setDefaultFormat(fmt)
        # pw = GLWindow()
        # pw.show()
        #pw.showFullScreen()

        pw1 = MultiVideoWindow(MY_FLAGE_COUNT)
        pw1.resize(800, 600)
        pw1.show()
        #pw1.showFullScreen()

        # 2. 创建解码管理器 (配置最大线程数)
        manager = VideoPlayerManager(pw1, max_threads=9)


    count_file = 0
    for sid, files in cfg["screens"].items():
        

        #break

        if MY_FLAG==1:
            for video in files["video"]:
                #print("video:",video)
                path = video["path"]
                if count_file < MY_FLAGE_COUNT:
                    manager.add_video(count_file,path)
                count_file = count_file+1

        else:
            idx = int(sid)
        
            if idx < 0 or idx >= len(monitors):
                print(f"[WARN] Screen index {idx} not available, skip.")
                #continue
                idx = max_id
            max_id = idx

            player = ScreenPlayer(monitors[idx], files, cfg.get("hwaccel"))
            player.show()
            players.append(player)



    # 5. 运行并清理
    exit_code = app.exec()
    
    print("Shutting down players...")


    if MY_FLAG==1:
        manager.stop_all()
    else:
        for p in players:
            if hasattr(p, 'stop'):
                p.stop()
    

    sys.exit(exit_code)

if __name__ == "__main__":
    main()