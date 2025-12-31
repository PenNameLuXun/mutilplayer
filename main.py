import sys, json
from PySide6.QtWidgets import QApplication
from screeninfo import get_monitors
from player.screen_player import ScreenPlayer

cfg = json.load(open("config.json"))

app = QApplication(sys.argv)
monitors = get_monitors()

players = []

for sid, files in cfg["screens"].items():
    idx = int(sid)

    if idx < 0 or idx >= len(monitors):
        print(f"[WARN] Screen index {idx} not available, skip.")
        continue

    players.append(
        ScreenPlayer(monitors[idx], files, cfg.get("hwaccel"))
    )


sys.exit(app.exec())
