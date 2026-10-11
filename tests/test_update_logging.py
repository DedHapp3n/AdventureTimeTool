import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app_logger


class UpdateLoggingTests(unittest.TestCase):
    def close_handler(self):
        with app_logger._update_log_lock:
            if app_logger._update_log_handler is not None:
                app_logger._update_log_handler.close()
            app_logger._update_log_handler = None
            app_logger._update_log_handler_path = None

    def tearDown(self):
        self.close_handler()

    def test_update_log_is_created_appended_and_rotated(self):
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "AdventureTimeTool.exe"
            log_path = Path(temp) / "data" / "update.log"
            self.assertFalse(log_path.exists())

            with patch.object(app_logger.sys, "frozen", True, create=True), patch.object(
                app_logger.sys, "executable", str(executable)
            ), patch.object(app_logger, "UPDATE_LOG_MAX_BYTES", 512), patch.object(
                app_logger, "UPDATE_LOG_BACKUP_COUNT", 2
            ):
                app_logger.log_info("update", "first entry")
                app_logger.log_info("startup", "second entry")
                self.assertIn("first entry", log_path.read_text(encoding="utf-8"))
                self.assertIn("second entry", log_path.read_text(encoding="utf-8"))

                for index in range(30):
                    app_logger.log_info("update", f"rotation entry {index}: " + "x" * 100)

                self.assertTrue(log_path.with_name("update.log.1").is_file())
                self.assertLessEqual(
                    len(list(log_path.parent.glob("update.log.*"))),
                    app_logger.UPDATE_LOG_BACKUP_COUNT,
                )
                self.assertIn("rotation entry 29", log_path.read_text(encoding="utf-8"))
                self.close_handler()


if __name__ == "__main__":
    unittest.main()
