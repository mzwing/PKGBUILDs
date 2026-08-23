from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.packages import discover_packages

VALID = """[check]
source = "github"
github = "so1ve/xwayclip"

[update]
updater = "vcs"
"""


def write_package(root: Path, name: str, update_toml: str) -> Path:
    directory = root / name
    directory.mkdir()
    (directory / "update.toml").write_text(update_toml)
    return directory


class DiscoverPackagesTest(unittest.TestCase):
    def test_finds_update_toml_dirs_and_ignores_others(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "xwayclip", VALID)
            (root / "plain-dir").mkdir()

            packages = discover_packages(root)

            self.assertEqual(list(packages), ["xwayclip"])
            package = packages["xwayclip"]
            self.assertEqual(package.updater_name, "vcs")
            self.assertEqual(package.update, {})
            self.assertEqual(package.check["github"], "so1ve/xwayclip")
            self.assertEqual(package.pkgbuild, root / "xwayclip" / "PKGBUILD")
            self.assertEqual(package.srcinfo, root / "xwayclip" / ".SRCINFO")

    def test_reports_package_name_for_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "broken", '[update]\nupdater = "vcs"\n')
            with self.assertRaisesRegex(ValueError, r"broken:.*\[check\]"):
                discover_packages(root)

    def test_rejects_missing_updater(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "broken", "[check]\nsource = 'git'\n\n[update]\n")
            with self.assertRaisesRegex(ValueError, r"broken:.*updater"):
                discover_packages(root)

    def test_rejects_unknown_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_package(root, "broken", f"{VALID}\n[extra]\nkey = 1\n")
            with self.assertRaisesRegex(ValueError, r"broken:.*extra"):
                discover_packages(root)


if __name__ == "__main__":
    unittest.main()
