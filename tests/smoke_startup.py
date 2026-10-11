"""Isolated offscreen startup smoke test; run as a separate process."""

import os
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import app_paths
import main
import ui_main


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "data").mkdir()
    (root / "data" / "settings.json").write_text(json.dumps({"theme": "missing_pack"}), encoding="utf-8")
    app = QApplication([])
    splash = main.create_startup_splash()
    splash.show()
    controller = main.StartupController(app, splash)
    state = {"ok": False}

    def finish():
        state["ok"] = (
            controller.window is not None
            and controller.window.isVisible()
            and controller.window.get_active_theme() == "diablo"
            and getattr(controller.window, "_browser_web_view", None) is not None
            and json.loads((root / "data" / "settings.json").read_text(encoding="utf-8"))["theme"] == "diablo"
        )
        app.quit()

    with patch.object(app_paths, "app_base_dir", return_value=root), patch.object(ui_main, "app_base_dir", return_value=root), patch.object(main, "check_latest_release", return_value=None):
        QTimer.singleShot(0, controller.start)
        QTimer.singleShot(5000, finish)
        app.exec()

    if not state["ok"]:
        raise SystemExit("startup smoke failed")
    print("startup smoke passed")
