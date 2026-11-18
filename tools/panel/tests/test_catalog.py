from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.panel import catalog


class CatalogTests(unittest.TestCase):
    def test_target_count_and_groups(self):
        self.assertEqual(len(catalog.TARGETS), 35)
        self.assertIn("Y1", catalog.TARGETS)
        self.assertEqual(len(catalog.UI_GROUPS["site"]), 12)
        self.assertEqual(len(catalog.UI_GROUPS["component"]), 8)
        self.assertEqual(len(catalog.UI_GROUPS["middleware"]), 6)
        self.assertEqual(len(catalog.UI_GROUPS["infra"]), 3)
        for tid, target in catalog.TARGETS.items():
            self.assertTrue(target.name, tid)
            self.assertTrue(target.build_checks or target.source_checks, tid)

    def test_lab_commands_use_up_and_down(self):
        self.assertEqual(catalog.command_for("R1", "start")[-2:], ["up", "R1"])
        self.assertEqual(catalog.command_for("R1", "stop")[-2:], ["down", "R1"])
        self.assertEqual(catalog.command_for("infra:nginx", "start")[-2:], ["up", "infra:nginx"])
        self.assertEqual(catalog.command_for("infra:nginx", "stop")[-2:], ["down", "infra:nginx"])

    def test_direct_script_commands(self):
        cmd = catalog.command_for("C3", "start")
        self.assertEqual(cmd[-1], "start")
        self.assertTrue(cmd[-2].endswith("c3_honeypot.py"))
        cmd = catalog.command_for("C2-1b", "start")
        self.assertEqual(cmd[-1], "start")
        self.assertTrue(cmd[-2].endswith("c2_sba.py"))
        cmd = catalog.command_for("C4-1", "start")
        self.assertEqual(cmd[-2:], ["start", "redis"])
        self.assertTrue(cmd[-3].endswith("c4_start.py"))

    def test_stop_all_keeps_mysql_and_redis(self):
        plan = catalog.stop_all_plan()
        for expected in ("R8", "Y1", "C5", "R13", "R12", "infra:nginx"):
            self.assertIn(expected, plan)
        self.assertNotIn("infra:mysql", plan)
        self.assertNotIn("infra:redis", plan)
        self.assertLess(plan.index("Y1"), plan.index("C4-1"))
        self.assertLess(plan.index("C5"), plan.index("C2-1a"))
        self.assertLess(plan.index("R13"), plan.index("R2"))
        self.assertEqual(plan[-1], "infra:nginx")

    def test_stop_order_filters_protected_infra(self):
        plan = catalog.stop_order(["infra:mysql", "infra:redis", "infra:nginx"])
        self.assertEqual(plan, ["infra:nginx"])

    def test_start_plan_dependencies(self):
        with patch.object(catalog.lb, "port_open", return_value=False), patch.object(
            catalog.lb, "nginx_running", return_value=False
        ):
            self.assertEqual(catalog.start_plan("C3"), ["C3"])
            self.assertEqual(catalog.start_plan("C5"), ["C2-1b", "infra:nginx", "C5"])
            self.assertEqual(
                catalog.start_plan("Y1"),
                ["infra:mysql", "C4-1", "infra:nginx", "Y1"],
            )

    def test_build_scan_covers_all_targets(self):
        result = catalog.rescan_build()
        self.assertEqual(len(result), 35)
        valid = {"ready", "partial", "unbuilt", "absent"}
        for tid, info in result.items():
            self.assertIn(info["state"], valid, tid)
            self.assertIn("checks", info, tid)
            self.assertIn("hint", info, tid)


if __name__ == "__main__":
    unittest.main()
