from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from tools import check_version
from tools.packages import Package
from tools.updaters.apt import (
    PackageRecord,
    compare_debian_versions,
    decode_metadata,
    parse_packages,
    select_latest_record,
    select_record_by_version,
    update_pkgbuild_text,
)

REPO_ROOT = "https://pro-store-packages.uniontech.com/appstore/"


class AptUpdaterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.records = parse_packages(
            """Package: deepin-wine10-stable
Version: 10.14deepin7
Architecture: amd64
Filename: pool/appstore/d/deepin-wine10-stable/deepin-wine10-stable_10.14deepin7_amd64.deb
SHA256: oldsha

Package: deepin-wine10-stable
Version: 10.14deepin8-1
Architecture: amd64
Filename: pool/appstore/d/deepin-wine10-stable/deepin-wine10-stable_10.14deepin8-1_amd64.deb
SHA256: newsha
"""
        )

    def test_selects_latest_and_exact_records(self) -> None:
        latest = select_latest_record(self.records, "deepin-wine10-stable", "amd64")
        exact = select_record_by_version(
            self.records,
            "deepin-wine10-stable",
            "amd64",
            "10.14deepin7",
        )
        self.assertEqual(latest.version, "10.14deepin8-1")
        self.assertEqual(exact.version, "10.14deepin7")

    def test_exact_version_must_exist(self) -> None:
        with self.assertRaises(ValueError):
            select_record_by_version(
                self.records,
                "deepin-wine10-stable",
                "amd64",
                "10.99",
            )

    def test_decodes_invalid_utf8(self) -> None:
        decoded = decode_metadata(b"Package: test\nDescription: bad \xed\n")
        self.assertIn("Package: test", decoded)

    def test_compares_debian_versions(self) -> None:
        self.assertLess(compare_debian_versions("1.0~beta", "1.0"), 0)
        self.assertGreater(compare_debian_versions("2:1.0", "1:9.9"), 0)
        self.assertGreater(compare_debian_versions("1.0-2", "1.0-1"), 0)

    def test_updates_only_apt_pkgbuild_fields(self) -> None:
        record = PackageRecord(
            package="deepin-wine10-stable",
            version="10.14deepin8-1",
            architecture="amd64",
            filename="pool/appstore/d/deepin-wine10-stable/deepin-wine10-stable_10.14deepin8-1_amd64.deb",
            sha256="newsha",
        )
        original = """pkgname='deepin-wine10-stable'
_pkgver=10.14deepin7
pkgver=${_pkgver//-/_}
pkgrel=2
source=(
    "https://example.invalid/deepin-wine10-stable_${_pkgver}_amd64.deb"
)
noextract=(
    "deepin-wine10-stable_${_pkgver}_amd64.deb"
)
sha256sums=('oldsha')
"""
        updated = update_pkgbuild_text(original, record, REPO_ROOT, "_pkgver")
        self.assertIn("_pkgver=10.14deepin8-1", updated)
        self.assertIn("pkgrel=1", updated)
        self.assertIn(record.sha256, updated)
        self.assertIn("pool/appstore/d/deepin-wine10-stable", updated)

    def test_checker_stdout_is_only_version(self) -> None:
        fake = Package(
            name="deepin-wine10-stable",
            directory=Path("deepin-wine10-stable"),
            check={},
            update={},
        )
        output = io.StringIO()
        with (
            mock.patch.object(
                check_version,
                "discover_packages",
                return_value={"deepin-wine10-stable": fake},
            ),
            mock.patch.object(
                check_version.apt, "latest_version", return_value="10.14deepin8"
            ),
            contextlib.redirect_stdout(output),
        ):
            result = check_version.main(["deepin-wine10-stable"])
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "10.14deepin8\n")


if __name__ == "__main__":
    unittest.main()
