from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest import mock

from tools.commands import check_version
from tools.debian.control import (
    PackageRecord,
    decode_metadata,
    parse_packages,
    select_latest_record,
    select_record_by_version,
)
from tools.debian.repository import parse_release_packages_paths
from tools.debian.version import compare_debian_versions
from tools.packages import Package
from tools.updaters.apt import AptUpdater, update_pkgbuild_text
from tools.updaters.vcs import VcsConfig, VcsUpdater

REPO_ROOT = "https://pro-store-packages.uniontech.com/appstore/"


class DebianControlTest(unittest.TestCase):
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
            self.records, "deepin-wine10-stable", "amd64", "10.14deepin7"
        )
        self.assertEqual(latest.version, "10.14deepin8-1")
        self.assertEqual(exact.version, "10.14deepin7")

    def test_exact_version_must_exist(self) -> None:
        with self.assertRaises(ValueError):
            select_record_by_version(
                self.records, "deepin-wine10-stable", "amd64", "10.99"
            )

    def test_decodes_invalid_utf8(self) -> None:
        decoded = decode_metadata(b"Package: test\nDescription: bad \xed\n")
        self.assertIn("Package: test", decoded)


class DebianVersionTest(unittest.TestCase):
    def test_compares_debian_versions(self) -> None:
        self.assertLess(compare_debian_versions("1.0~beta", "1.0"), 0)
        self.assertGreater(compare_debian_versions("2:1.0", "1:9.9"), 0)
        self.assertGreater(compare_debian_versions("1.0-2", "1.0-1"), 0)
        self.assertEqual(compare_debian_versions("1.0", "1.0"), 0)
        self.assertGreater(compare_debian_versions("1.10", "1.9"), 0)


class ReleaseIndexTest(unittest.TestCase):
    def test_prefers_the_requested_component_and_architecture(self) -> None:
        release = """SHA256:
 abc 10 appstore/binary-amd64/Packages
 def 20 appstore/binary-amd64/Packages.gz
 ghi 30 appstore/binary-arm64/Packages.gz
Other:
 jkl 40 appstore/binary-amd64/Packages.xz
"""
        self.assertEqual(
            parse_release_packages_paths(release, "appstore", "amd64"),
            ["appstore/binary-amd64/Packages", "appstore/binary-amd64/Packages.gz"],
        )


class AptUpdaterTest(unittest.TestCase):
    def test_updates_only_apt_pkgbuild_fields(self) -> None:
        record = PackageRecord(
            package="deepin-wine10-stable",
            version="10.14deepin8-1",
            architecture="amd64",
            filename=(
                "pool/appstore/d/deepin-wine10-stable/"
                "deepin-wine10-stable_10.14deepin8-1_amd64.deb"
            ),
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

    def test_config_requires_every_repository_field(self) -> None:
        with self.assertRaisesRegex(ValueError, r"deepin:.*distribution"):
            AptUpdater().parse_config(
                "deepin", {"repo_root": REPO_ROOT, "package": "x", "variable": "_v"}
            )


class CheckVersionTest(unittest.TestCase):
    def test_stdout_is_only_the_version(self) -> None:
        package = Package(
            name="deepin-wine10-stable",
            directory=Path("deepin-wine10-stable"),
            check={},
            updater_name="apt",
            update={},
        )
        updater = mock.Mock()
        updater.parse_config.return_value = object()
        updater.latest_version.return_value = "10.14deepin8"
        output = io.StringIO()
        with (
            mock.patch.object(
                check_version,
                "discover_packages",
                return_value={"deepin-wine10-stable": package},
            ),
            mock.patch.object(check_version, "get_updater", return_value=updater),
            contextlib.redirect_stdout(output),
        ):
            version = check_version.package_version(Path("."), "deepin-wine10-stable")
            print(version)
        self.assertEqual(output.getvalue(), "10.14deepin8\n")

    def test_unknown_package_is_reported(self) -> None:
        with (
            mock.patch.object(check_version, "discover_packages", return_value={}),
            self.assertRaisesRegex(ValueError, "unknown package"),
        ):
            check_version.package_version(Path("."), "nope")

    def test_non_apt_updaters_defer_to_nvchecker(self) -> None:
        with self.assertRaises(NotImplementedError):
            VcsUpdater().latest_version(VcsConfig())


if __name__ == "__main__":
    unittest.main()
