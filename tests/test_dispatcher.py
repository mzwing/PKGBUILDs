from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import apply_updates


class DispatcherTest(unittest.TestCase):
    def test_routes_standard_nvcmp_json_without_package_logic(self) -> None:
        updates = [
            {
                "name": "example-bin",
                "oldver": "1.0",
                "newver": "2.0",
                "delta": "new",
            }
        ]
        config = {
            "example-bin": {
                "updater": "declarative",
            }
        }
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(apply_updates.declarative, "apply_update") as updater,
        ):
            applied = apply_updates.apply_updates(
                updates,
                config,
                Path(temporary),
            )
        self.assertEqual(applied, ["example-bin"])
        updater.assert_called_once()
        self.assertEqual(updater.call_args.args[2:4], ("1.0", "2.0"))

    def test_rejects_unknown_package(self) -> None:
        updates = [{"name": "unknown", "oldver": "1", "newver": "2", "delta": "new"}]
        with self.assertRaises(TypeError):
            apply_updates.apply_updates(updates, {}, Path.cwd())

    def test_rejects_non_update_delta(self) -> None:
        updates = [{"name": "example", "oldver": "1", "newver": "1", "delta": "equal"}]
        config = {"example": {"updater": "declarative"}}
        with self.assertRaises(ValueError):
            apply_updates.apply_updates(updates, config, Path.cwd())


if __name__ == "__main__":
    unittest.main()
