#!/usr/bin/env python3
"""校验各包 PKGBUILD 语法与 .SRCINFO 同步。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.packages import discover_packages


def verify(repository_root: Path, *, require_makepkg: bool) -> None:
    packages = discover_packages(repository_root)
    if not packages:
        raise RuntimeError("no packages discovered (expected */update.toml)")

    makepkg = shutil.which("makepkg")
    if require_makepkg and makepkg is None:
        raise RuntimeError("makepkg is required but was not found")

    for name, package in packages.items():
        pkgbuild = package.directory / "PKGBUILD"
        syntax = subprocess.run(
            ["bash", "-n", str(pkgbuild)],
            text=True,
            capture_output=True,
            check=False,
        )
        if syntax.returncode != 0:
            raise RuntimeError(f"{name}: invalid PKGBUILD: {syntax.stderr.strip()}")

        if makepkg is None:
            continue
        generated = subprocess.run(
            [makepkg, "--printsrcinfo"],
            cwd=package.directory,
            text=True,
            capture_output=True,
            check=False,
        )
        if generated.returncode != 0:
            raise RuntimeError(
                f"{name}: makepkg --printsrcinfo failed: {generated.stderr.strip()}"
            )
        current = (package.directory / ".SRCINFO").read_text()
        if current != generated.stdout:
            raise ValueError(f"{name}: .SRCINFO is not generated from PKGBUILD")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify PKGBUILD and .SRCINFO files")
    parser.add_argument("--require-makepkg", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    verify(Path(__file__).resolve().parents[1], require_makepkg=args.require_makepkg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
