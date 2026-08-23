from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.commands.verify import Tools, verify
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
    """Every case pins Tools so the result does not depend on what is installed."""

    def test_accepts_a_consistent_package(self) -> None:
        with self._package() as root:
            self.assertEqual(self._verify(root).failures, [])

    def test_detects_a_hand_edited_source_array(self) -> None:
        with self._package() as root:
            self._edit(
                root,
                '$url/v$_pkgver.tar.gz")',
                '$url/hand-edited.tar.gz")',
            )
            self.assertIn("source in PKGBUILD does not match", self._one_failure(root))

    def test_detects_pkgname_directory_mismatch(self) -> None:
        with self._package() as root:
            self._edit(root, "pkgname=example", "pkgname=renamed")
            self.assertIn("pkgname is ['renamed']", self._one_failure(root))

    def test_detects_a_wrong_gitignore(self) -> None:
        with self._package() as root:
            (root / "example" / ".gitignore").write_text("*\n")
            self.assertIn(".gitignore", self._one_failure(root))

    def test_detects_an_invalid_update_toml(self) -> None:
        with self._package() as root:
            path = root / "example" / "update.toml"
            path.write_text(path.read_text() + 'nonsense = "x"\n')
            self.assertIn("nonsense", self._one_failure(root))

    def test_accepts_srcinfo_that_matches_makepkg(self) -> None:
        with self._package() as root:
            report = verify(
                root,
                require_makepkg=True,
                tools=self._tools(root, makepkg_output=SRCINFO),
            )
            self.assertEqual(report.failures, [])

    def test_detects_srcinfo_out_of_sync_with_pkgbuild(self) -> None:
        with self._package() as root:
            report = verify(
                root,
                require_makepkg=True,
                tools=self._tools(
                    root, makepkg_output=SRCINFO.replace("pkgver = 1.0", "pkgver = 9.9")
                ),
            )
            self.assertEqual(len(report.failures), 1)
            self.assertIn(
                ".SRCINFO is not generated from PKGBUILD", report.failures[0].detail
            )

    def test_require_makepkg_without_makepkg_is_an_error(self) -> None:
        with (
            self._package() as root,
            self.assertRaisesRegex(RuntimeError, "makepkg is required"),
        ):
            verify(root, require_makepkg=True, tools=Tools(None, None))

    def test_rejects_an_empty_repository(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(RuntimeError, "no packages discovered"),
        ):
            verify(Path(temporary), require_makepkg=False)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _tools(root: Path, *, makepkg_output: str | None = None) -> Tools:
        """Pin makepkg to a stub that prints known output, or to nothing at all."""
        makepkg = None
        if makepkg_output is not None:
            stub = root / "fake-makepkg"
            stub.write_text(
                f"#!/bin/sh\ncat <<'PKGTOOL_EOF'\n{makepkg_output}PKGTOOL_EOF\n"
            )
            stub.chmod(0o755)
            makepkg = str(stub)
        return Tools(makepkg=makepkg, shfmt=shutil.which("shfmt"))

    def _verify(self, root: Path):
        return verify(root, require_makepkg=False, tools=self._tools(root))

    def _one_failure(self, root: Path) -> str:
        failures = self._verify(root).failures
        self.assertEqual(len(failures), 1)
        return failures[0].detail

    @staticmethod
    def _edit(root: Path, old: str, new: str) -> None:
        pkgbuild = root / "example" / "PKGBUILD"
        text = pkgbuild.read_text()
        assert old in text, f"fixture no longer contains {old!r}"
        pkgbuild.write_text(text.replace(old, new))

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
