from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.commands import apply_updates
from tools.packages import Package


def make_package(name: str, root: Path) -> Package:
    return Package(
        name=name,
        directory=root / name,
        check={},
        updater_name="declarative",
        update={},
    )


class RecordingUpdater:
    """Stands in for a real updater; fails for the names it is told to fail on."""

    def __init__(self, failing: frozenset[str] = frozenset()) -> None:
        self.failing = failing
        self.calls: list[tuple[str, str | None, str]] = []

    def parse_config(self, package: str, raw: dict) -> dict:
        del package
        return dict(raw)

    def apply(self, context, config) -> None:
        del config
        if context.name in self.failing:
            raise RuntimeError("upstream is down")
        self.calls.append((context.name, context.oldver, context.newver))


class DispatcherTest(unittest.TestCase):
    def test_routes_via_registry(self) -> None:
        updates = [{"name": "example-bin", "oldver": "1.0", "newver": "2.0"}]
        updater = RecordingUpdater()
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(apply_updates, "get_updater", return_value=updater),
        ):
            root = Path(temporary)
            applied, report = apply_updates.apply_updates(
                updates, {"example-bin": make_package("example-bin", root)}
            )

        self.assertEqual(applied, ["example-bin"])
        self.assertEqual(report.failures, [])
        self.assertEqual(updater.calls, [("example-bin", "1.0", "2.0")])

    def test_one_failure_does_not_stop_the_others(self) -> None:
        updates = [
            {"name": "bad", "oldver": "1", "newver": "2"},
            {"name": "good", "oldver": "1", "newver": "2"},
        ]
        updater = RecordingUpdater(failing=frozenset({"bad"}))
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(apply_updates, "get_updater", return_value=updater),
        ):
            root = Path(temporary)
            applied, report = apply_updates.apply_updates(
                updates,
                {name: make_package(name, root) for name in ("bad", "good")},
            )

        self.assertEqual(applied, ["good"])
        self.assertEqual([failure.package for failure in report.failures], ["bad"])
        with self.assertRaisesRegex(RuntimeError, "upstream is down"):
            report.raise_if_failed()

    def test_rejects_unknown_package(self) -> None:
        updates = [{"name": "unknown", "oldver": "1", "newver": "2"}]
        with self.assertRaises(KeyError):
            apply_updates.apply_updates(updates, {})

    def test_rejects_duplicate_results(self) -> None:
        updates = [
            {"name": "example", "oldver": "1", "newver": "2"},
            {"name": "example", "oldver": "1", "newver": "2"},
        ]
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                apply_updates, "get_updater", return_value=RecordingUpdater()
            ),
            self.assertRaises(ValueError),
        ):
            root = Path(temporary)
            apply_updates.apply_updates(
                updates, {"example": make_package("example", root)}
            )

    def test_rejects_invalid_result(self) -> None:
        with self.assertRaises(ValueError):
            apply_updates.apply_updates([{"name": "", "newver": "2"}], {})


if __name__ == "__main__":
    unittest.main()
