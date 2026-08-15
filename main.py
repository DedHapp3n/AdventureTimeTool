import json
import sys

from qtwebengine_bootstrap import (
    configure_qtwebengine_logging,
    install_qtwebengine_js_stderr_filter,
)


configure_qtwebengine_logging()
install_qtwebengine_js_stderr_filter()

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app_logger import log_warning
from app_paths import resource_path
from ui_main import MainWindow


def create_startup_splash():
    pixmap = QPixmap(420, 220)
    pixmap.fill(QColor(17, 15, 12))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(QColor(197, 151, 67))
    painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)

    icon = QPixmap(str(resource_path("assets/ui_elements/icons/shilling.png")))
    if not icon.isNull():
        scaled_icon = icon.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap((pixmap.width() - scaled_icon.width()) // 2, 28, scaled_icon)

    title_font = QFont("Segoe UI", 19, QFont.Bold)
    painter.setFont(title_font)
    painter.setPen(QColor(255, 225, 150))
    painter.drawText(QRect(20, 112, pixmap.width() - 40, 38), Qt.AlignCenter, "Adventure Time Tool")

    status_font = QFont("Segoe UI", 11)
    painter.setFont(status_font)
    painter.setPen(QColor(220, 210, 185))
    painter.drawText(QRect(20, 156, pixmap.width() - 40, 28), Qt.AlignCenter, "Wird geladen...")
    painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setWindowFlag(Qt.Tool, True)
    return splash


def browser_preload_enabled(window):
    try:
        main_cfg = getattr(window, "main_ui_layout_config", {}).get("browser_screen", {})
        if not isinstance(main_cfg, dict):
            main_cfg = {}
        layout_file = str(main_cfg.get("layout_file", "") or "").strip() or "browser_layout.json"
        active_theme = window.get_active_theme() if hasattr(window, "get_active_theme") else "diablo"
        assets_dir = getattr(window, "assets_dir", resource_path("assets"))
        candidates = [
            assets_dir / "themes" / active_theme / layout_file,
            assets_dir / "themes" / "diablo" / "browser_layout.json",
        ]
        cfg = {}
        for layout_path in candidates:
            if not layout_path.exists():
                continue
            with open(layout_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("browser_screen"), dict):
                cfg = data["browser_screen"]
                break
        return isinstance(cfg, dict) and bool(cfg.get("preload_on_start", False))
    except Exception as exc:
        log_warning("browser", f"browser preload config check failed: {exc}")
        return True


def show_main_window(window, splash):
    window.show()
    window.ensure_visible_on_screen()
    QTimer.singleShot(0, splash.close)


def initialize_hidden_browser_then_show(window, splash):
    try:
        window.preload_browser_if_enabled()
    except Exception as exc:
        log_warning("browser", f"browser preload failed: {exc}")
    QTimer.singleShot(750, lambda: show_main_window(window, splash))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = create_startup_splash()
    splash.show()
    app.processEvents()

    window = MainWindow()
    if browser_preload_enabled(window):
        QTimer.singleShot(0, lambda: initialize_hidden_browser_then_show(window, splash))
    else:
        QTimer.singleShot(0, lambda: show_main_window(window, splash))
    sys.exit(app.exec())
