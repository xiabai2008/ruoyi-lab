from __future__ import annotations

import unittest

from tools.panel.status_poller import derive_display_state as derive


class DisplayStateTests(unittest.TestCase):
    def test_up_is_running(self):
        self.assertEqual(derive("R1", {"state": "UP"}, "ready", True)[0], "RUNNING")

    def test_backend_down_nginx_left_is_stopped(self):
        raw = {"state": "DEGRADED", "pid": None, "pid_alive": False, "conf_name": None, "backend_up": False}
        self.assertEqual(derive("R1", raw, "ready", True)[0], "STOPPED")

    def test_pid_alive_backend_down_is_broken(self):
        raw = {"state": "DEGRADED", "pid": 123, "pid_alive": True, "conf_name": None, "backend_up": False}
        self.assertEqual(derive("R1", raw, "ready", True)[0], "BROKEN")

    def test_probe_failure_but_backend_up_is_degraded(self):
        raw = {"state": "DEGRADED", "pid": 123, "pid_alive": True, "conf_name": None, "backend_up": True}
        self.assertEqual(derive("R1", raw, "ready", True)[0], "DEGRADED")

    def test_conf_enabled_backend_down_is_degraded(self):
        raw = {
            "state": "DEGRADED",
            "pid": None,
            "pid_alive": False,
            "conf_name": "R12",
            "conf_enabled": True,
            "backend_up": False,
        }
        self.assertEqual(derive("R12", raw, "ready", True)[0], "DEGRADED")

    def test_unbuilt_down_is_not_ready(self):
        self.assertEqual(derive("R1", {"state": "DOWN"}, "unbuilt", True)[0], "NOT_READY")

    def test_conf_enabled_entry_down_nginx_up_is_broken(self):
        raw = {"state": "DOWN", "pid": None, "pid_alive": False, "conf_name": "D1", "conf_enabled": True}
        self.assertEqual(derive("D1", raw, "ready", True)[0], "BROKEN")

    def test_conf_enabled_entry_down_nginx_down_is_stopped(self):
        raw = {"state": "DOWN", "pid": None, "pid_alive": False, "conf_name": "D1", "conf_enabled": True}
        self.assertEqual(derive("D1", raw, "ready", False)[0], "STOPPED")

    def test_y1_backend_up_conf_disabled_is_degraded(self):
        raw = {"state": "DEGRADED", "backend_up": True, "conf_enabled": False}
        self.assertEqual(derive("Y1", raw, "ready", True)[0], "DEGRADED")

    def test_y1_conf_enabled_backend_down_nginx_down_is_stopped(self):
        raw = {"state": "DOWN", "backend_up": False, "conf_enabled": True}
        self.assertEqual(derive("Y1", raw, "ready", False)[0], "STOPPED")


if __name__ == "__main__":
    unittest.main()
