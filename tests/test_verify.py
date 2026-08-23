from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.commands.verify import verify
from tools.templates import PACKAGE_GITIGNORE

PKGBUILD = """pkgname=example
_pkgver=1.0
pkgver=$_pkgver
pkgrel=1
arch=('x86_64')
url='https://example.invalid/example'
source=("example-$_pkgver.tar.gz::$url/v$_pkgver.tar.gz")
sha256sums=('abc')
"""

SRCINFO = """pkgbase = example
\tpkgver = 1.0
\tpkgrel = 1
\tsource = example-1.0.tar.gz::https://example.invalid/example/v1.0.tar.gz
\tsha256sums = abc

pkgname = example
"""

UPDATE_TOML = """[check]
source = "github"
github = "someone/example"

[update]
updater = "declarative"

[update.version]
variable = "_pkgver"
transform = "identity"

[[update.assets]]
kind = "url"
source_entry = "example-$_pkgver.tar.gz::$url/v$_pkgver.tar.gz"
"""


class VerifyTest(unittest.TestCase):
    def test_accepts_a_consistent_package(self) -> None:
        with self._package() as root:
            self.assertEqual(verify(root, require_makepkg=False).failures, [])

    def test_detects_a_hand_edited_source_array(self) -> None:
        with self._package() as root:
            pkgbuild = root / "example" / "PKGBUILD"
            pkgbuild.write_text(
                pkgbuild.read_text().replace(
                    'source=("example-$_pkgver.tar.gz::$url/v$_pkgver.tar.gz")',
                    'source=("example-$_pkgver.tar.gz::$url/hand-edited.tar.gz")',
                )
            )
            failures = verify(root, require_makepkg=False).failures
            self.assertEqual(len(failures), 1)
            self.assertIn("source in PKGBUILD does not match", failures[0].detail)

    def test_detects_pkgname_directory_mismatch(self) -> None:
        with self._package() as root:
            pkgbuild = root / "example" / "PKGBUILD"
            pkgbuild.write_text(
                pkgbuild.read_text().replace("pkgname=example", "pkgname=renamed")
            )
            failures = verify(root, require_makepkg=False).failures
            self.assertEqual(len(failures), 1)
            self.assertIn("pkgname is ['renamed']", failures[0].detail)

    def test_detects_a_wrong_gitignore(self) -> None:
        with self._package() as root:
            (root / "example" / ".gitignore").write_text("*\n")
            failures = verify(root, require_makepkg=False).failures
            self.assertEqual(len(failures), 1)
            self.assertIn(".gitignore", failures[0].detail)

    def test_detects_an_invalid_update_toml(self) -> None:
        with self._package() as root:
            path = root / "example" / "update.toml"
            path.write_text(path.read_text() + 'nonsense = "x"\n')
            failures = verify(root, require_makepkg=False).failures
            self.assertEqual(len(failures), 1)
            self.assertIn("nonsense", failures[0].detail)

    def test_rejects_an_empty_repository(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(RuntimeError, "no packages discovered"),
        ):
            verify(Path(temporary), require_makepkg=False)

    class _Package:
        def __init__(self) -> None:
            self._temporary = tempfile.TemporaryDirectory()

        def __enter__(self) -> Path:
            root = Path(self._temporary.name)
            directory = root / "example"
            directory.mkdir()
            (directory / "PKGBUILD").write_text(PKGBUILD)
            (directory / ".SRCINFO").write_text(SRCINFO)
            (directory / ".gitignore").write_text(PACKAGE_GITIGNORE)
            (directory / "update.toml").write_text(UPDATE_TOML)
            return root

        def __exit__(self, *exc_info: object) -> None:
            self._temporary.cleanup()

    def _package(self) -> _Package:
        return self._Package()


if __name__ == "__main__":
    unittest.main()
