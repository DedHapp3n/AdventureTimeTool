import sys

from qtwebengine_bootstrap import (
    configure_qtwebengine_logging,
    install_qtwebengine_js_stderr_filter,
)


configure_qtwebengine_logging()
install_qtwebengine_js_stderr_filter()

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ui_main import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.ensure_visible_on_screen()
    QTimer.singleShot(250, window.preload_browser_if_enabled)
    sys.exit(app.exec())
