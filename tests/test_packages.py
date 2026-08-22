from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.packages import discover_packages


class DiscoverPackagesTest(unittest.TestCase):
    def test_finds_update_toml_dirs_and_ignores_others(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            managed = root / "xwayclip"
            managed.mkdir()
            (managed / "update.toml").write_text(
                """[check]
source = "github"
github = "so1ve/xwayclip"

[update]
updater = "vcs"
"""
            )
            unmanaged = root / "plain-dir"
            unmanaged.mkdir()

            packages = discover_packages(root)

            self.assertEqual(list(packages), ["xwayclip"])
            package = packages["xwayclip"]
            self.assertEqual(package.directory, managed)
            self.assertEqual(package.check["source"], "github")
            self.assertEqual(package.update["updater"], "vcs")

    def test_empty_repository_discovers_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(discover_packages(Path(temporary)), {})


if __name__ == "__main__":
    unittest.main()
