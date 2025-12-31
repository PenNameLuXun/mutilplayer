import sys
import json
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from screeninfo import get_monitors
from player.screen_player import ScreenPlayer

def main():
    # 1. 加载配置
    with open("config.json", "r",encoding="utf-8") as f:
        cfg = json.load(f)

    app = QApplication(sys.argv)

    # 2. 处理 Ctrl+C 的关键：将信号重新映射给 Qt 的 quit 槽
    # 这样按下 Ctrl+C 时，app.exec() 会安全返回，并触发 closeEvent
    signal.signal(signal.SIGINT, lambda *args: app.quit())

    # 3. 使用定时器让 Python 解释器有机会处理信号
    # Qt 的主循环有时会完全阻塞 Python 信号处理，加个定时器能确保信号被捕获
    timer = QTimer()
    timer.start(500) 
    timer.timeout.connect(lambda: None) 

    monitors = get_monitors()
    players = []

    for sid, files in cfg["screens"].items():
        idx = int(sid)
        if idx < 0 or idx >= len(monitors):
            print(f"[WARN] Screen index {idx} not available, skip.")
            continue

        player = ScreenPlayer(monitors[idx], files, cfg.get("hwaccel"))
        player.show()
        players.append(player)

    # 4. 运行并确保退出时清理
    exit_code = app.exec()
    
    # 显式停止所有线程（如果 closeEvent 没能覆盖到）
    for p in players:
        if hasattr(p, 'stop'):
            p.stop()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()