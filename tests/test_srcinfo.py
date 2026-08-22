from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.generate_srcinfo import fallback_srcinfo


class SrcinfoFallbackTest(unittest.TestCase):
    def test_updates_managed_fields_from_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package_dir = Path(temporary)
            (package_dir / "PKGBUILD").write_text(
                """_pkgver=2.0-beta
pkgver=${_pkgver//-/_}
pkgrel=1
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


if __name__ == "__main__":
    unittest.main()
