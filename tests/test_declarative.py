from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.updaters.base import UpdateContext
from tools.updaters.declarative import DeclarativeUpdater


def context(directory: Path, name: str, oldver: str | None, newver: str):
    return UpdateContext(name=name, directory=directory, oldver=oldver, newver=newver)


class DeclarativeUpdaterTest(unittest.TestCase):
    def test_release_asset_hashes_the_url_it_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "spark-store-console-bin"
            package_dir.mkdir()
            (package_dir / "PKGBUILD").write_text(
                """_pkgver=4.8.1
pkgver=${_pkgver//-/_}
pkgrel=7
source=("old::https://old.invalid")
sha256sums=('oldsum')
"""
            )
            raw = {
                "version": {
                    "variable": "_pkgver",
                    "transform": "hyphen_to_underscore",
                },
                "assets": [
                    {
                        "kind": "release_asset",
                        "index_url": "https://api.invalid/releases",
                        "asset_name": "spark-store-console_{version}_all.deb",
                        "source_entry": (
                            "spark-store-console_${_pkgver}_all.deb::{url}"
                        ),
                    }
                ],
            }
            releases = [
                {
                    "assets": [
                        {
                            "name": "spark-store-console_4.8.1-console2_all.deb",
                            "browser_download_url": (
                                "https://download.invalid/console2.deb"
                            ),
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
            hashed: list[str] = []

            def fake_hash(url: str) -> str:
                hashed.append(url)
                return f"hash-{url.rsplit('/', 1)[-1]}"

            updater = DeclarativeUpdater(
                fetch_json_fn=lambda _url: releases, hash_url_fn=fake_hash
            )
            config = updater.parse_config("spark-store-console-bin", raw)
            updater.apply(
                context(
                    package_dir, "spark-store-console-bin", "4.8.1", "4.8.1-console2"
                ),
                config,
            )

            updated = (package_dir / "PKGBUILD").read_text()
            self.assertIn("_pkgver=4.8.1-console2", updated)
            self.assertIn("pkgver=${_pkgver//-/_}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertIn(
                'source=("spark-store-console_${_pkgver}_all.deb::'
                'https://download.invalid/console2.deb")',
                updated,
            )
            self.assertIn("hash-console2.deb", updated)
            self.assertNotIn("https://older.invalid", updated)
            # The checksum describes the URL that was written, not a second one
            # configured separately.
            self.assertEqual(hashed, ["https://download.invalid/console2.deb"])

    def test_arch_expansion_covers_all_architectures(self) -> None:
        arches = ("i686", "x86_64", "aarch64", "armv7h")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "serenity-bin"
            package_dir.mkdir()
            lines = [
                "_pkgname=serenity",
                "_pkgver='1.0-beta.1'",
                "pkgver=${_pkgver//-/}",
                "pkgrel=2",
                "url='https://example.invalid/serenity'",
                'source=("old")',
                *[f'source_{arch}=("old")' for arch in arches],
                "sha256sums=('old')",
                *[f"sha256sums_{arch}=('old')" for arch in arches],
            ]
            (package_dir / "PKGBUILD").write_text("\n".join(lines) + "\n")
            raw = {
                "version": {"variable": "_pkgver", "transform": "remove_hyphen"},
                "assets": [
                    {
                        "kind": "url",
                        "source_entry": "LICENSE::$url/raw/v$_pkgver/LICENSE",
                    },
                    {
                        "kind": "url",
                        "arches": list(arches),
                        "arch_aliases": {
                            "i686": "386",
                            "x86_64": "amd64",
                            "aarch64": "arm64",
                            "armv7h": "armv7",
                        },
                        "source_entry": (
                            "${_pkgname}_{arch}.tar.zst::$url/linux_{alias}"
                        ),
                    },
                ],
            }

            updater = DeclarativeUpdater(
                hash_url_fn=lambda url: f"hash-{url.rsplit('/', 1)[-1]}"
            )
            config = updater.parse_config("serenity-bin", raw)
            updater.apply(
                context(package_dir, "serenity-bin", "1.0-beta.1", "1.1.0-beta.3"),
                config,
            )

            updated = (package_dir / "PKGBUILD").read_text()
            self.assertIn("_pkgver=1.1.0-beta.3", updated)
            self.assertIn("pkgver=${_pkgver//-/}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertIn('source=("LICENSE::$url/raw/v$_pkgver/LICENSE")', updated)
            self.assertIn('"${_pkgname}_i686.tar.zst::$url/linux_386"', updated)
            self.assertIn('"${_pkgname}_armv7h.tar.zst::$url/linux_armv7"', updated)
            # Checksums come from the shell-expanded URLs, one per architecture.
            self.assertIn("sha256sums_i686=('hash-linux_386')", updated)
            self.assertIn("sha256sums_armv7h=('hash-linux_armv7')", updated)
            self.assertIn("sha256sums=('hash-LICENSE')", updated)

    def test_static_source_entries_skips_release_assets(self) -> None:
        updater = DeclarativeUpdater()
        config = updater.parse_config(
            "mixed",
            {
                "version": {"variable": "_pkgver", "transform": "identity"},
                "assets": [
                    {"kind": "url", "source_entry": "LICENSE::$url/v$_pkgver"},
                    {
                        "kind": "release_asset",
                        "arches": ["x86_64"],
                        "index_url": "https://api.invalid",
                        "asset_name": "thing_{version}.deb",
                        "source_entry": "{filename}::{url}",
                    },
                ],
            },
        )
        self.assertEqual(
            updater.static_source_entries(config, "1.0"),
            {"source": ["LICENSE::$url/v$_pkgver"]},
        )

    def test_rejects_unknown_asset_key(self) -> None:
        updater = DeclarativeUpdater()
        with self.assertRaisesRegex(ValueError, r"pkg:.*url"):
            updater.parse_config(
                "pkg",
                {
                    "version": {"variable": "_pkgver", "transform": "identity"},
                    "assets": [
                        {
                            "kind": "url",
                            "url": "https://example.invalid/{version}",
                            "source_entry": "a::b",
                        }
                    ],
                },
            )


if __name__ == "__main__":
    unittest.main()
