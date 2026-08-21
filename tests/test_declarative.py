from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.updaters.declarative import apply_update


class DeclarativeUpdaterTest(unittest.TestCase):
    def test_updates_json_asset_version_url_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "spark"
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
                "directory": "spark",
                "version": {
                    "variable": "_pkgver",
                    "transform": "hyphen_to_underscore",
                },
                "assets": [
                    {
                        "kind": "json_asset",
                        "index_url": "https://api.invalid/releases",
                        "asset_name": "spark-store-console_{version}_all.deb",
                        "source_field": "source_x86_64",
                        "checksum_field": "sha256sums_x86_64",
                        "source_value": "{filename}::{url}",
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

    def test_template_assets_cover_all_serenity_architectures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "serenity"
            package_dir.mkdir()
            fields = [
                "source",
                "source_i686",
                "source_x86_64",
                "source_aarch64",
                "source_armv7h",
            ]
            checksums = [field.replace("source", "sha256sums") for field in fields]
            lines = ["_pkgver='1.0-beta.1'", "pkgver=${_pkgver//-/}", "pkgrel=2"]
            lines.extend(f'{field}=("old")' for field in fields)
            lines.extend(f"{field}=('old')" for field in checksums)
            (package_dir / "PKGBUILD").write_text("\n".join(lines) + "\n")
            assets = []
            for field, checksum in zip(fields, checksums, strict=True):
                assets.append(
                    {
                        "kind": "template",
                        "download_url": f"https://download.invalid/{field}/{{version}}",
                        "source_value": f"{field}::$url/v$_pkgver/{field}",
                        "source_field": field,
                        "checksum_field": checksum,
                    }
                )
            config = {
                "directory": "serenity",
                "version": {"variable": "_pkgver", "transform": "remove_hyphen"},
                "assets": assets,
            }

            apply_update(
                "serenity-bin",
                config,
                "1.0-beta.1",
                "1.1.0-beta.3",
                root,
                hash_url_fn=lambda url: f"hash-{url.split('/')[-2]}",
            )

            updated = (package_dir / "PKGBUILD").read_text()
            self.assertIn("_pkgver=1.1.0-beta.3", updated)
            self.assertIn("pkgver=${_pkgver//-/}", updated)
            for field in fields:
                self.assertIn(f"{field}::$url/v$_pkgver/{field}", updated)
                self.assertIn(f"hash-{field}", updated)


if __name__ == "__main__":
    unittest.main()
