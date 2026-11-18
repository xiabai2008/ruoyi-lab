from __future__ import annotations

import unittest

from tools.panel.operations import OperationConflict, OperationManager


class _DummyPoller:
    def refresh_now(self):
        pass


class OperationConflictTests(unittest.TestCase):
    def test_same_target_is_rejected(self):
        manager = OperationManager(_DummyPoller())
        manager.submit_start("C3")
        with self.assertRaises(OperationConflict):
            manager.submit_start("C3")

    def test_c2_pair_shares_lifecycle(self):
        manager = OperationManager(_DummyPoller())
        manager.submit_start("C2-1a")
        with self.assertRaises(OperationConflict):
            manager.submit_start("C2-1b")

    def test_different_targets_are_allowed(self):
        manager = OperationManager(_DummyPoller())
        manager.submit_start("C3")
        manager.submit_start("C4-2")
        self.assertEqual(len(manager.recent()), 2)


if __name__ == "__main__":
    unittest.main()
