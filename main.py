import json
import os
import shutil
import subprocess
import sys

from qtwebengine_bootstrap import (
    configure_qtwebengine_logging,
    install_qtwebengine_js_stderr_filter,
)


configure_qtwebengine_logging()
install_qtwebengine_js_stderr_filter()

from PySide6.QtCore import QObject, QRect, Qt, QThread, QTimer, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from app_logger import log_info, log_warning
from app_paths import app_base_dir, ensure_runtime_defaults, resource_path
from texturepacks import available_texturepacks, ensure_texturepacks_dir, layout_candidates
from update_manager import check_latest_release, prepare_update
from version import APP_VERSION
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
        candidates = layout_candidates(active_theme, layout_file, "browser_layout.json")
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


class StartupWorker(QThread):
    def __init__(self, operation, argument=None):
        super().__init__()
        self.operation = operation
        self.argument = argument
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = (
                check_latest_release()
                if self.operation == "check"
                else prepare_update(self.argument)
            )
            self.error = None
        except Exception as exc:
            self.result = None
            self.error = str(exc)


class StartupController(QObject):
    def __init__(self, app, splash):
        super().__init__()
        self.app = app
        self.splash = splash
        self.workers = []
        self.window = None
        self.app.aboutToQuit.connect(self._wait_for_workers)

    def start(self):
        try:
            ensure_runtime_defaults()
            ensure_texturepacks_dir()
            available_texturepacks()
        except Exception as exc:
            log_warning("startup", f"runtime setup failed: {exc}")
        self.splash.showMessage("Prüfe auf Updates...", Qt.AlignBottom | Qt.AlignHCenter, QColor(220, 210, 185))
        log_info("update", "UPDATE CHECK START")
        self._work("check", None, self._checked)

    def _work(self, operation, argument, callback):
        worker = StartupWorker(operation, argument)
        worker.callback = callback
        self.workers.append(worker)
        worker.finished.connect(self._worker_finished)
        worker.start()
        return worker

    @Slot()
    def _worker_finished(self):
        worker = self.sender()
        if not isinstance(worker, StartupWorker):
            log_warning("startup", "worker finished without StartupWorker sender")
            return
        worker.wait()
        if worker.isRunning():
            log_warning("startup", f"worker still running after finished: {worker.operation}")
            return
        if worker.operation == "check":
            log_info("update", "UPDATE CHECK FINISHED")
        result = worker.result
        error = worker.error
        try:
            worker.callback(result, error)
        finally:
            if worker in self.workers:
                self.workers.remove(worker)
            worker.deleteLater()

    def _wait_for_workers(self):
        for worker in list(self.workers):
            if worker.isRunning():
                worker.wait()

    def _checked(self, release, error):
        if error:
            log_warning("update", f"release check failed: {error}")
        if not release:
            self._start_window()
            return
        log_info("update", f"UPDATE FOUND {release['version']}")
        if not getattr(sys, "frozen", False):
            log_warning("update", f"release {release['version']} available; source checkout is not self-updated")
            self._start_window()
            return
        self.splash.hide()
        answer = QMessageBox.question(
            None, "Adventure Time Tool Update",
            f"Version {release['version']} ist verfügbar (installiert: {APP_VERSION}). Jetzt herunterladen und installieren?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        self.splash.show()
        if answer != QMessageBox.Yes:
            self._start_window()
            return
        self.splash.showMessage("Lade Update herunter und prüfe Dateien...", Qt.AlignBottom | Qt.AlignHCenter, QColor(220, 210, 185))
        log_info("update", "UPDATE PREPARE START")
        self._work("prepare", release, self._prepared)

    def _prepared(self, payload, error):
        if error or payload is None:
            log_warning("update", f"update preparation failed: {error}")
            self.splash.hide()
            QMessageBox.warning(None, "Update fehlgeschlagen", f"Das Update konnte nicht vorbereitet werden:\n{error}")
            self.splash.show()
            self._start_window()
            return
        try:
            worker_source = resource_path("update_worker.ps1")
            worker_copy = payload.parent / "update_worker.ps1"
            shutil.copy2(worker_source, worker_copy)
            log_info("update", "UPDATE WORKER COPY")
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            process = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(worker_copy),
                 "-ParentPid", str(os.getpid()), "-Payload", str(payload), "-InstallDir", str(app_base_dir())],
                creationflags=creationflags, close_fds=True,
            )
            if process is None:
                raise RuntimeError("updater process was not created")
            log_info("update", "UPDATE WORKER LAUNCH")
            self.splash.showMessage(
                "Update wird installiert. Das Programm startet gleich neu...",
                Qt.AlignBottom | Qt.AlignHCenter,
                QColor(220, 210, 185),
            )
            QTimer.singleShot(500, self._quit_for_update)
        except Exception as exc:
            log_warning("update", f"updater launch failed: {exc}")
            self._start_window()

    def _quit_for_update(self):
        self._wait_for_workers()
        log_info("update", "UPDATE APP SHUTDOWN")
        self.app.quit()

    def _start_window(self):
        self.splash.showMessage("Wird geladen...", Qt.AlignBottom | Qt.AlignHCenter, QColor(220, 210, 185))
        try:
            self.window = MainWindow()
            if browser_preload_enabled(self.window):
                QTimer.singleShot(0, lambda: initialize_hidden_browser_then_show(self.window, self.splash))
            else:
                QTimer.singleShot(0, lambda: show_main_window(self.window, self.splash))
        except Exception as exc:
            log_warning("startup", f"window initialization failed: {exc}")
            raise


if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = create_startup_splash()
    splash.show()
    app.processEvents()
    controller = StartupController(app, splash)
    QTimer.singleShot(0, controller.start)
    sys.exit(app.exec())
