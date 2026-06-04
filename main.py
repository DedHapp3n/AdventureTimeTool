import sys

from qtwebengine_bootstrap import (
    configure_qtwebengine_logging,
    install_qtwebengine_js_stderr_filter,
)


configure_qtwebengine_logging()
install_qtwebengine_js_stderr_filter()

from PySide6.QtWidgets import QApplication
from ui_main import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
