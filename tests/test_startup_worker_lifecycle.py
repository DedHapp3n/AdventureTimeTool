import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QObject, QThread, QTimer, Signal, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import main


APP = QApplication.instance() or QApplication([])


class FakeApp(QObject):
    aboutToQuit = Signal()
    lastWindowClosed = Signal()

    def __init__(self):
        super().__init__()
        self.quit_called = False
        self.quit_on_last_window_closed = True

    def setQuitOnLastWindowClosed(self, enabled):
        self.quit_on_last_window_closed = bool(enabled)

    def quitOnLastWindowClosed(self):
        return self.quit_on_last_window_closed

    def quit(self):
        self.quit_called = True
        self.aboutToQuit.emit()


class FakeSplash:
    def __init__(self):
        self.messages = []

    def showMessage(self, *_args):
        self.messages.append(_args[0])

    def hide(self):
        pass

    def show(self):
        pass


class StartupWorkerLifecycleTests(unittest.TestCase):
    def test_check_prepare_callbacks_run_only_after_threads_stop(self):
        qt_messages = []

        def message_handler(_kind, _context, message):
            qt_messages.append(str(message))

        previous_handler = qInstallMessageHandler(message_handler)
        try:
            for iteration in range(3):
                with self.subTest(iteration=iteration):
                    fake_app = FakeApp()
                    controller = main.StartupController(fake_app, FakeSplash())
                    loop = QEventLoop()
                    timeline = []
                    destroyed = []
                    timeout = QTimer()
                    timeout.setSingleShot(True)
                    timeout.timeout.connect(loop.quit)

                    def check_operation():
                        time.sleep(0.02)
                        return {"version": "v1.3.2"}

                    def prepare_operation(release):
                        time.sleep(0.02)
                        return f"payload:{release['version']}"

                    def prepared(result, error):
                        self.assertIs(QThread.currentThread(), APP.thread())
                        worker = next(
                            item for item in controller.workers if item.operation == "prepare"
                        )
                        self.assertFalse(worker.isRunning())
                        self.assertIn(worker, controller.workers)
                        self.assertIsNone(error)
                        self.assertEqual(result, "payload:v1.3.2")
                        timeline.append("prepare_callback")
                        QTimer.singleShot(0, controller._quit_for_update)

                    def checked(result, error):
                        self.assertIs(QThread.currentThread(), APP.thread())
                        worker = next(
                            item for item in controller.workers if item.operation == "check"
                        )
                        self.assertFalse(worker.isRunning())
                        self.assertIn(worker, controller.workers)
                        self.assertIsNone(error)
                        timeline.append("check_callback")
                        next_worker = controller._work("prepare", result, prepared)
                        next_worker.destroyed.connect(
                            lambda *_args: destroyed.append("prepare")
                        )

                    fake_app.aboutToQuit.connect(loop.quit)
                    with patch.object(main, "check_latest_release", side_effect=check_operation), patch.object(
                        main, "prepare_update", side_effect=prepare_operation
                    ):
                        first_worker = controller._work("check", None, checked)
                        first_worker.destroyed.connect(
                            lambda *_args: destroyed.append("check")
                        )
                        timeout.start(5000)
                        loop.exec()

                    timeout.stop()
                    self.assertTrue(fake_app.quit_called)
                    self.assertEqual(timeline, ["check_callback", "prepare_callback"])
                    self.assertEqual(controller.workers, [])
                    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                    APP.processEvents()
                    self.assertCountEqual(destroyed, ["check", "prepare"])
        finally:
            qInstallMessageHandler(previous_handler)

        self.assertFalse(
            any("QThread: Destroyed while thread" in message for message in qt_messages),
            qt_messages,
        )

    def test_prepared_update_launches_worker_before_queued_shutdown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / "data" / "updates" / "v1.3.2" / "payload"
            payload.mkdir(parents=True)
            worker_source = root / "update_worker.ps1"
            worker_source.write_text("# test worker", encoding="utf-8")
            fake_app = FakeApp()
            splash = FakeSplash()
            controller = main.StartupController(fake_app, splash)
            queued = []
            process = object()

            with patch.object(main, "resource_path", return_value=worker_source), patch.object(
                main, "app_base_dir", return_value=root
            ), patch.object(main.subprocess, "Popen", return_value=process) as popen, patch.object(
                main.QTimer,
                "singleShot",
                side_effect=lambda delay, callback: queued.append((delay, callback)),
            ):
                controller._prepared(payload, None)

            self.assertTrue((payload.parent / "update_worker.ps1").is_file())
            self.assertEqual(popen.call_count, 1)
            self.assertIn("-Payload", popen.call_args.args[0])
            self.assertFalse(fake_app.quit_called)
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0][0], 500)
            self.assertEqual(
                splash.messages[-1],
                "Update wird installiert. Das Programm startet gleich neu...",
            )

            queued[0][1]()
            self.assertTrue(fake_app.quit_called)


if __name__ == "__main__":
    unittest.main()
