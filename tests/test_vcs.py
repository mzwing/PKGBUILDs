from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.updaters.vcs import apply_update


class VcsUpdaterTest(unittest.TestCase):
    def test_uses_exact_commit_and_pkgver_function(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            upstream.mkdir()
            self._git(upstream, "init")
            self._git(upstream, "config", "user.name", "Test")
            self._git(upstream, "config", "user.email", "test@example.invalid")
            self._git(upstream, "config", "commit.gpgsign", "false")
            commits = []
            for number in range(1, 4):
                (upstream / "hfd.sh").write_text(f"version {number}\n")
                self._git(upstream, "add", "hfd.sh")
                self._git(upstream, "commit", "-m", f"commit {number}")
                commits.append(self._git(upstream, "rev-parse", "HEAD").strip())

            package_dir = root / "hfd-git"
            package_dir.mkdir()
            marker = root / "package-ran"
            pkgbuild = f"""pkgname=hfd-git
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
"""
            pkgbuild_path = package_dir / "PKGBUILD"
            pkgbuild_path.write_text(pkgbuild)
            apply_update("hfd-git", {}, commits[0], commits[1], root)

            updated = pkgbuild_path.read_text()
            self.assertIn(f"pkgver=r2.{commits[1][:7]}", updated)
            self.assertIn("pkgrel=1", updated)
            self.assertFalse(marker.exists())

    def test_missing_commit_does_not_write_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            upstream.mkdir()
            self._git(upstream, "init")
            self._git(upstream, "config", "user.name", "Test")
            self._git(upstream, "config", "user.email", "test@example.invalid")
            self._git(upstream, "config", "commit.gpgsign", "false")
            (upstream / "file").write_text("one")
            self._git(upstream, "add", "file")
            self._git(upstream, "commit", "-m", "one")
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
                apply_update("hfd-git", {}, None, "0" * 40, root)
            self.assertEqual(pkgbuild_path.read_text(), original)

    def test_failing_pkgver_function_does_not_write_pkgbuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            upstream = root / "upstream"
            upstream.mkdir()
            self._git(upstream, "init")
            self._git(upstream, "config", "user.name", "Test")
            self._git(upstream, "config", "user.email", "test@example.invalid")
            self._git(upstream, "config", "commit.gpgsign", "false")
            (upstream / "file").write_text("one")
            self._git(upstream, "add", "file")
            self._git(upstream, "commit", "-m", "one")
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
                apply_update("hfd-git", {}, None, commit, root)
            self.assertEqual(pkgbuild_path.read_text(), original)

    @staticmethod
    def _git(directory: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(directory), *args],
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout


if __name__ == "__main__":
    unittest.main()
