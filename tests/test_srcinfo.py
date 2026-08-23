from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.commands.generate_srcinfo import fallback_srcinfo, managed_pkgbuild_fields


class SrcinfoFallbackTest(unittest.TestCase):
    def test_updates_managed_fields_from_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = Path(temporary)
            (package_dir / "PKGBUILD").write_text(
                """_pkgver=2.0-beta
pkgver=${_pkgver//-/_}
pkgrel=1
arch=('x86_64')
source=("file_${_pkgver}::https://example.invalid/${_pkgver}")
sha256sums=('newsum')
"""
            )
            (package_dir / ".SRCINFO").write_text(
                """pkgbase = example
\tpkgver = 1.0
\tpkgrel = 3
\tsource = file_1.0::https://example.invalid/1.0
\tsha256sums = oldsum

pkgname = example
"""
            )

            generated = fallback_srcinfo(package_dir)

            self.assertIn("\tpkgver = 2.0_beta", generated)
            self.assertIn("\tpkgrel = 1", generated)
            self.assertIn(
                "\tsource = file_2.0-beta::https://example.invalid/2.0-beta",
                generated,
            )
            self.assertIn("\tsha256sums = newsum", generated)

    def test_refuses_to_emit_a_stale_srcinfo(self) -> None:
        """A PKGBUILD that gained an architecture cannot be patched in place."""
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = Path(temporary)
            (package_dir / "PKGBUILD").write_text(
                """_pkgver=2.0
pkgver=$_pkgver
pkgrel=1
arch=('x86_64' 'aarch64')
source=("base")
sha256sums=('a')
source_aarch64=("new-arch")
sha256sums_aarch64=('b')
"""
            )
            (package_dir / ".SRCINFO").write_text(
                """pkgbase = example
\tpkgver = 1.0
\tpkgrel = 1
\tsource = base
\tsha256sums = a

pkgname = example
"""
            )

            with self.assertRaisesRegex(ValueError, "source_aarch64"):
                fallback_srcinfo(package_dir)

    def test_managed_fields_follow_the_declared_architectures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pkgbuild = Path(temporary) / "PKGBUILD"
            pkgbuild.write_text(
                """arch=('x86_64' 'aarch64')
source=("a")
sha256sums=('b')
source_x86_64=("c")
sha256sums_x86_64=('d')
noextract=("e")
"""
            )
            self.assertEqual(
                managed_pkgbuild_fields(pkgbuild),
                [
                    "source",
                    "source_x86_64",
                    "sha256sums",
                    "sha256sums_x86_64",
                    "noextract",
                ],
            )


if __name__ == "__main__":
    unittest.main()
