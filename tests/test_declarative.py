from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.updaters.declarative import apply_update


class DeclarativeUpdaterTest(unittest.TestCase):
    def test_release_asset_targets_arch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "spark-store-console-bin"
            package_dir.mkdir()
            (package_dir / "PKGBUILD").write_text(
                """_pkgver=4.8.1
pkgver=${_pkgver//-/_}
pkgrel=7
source_x86_64=("old::https://old.invalid")
sha256sums_x86_64=('oldsum')
"""
            )
            config = {
                "version": {
                    "variable": "_pkgver",
                    "transform": "hyphen_to_underscore",
                },
                "assets": [
                    {
                        "kind": "release_asset",
                        "arches": ["x86_64"],
                        "index_url": "https://api.invalid/releases",
                        "asset_name": "spark-store-console_{version}_all.deb",
                        "source_entry": "{filename}::{url}",
                    }
                ],
            }
            releases = [
                {
                    "assets": [
                        {
                            "name": "spark-store-console_4.8.1-console2_all.deb",
                            "browser_download_url": "https://download.invalid/console2.deb",
                        }
                    ]
                },
                {
                    "assets": [
                        {
                            "name": "spark-store-console_4.8.1-console2_all.deb",
                            "browser_download_url": "https://older.invalid/console2.deb",
                        }
                    ]
                },
            ]

            apply_update(
                "spark-store-console-bin",
                config,
                "4.8.1",
                "4.8.1-console2",
                root,
                fetch_json_fn=lambda _url: releases,
                hash_url_fn=lambda url: f"hash-{url.rsplit('/', 1)[-1]}",
            )

            updated = (package_dir / "PKGBUILD").read_text()
            self.assertIn("_pkgver=4.8.1-console2", updated)
            self.assertIn("pkgver=${_pkgver//-/_}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertIn("https://download.invalid/console2.deb", updated)
            self.assertIn("hash-console2.deb", updated)
            self.assertNotIn("https://older.invalid", updated)

    def test_arch_expansion_covers_all_serenity_architectures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "serenity-bin"
            package_dir.mkdir()
            lines = [
                "_pkgver='1.0-beta.1'",
                "pkgver=${_pkgver//-/}",
                "pkgrel=2",
                'source=("old")',
                *[
                    f'source_{arch}=("old")'
                    for arch in ("i686", "x86_64", "aarch64", "armv7h")
                ],
                "sha256sums=('old')",
                *[
                    f"sha256sums_{arch}=('old')"
                    for arch in ("i686", "x86_64", "aarch64", "armv7h")
                ],
            ]
            (package_dir / "PKGBUILD").write_text("\n".join(lines) + "\n")
            config = {
                "version": {"variable": "_pkgver", "transform": "remove_hyphen"},
                "assets": [
                    {
                        "kind": "url",
                        "url": "https://download.invalid/LICENSE/{version}",
                        "source_entry": "LICENSE::$url/v$_pkgver/LICENSE",
                    },
                    {
                        "kind": "url",
                        "arches": ["i686", "x86_64", "aarch64", "armv7h"],
                        "arch_aliases": {
                            "i686": "386",
                            "x86_64": "amd64",
                            "aarch64": "arm64",
                            "armv7h": "armv7",
                        },
                        "url": "https://download.invalid/linux_{alias}",
                        "source_entry": "${_pkgname}_{arch}.tar.zst::$url/linux_{alias}",
                    },
                ],
            }

            apply_update(
                "serenity-bin",
                config,
                "1.0-beta.1",
                "1.1.0-beta.3",
                root,
                hash_url_fn=lambda url: f"hash-{url.rsplit('/', 1)[-1]}",
            )

            updated = (package_dir / "PKGBUILD").read_text()
            self.assertIn("_pkgver=1.1.0-beta.3", updated)
            self.assertIn("pkgver=${_pkgver//-/}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertIn('source=("LICENSE::$url/v$_pkgver/LICENSE")', updated)
            self.assertIn(
                '"${_pkgname}_i686.tar.zst::$url/linux_386"',
                updated,
            )
            self.assertIn(
                '"${_pkgname}_armv7h.tar.zst::$url/linux_armv7"',
                updated,
            )
            for field in ("source_i686", "sha256sums_x86_64", "sha256sums_armv7h"):
                self.assertIn(f"{field}=", updated)


if __name__ == "__main__":
    unittest.main()
