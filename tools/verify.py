#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify(repository_root: Path, *, require_makepkg: bool) -> None:
    with (repository_root / "updaters.toml").open("rb") as config_file:
        packages = tomllib.load(config_file)
    if not packages:
        raise TypeError("updaters.toml must contain package tables")

    with (repository_root / "nvchecker.toml").open("rb") as config_file:
        checked = tomllib.load(config_file)
    checked = {name for name in checked if name != "__config__"}
    managed = set(packages)
    if checked != managed:
        detail = " ".join(
            [
                *sorted(f"+{name}" for name in checked - managed),
                *sorted(f"-{name}" for name in managed - checked),
            ]
        )
        raise ValueError(f"nvchecker.toml and updaters.toml disagree: {detail}")

    makepkg = shutil.which("makepkg")
    if require_makepkg and makepkg is None:
        raise RuntimeError("makepkg is required but was not found")

    for name, package in packages.items():
        if not isinstance(package, dict):
            raise TypeError(f"{name}: invalid package configuration")
        directory = package.get("directory", name)
        if not isinstance(directory, str):
            raise TypeError(f"{name}: package directory is not configured")
        package_dir = repository_root / directory
        pkgbuild = package_dir / "PKGBUILD"
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
            cwd=package_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if generated.returncode != 0:
            raise RuntimeError(
                f"{name}: makepkg --printsrcinfo failed: {generated.stderr.strip()}"
            )
        current = (package_dir / ".SRCINFO").read_text()
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
