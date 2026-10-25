import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = Path(__file__).with_name("startup_window_scenario.py")


class StartupWindowLifecycleTests(unittest.TestCase):
    def run_scenario(self, name):
        environment = os.environ.copy()
        environment["QT_QPA_PLATFORM"] = "offscreen"
        environment["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        completed = subprocess.run(
            [sys.executable, str(SCENARIO), name],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn("QThread: Destroyed while thread", completed.stdout + completed.stderr)
        line = next(
            line for line in completed.stdout.splitlines() if line.startswith("EVENTS_JSON=")
        )
        return json.loads(line.removeprefix("EVENTS_JSON="))

    def assert_order(self, events, *expected):
        positions = [events.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions), events)

    def test_last_window_autoquit_is_reproduced_and_guarded(self):
        before = self.run_scenario("raw_unprotected")
        self.assert_order(
            before,
            "SPLASH HIDE",
            "UPDATE DIALOG OPEN",
            "DIALOG CLOSE NO",
            "LAST WINDOW CLOSED",
            "UPDATE DIALOG RESULT NO",
            "ABOUT TO QUIT",
        )
        self.assertNotIn("EXPLICIT QUIT", before)

        after = self.run_scenario("raw_guarded")
        self.assert_order(
            after,
            "LAST WINDOW CLOSED",
            "UPDATE DIALOG RESULT NO",
            "SPLASH SHOW AFTER DIALOG",
            "EXPLICIT QUIT",
            "ABOUT TO QUIT",
        )

    def test_update_no_starts_main_window_and_keeps_app_alive(self):
        events = self.run_scenario("update_no")
        self.assertIn("APP START version=1.4.0", events)
        self.assert_order(
            events,
            "UPDATE DIALOG OPEN",
            "UPDATE DIALOG RESULT NO",
            "MAIN WINDOW CREATE",
            "MAIN WINDOW SHOW",
            "MAIN WINDOW READY",
            "ABOUT TO QUIT",
        )
        self.assertIn("quitOnLastWindowClosed=True", events)
        self.assertIn("WORKERS EMPTY", events)
        self.assertEqual(events[-2:], ["POPEN CALLS=0", "FINAL WORKERS=0"])

    def test_update_yes_prepares_and_launches_before_explicit_shutdown(self):
        events = self.run_scenario("update_yes")
        self.assert_order(
            events,
            "UPDATE DIALOG RESULT YES",
            "UPDATE PREPARE START",
            "UPDATE PAYLOAD READY",
            "UPDATE WORKER LAUNCH",
            "UPDATE APP SHUTDOWN",
            "ABOUT TO QUIT",
        )
        self.assertNotIn("MAIN WINDOW CREATE", events)
        self.assertIn("POPEN CALLS=1", events)
        self.assertIn("FINAL WORKERS=0", events)

    def test_no_update_restores_normal_main_window_autoquit(self):
        events = self.run_scenario("no_update")
        self.assert_order(
            events,
            "UPDATE CHECK FINISHED",
            "MAIN WINDOW CREATE",
            "MAIN WINDOW SHOW",
            "MAIN WINDOW READY",
            "LAST WINDOW CLOSED",
            "ABOUT TO QUIT",
        )
        self.assertIn("quitOnLastWindowClosed=True", events)
        self.assertIn("WORKERS EMPTY", events)

    def test_check_and_prepare_errors_still_start_main_window(self):
        for scenario in ("check_error", "prepare_error"):
            with self.subTest(scenario=scenario):
                events = self.run_scenario(scenario)
                self.assert_order(
                    events,
                    "MAIN WINDOW CREATE",
                    "MAIN WINDOW SHOW",
                    "MAIN WINDOW READY",
                    "ABOUT TO QUIT",
                )
                self.assertIn("quitOnLastWindowClosed=True", events)
                self.assertIn("WORKERS EMPTY", events)
                if scenario == "prepare_error":
                    self.assertIn("PREPARE ERROR DIALOG VISIBLE", events)


if __name__ == "__main__":
    unittest.main()
