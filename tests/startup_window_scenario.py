"""Run isolated, real-Qt startup window lifecycle scenarios for integration tests."""

import json
import os
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen, QWidget

import main


scenario = sys.argv[1]
events = []


def record(event):
    events.append(str(event))


def finish(app):
    print("EVENTS_JSON=" + json.dumps(events), flush=True)
    app.quit()


def run_raw_lifecycle(guarded):
    app = QApplication([])
    app.setQuitOnLastWindowClosed(not guarded)
    app.lastWindowClosed.connect(lambda: record("LAST WINDOW CLOSED"))
    app.aboutToQuit.connect(lambda: record("ABOUT TO QUIT"))
    record(f"quitOnLastWindowClosed={app.quitOnLastWindowClosed()}")
    splash = QSplashScreen(QPixmap(100, 60))
    splash.show()
    app.processEvents()
    record("SPLASH SHOW")

    def close_dialog():
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                record("DIALOG CLOSE NO")
                widget.done(QMessageBox.No)
                return
        QTimer.singleShot(10, close_dialog)

    def show_dialog():
        splash.hide()
        record("SPLASH HIDE")
        QTimer.singleShot(30, close_dialog)
        record("UPDATE DIALOG OPEN")
        answer = QMessageBox.question(
            None,
            "Test update",
            "Update?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        record("UPDATE DIALOG RESULT " + ("YES" if answer == QMessageBox.Yes else "NO"))
        splash.show()
        record("SPLASH SHOW AFTER DIALOG")
        QTimer.singleShot(100, lambda: (record("EXPLICIT QUIT"), app.quit()))

    QTimer.singleShot(0, show_dialog)
    QTimer.singleShot(3000, lambda: (record("TIMEOUT"), app.quit()))
    app.exec()
    print("EVENTS_JSON=" + json.dumps(events), flush=True)


class TestWindow(QWidget):
    def ensure_visible_on_screen(self):
        pass

    def preload_browser_if_enabled(self):
        record("BROWSER PRELOAD")


def run_controller_scenario(name):
    app = QApplication([])
    main.log_info = lambda _category, message: record(message)
    main.log_warning = lambda _category, message: record("WARNING " + message)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        payload = root / "data" / "updates" / "v1.3.5" / "payload"
        payload.mkdir(parents=True)
        worker_source = root / "update_worker.ps1"
        worker_source.write_text("# test worker", encoding="utf-8")

        splash = main.create_startup_splash()
        splash.show()
        app.processEvents()

        release = {
            "version": "v1.3.5",
            "zip_url": "https://example.invalid/update.zip",
            "sha_url": "https://example.invalid/update.zip.sha256",
        }

        def check_release():
            time.sleep(0.03)
            if name == "check_error":
                raise RuntimeError("test check failure")
            if name == "no_update":
                return None
            return release

        def prepare_release(_release):
            time.sleep(0.03)
            if name == "prepare_error":
                raise RuntimeError("test prepare failure")
            record("UPDATE PAYLOAD READY")
            return payload

        controller = main.StartupController(app, splash)
        process_calls = []

        def fake_popen(*args, **kwargs):
            process_calls.append((args, kwargs))
            return object()

        def service_dialogs():
            for widget in app.topLevelWidgets():
                if not isinstance(widget, QMessageBox) or not widget.isVisible():
                    continue
                if widget.windowTitle() == "Adventure Time Tool Update":
                    choice = QMessageBox.No if name == "update_no" else QMessageBox.Yes
                    button = widget.button(choice)
                    if button is not None:
                        button.click()
                elif widget.windowTitle() == "Update fehlgeschlagen":
                    record("PREPARE ERROR DIALOG VISIBLE")
                    button = widget.button(QMessageBox.Ok)
                    if button is not None:
                        button.click()
            QTimer.singleShot(10, service_dialogs)

        def watch_main_window():
            if controller.window is not None and controller.window.isVisible() and not controller.workers:
                record("MAIN WINDOW READY")
                record(f"quitOnLastWindowClosed={app.quitOnLastWindowClosed()}")
                record("WORKERS EMPTY")
                controller.window.close()
                return
            QTimer.singleShot(10, watch_main_window)

        with ExitStack() as stack:
            stack.enter_context(patch.object(main, "MainWindow", TestWindow))
            stack.enter_context(patch.object(main, "browser_preload_enabled", return_value=False))
            stack.enter_context(patch.object(main, "ensure_runtime_defaults"))
            stack.enter_context(patch.object(main, "ensure_texturepacks_dir"))
            stack.enter_context(patch.object(main, "available_texturepacks", return_value=[]))
            stack.enter_context(patch.object(main, "check_latest_release", side_effect=check_release))
            stack.enter_context(patch.object(main, "prepare_update", side_effect=prepare_release))
            stack.enter_context(patch.object(main, "resource_path", return_value=worker_source))
            stack.enter_context(patch.object(main, "app_base_dir", return_value=root))
            stack.enter_context(patch.object(main.subprocess, "Popen", side_effect=fake_popen))
            stack.enter_context(patch.object(main.sys, "frozen", True, create=True))

            QTimer.singleShot(0, service_dialogs)
            if name != "update_yes":
                QTimer.singleShot(0, watch_main_window)
            QTimer.singleShot(0, controller.start)
            QTimer.singleShot(5000, lambda: (record("TIMEOUT"), app.quit()))
            app.exec()

        record(f"POPEN CALLS={len(process_calls)}")
        record(f"FINAL WORKERS={len(controller.workers)}")
        print("EVENTS_JSON=" + json.dumps(events), flush=True)


if scenario == "raw_unprotected":
    run_raw_lifecycle(False)
elif scenario == "raw_guarded":
    run_raw_lifecycle(True)
elif scenario in {"update_no", "update_yes", "no_update", "check_error", "prepare_error"}:
    run_controller_scenario(scenario)
else:
    raise SystemExit(f"unknown scenario: {scenario}")
