from __future__ import annotations

import unittest

from tools.commands.publish_aur import srcinfo_version
from tools.templates import AUR_GITIGNORE, PACKAGE_GITIGNORE


class SrcinfoVersionTest(unittest.TestCase):
    def test_combines_pkgver_and_pkgrel(self) -> None:
        self.assertEqual(
            srcinfo_version("pkgbase = x\n\tpkgver = 1.2.3\n\tpkgrel = 4\n"),
            "1.2.3-4",
        )

    def test_includes_epoch_when_present(self) -> None:
        self.assertEqual(
            srcinfo_version(
                "pkgbase = x\n\tpkgver = 1.2.3\n\tpkgrel = 4\n\tepoch = 2\n"
            ),
            "2:1.2.3-4",
        )

    def test_ignores_repeated_fields_from_split_packages(self) -> None:
        text = (
            "pkgbase = x\n\tpkgver = 1.0\n\tpkgrel = 1\n\npkgname = x\n\tpkgrel = 9\n"
        )
        self.assertEqual(srcinfo_version(text), "1.0-1")

    def test_reports_a_truncated_srcinfo(self) -> None:
        with self.assertRaisesRegex(ValueError, "pkgrel"):
            srcinfo_version("pkgbase = x\n\tpkgver = 1.0\n")


class GitignoreTemplateTest(unittest.TestCase):
    def test_aur_copy_omits_update_toml(self) -> None:
        self.assertIn("!update.toml", PACKAGE_GITIGNORE)
        self.assertNotIn("update.toml", AUR_GITIGNORE)
        self.assertIn("!PKGBUILD", AUR_GITIGNORE)
        self.assertIn("!.SRCINFO", AUR_GITIGNORE)


if __name__ == "__main__":
    unittest.main()
