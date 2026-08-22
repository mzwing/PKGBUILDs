from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import apply_updates


class DispatcherTest(unittest.TestCase):
    def test_routes_via_registry(self) -> None:
        updates = [{"name": "example-bin", "oldver": "1.0", "newver": "2.0"}]
        config = {"example-bin": {"updater": "declarative"}}
        calls: list[tuple] = []

        def fake(name, package_config, oldver, newver, repository_root):
            calls.append((name, oldver, newver))

        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.dict(apply_updates.UPDATERS, {"declarative": fake}),
        ):
            applied = apply_updates.apply_updates(updates, config, Path(temporary))

        self.assertEqual(applied, ["example-bin"])
        self.assertEqual(calls, [("example-bin", "1.0", "2.0")])

    def test_rejects_unknown_package(self) -> None:
        updates = [{"name": "unknown", "oldver": "1", "newver": "2"}]
        with self.assertRaises(KeyError):
            apply_updates.apply_updates(updates, {}, Path.cwd())

    def test_rejects_duplicate_results(self) -> None:
        updates = [
            {"name": "example", "oldver": "1", "newver": "2"},
            {"name": "example", "oldver": "1", "newver": "2"},
        ]
        config = {"example": {"updater": "vcs"}}
        with (
            mock.patch.dict(apply_updates.UPDATERS, {"vcs": lambda *_args: None}),
            self.assertRaises(ValueError),
        ):
            apply_updates.apply_updates(updates, config, Path.cwd())

    def test_rejects_invalid_result(self) -> None:
        updates = [{"name": "", "newver": "2"}]
        config = {"": {"updater": "vcs"}}
        with self.assertRaises(ValueError):
            apply_updates.apply_updates(updates, config, Path.cwd())


if __name__ == "__main__":
    unittest.main()
