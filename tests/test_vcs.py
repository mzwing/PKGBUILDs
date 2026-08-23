from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.updaters.base import UpdateContext
from tools.updaters.vcs import VcsConfig, VcsUpdater


class VcsUpdaterTest(unittest.TestCase):
    def test_uses_exact_commit_and_pkgver_function(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._upstream(root, commits=3)
            commits = [
                line
                for line in self._git(
                    upstream, "rev-list", "--reverse", "HEAD"
                ).splitlines()
                if line
            ]

            package_dir = root / "hfd-git"
            package_dir.mkdir()
            marker = root / "package-ran"
            pkgbuild_path = package_dir / "PKGBUILD"
            pkgbuild_path.write_text(f"""pkgname=hfd-git
pkgver=r1.old
pkgrel=5
url='{upstream}'
source=("$pkgname::git+$url")
sha256sums=('SKIP')

pkgver() {{
    cd "$pkgname"
    printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)"
}}

package() {{
    touch '{marker}'
}}
""")
            self._apply(package_dir, "hfd-git", commits[0], commits[1])

            updated = pkgbuild_path.read_text()
            self.assertIn(f"pkgver=r2.{commits[1][:7]}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertFalse(marker.exists())

    def test_missing_commit_does_not_write_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._upstream(root, commits=1)
            package_dir = root / "hfd-git"
            package_dir.mkdir()
            original = f"""pkgname=hfd-git
pkgver=r1.old
pkgrel=1
url='{upstream}'
source=("$pkgname::git+$url")
sha256sums=('SKIP')
pkgver() {{ cd "$pkgname"; echo r1.test; }}
"""
            pkgbuild_path = package_dir / "PKGBUILD"
            pkgbuild_path.write_text(original)
            with self.assertRaises(RuntimeError):
                self._apply(package_dir, "hfd-git", None, "0" * 40)
            self.assertEqual(pkgbuild_path.read_text(), original)

    def test_failing_pkgver_function_does_not_write_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = self._upstream(root, commits=1)
            commit = self._git(upstream, "rev-parse", "HEAD").strip()
            package_dir = root / "hfd-git"
            package_dir.mkdir()
            original = f"""pkgname=hfd-git
pkgver=r1.old
pkgrel=1
url='{upstream}'
source=("$pkgname::git+$url")
sha256sums=('SKIP')
pkgver() {{ return 1; }}
"""
            pkgbuild_path = package_dir / "PKGBUILD"
            pkgbuild_path.write_text(original)
            with self.assertRaises(RuntimeError):
                self._apply(package_dir, "hfd-git", None, commit)
            self.assertEqual(pkgbuild_path.read_text(), original)

    def test_source_must_be_named_after_the_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_dir = root / "hfd-git"
            package_dir.mkdir()
            (package_dir / "PKGBUILD").write_text(
                """pkgname=hfd-git
pkgver=r1.old
pkgrel=1
source=("other::git+https://example.invalid/repo.git")
sha256sums=('SKIP')
"""
            )
            with self.assertRaisesRegex(ValueError, "expected one source"):
                self._apply(package_dir, "hfd-git", None, "0" * 40)

    @staticmethod
    def _apply(directory: Path, name: str, oldver: str | None, newver: str) -> None:
        VcsUpdater().apply(
            UpdateContext(name=name, directory=directory, oldver=oldver, newver=newver),
            VcsConfig(),
        )

    @classmethod
    def _upstream(cls, root: Path, *, commits: int) -> Path:
        upstream = root / "upstream"
        upstream.mkdir()
        cls._git(upstream, "init")
        cls._git(upstream, "config", "user.name", "Test")
        cls._git(upstream, "config", "user.email", "test@example.invalid")
        cls._git(upstream, "config", "commit.gpgsign", "false")
        for number in range(1, commits + 1):
            (upstream / "hfd.sh").write_text(f"version {number}\n")
            cls._git(upstream, "add", "hfd.sh")
            cls._git(upstream, "commit", "-m", f"commit {number}")
        return upstream

    @staticmethod
    def _git(directory: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(directory), *args],
            text=True,
            capture_output=True,
            check=True,
        ).stdout


if __name__ == "__main__":
    unittest.main()
