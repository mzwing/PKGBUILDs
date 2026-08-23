"""Check every package's invariants: syntax, formatting, naming, config, .SRCINFO."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.common.pkgbuild import read_array, read_assignment
from tools.common.pkgbuild_eval import read_variables
from tools.packages import Package, discover_packages
from tools.paths import repository_root
from tools.reporting import LOGGER, PackageReport
from tools.templates import PACKAGE_GITIGNORE
from tools.updaters import Updater, get_updater
from tools.updaters.declarative import DeclarativeUpdater

SHFMT_ARGS = ["-i", "4"]
_PKGBASE = re.compile(r"^pkgbase = (.+)$", flags=re.MULTILINE)


@dataclass(frozen=True)
class Tools:
    """External programs verify uses, resolved once and passed in explicitly.

    Which checks can run depends on what is installed, so the lookup is a value
    rather than a hidden call: tests can then pin it instead of behaving
    differently on a machine that happens to have pacman.
    """

    makepkg: str | None
    shfmt: str | None

    @classmethod
    def discover(cls) -> Tools:
        return cls(makepkg=shutil.which("makepkg"), shfmt=shutil.which("shfmt"))


def verify(
    repository_root: Path,
    *,
    require_makepkg: bool,
    tools: Tools | None = None,
) -> PackageReport:
    packages = discover_packages(repository_root)
    if not packages:
        raise RuntimeError("no packages discovered (expected */update.toml)")

    tools = tools if tools is not None else Tools.discover()
    if require_makepkg and tools.makepkg is None:
        raise RuntimeError("makepkg is required but was not found")
    if tools.makepkg is None:
        LOGGER.warning("makepkg not found; skipping .SRCINFO regeneration check")
    if tools.shfmt is None:
        LOGGER.warning("shfmt not found; skipping PKGBUILD formatting check")

    report = PackageReport("verify")
    for name, package in packages.items():
        with report.package(name):
            _check_syntax(package)
            _check_formatting(package, tools.shfmt)
            _check_pkgname(package)
            _check_pkgbase(package)
            _check_gitignore(package)
            updater, config = _check_update_config(package)
            _check_source_drift(package, updater, config)
            _check_srcinfo(package, tools.makepkg)
    return report


def _check_syntax(package: Package) -> None:
    result = _run(["bash", "-n", str(package.pkgbuild)])
    if result.returncode != 0:
        raise ValueError(f"invalid PKGBUILD: {result.stderr.strip()}")


def _check_formatting(package: Package, shfmt: str | None) -> None:
    if shfmt is None:
        return
    result = _run([shfmt, *SHFMT_ARGS, "-d", str(package.pkgbuild)])
    if result.returncode != 0 or result.stdout.strip():
        detail = result.stdout.strip() or result.stderr.strip()
        raise ValueError(f"PKGBUILD is not shfmt-formatted:\n{detail}")


def _check_pkgname(package: Package) -> None:
    """The AUR push derives the repository name from the directory name."""
    names = read_variables(package.pkgbuild, ["pkgname"]).get("pkgname", [])
    if names != [package.name]:
        raise ValueError(
            f"pkgname is {names} but the directory is {package.name!r}; "
            "they must match for the AUR push to target the right repository"
        )


def _check_pkgbase(package: Package) -> None:
    match = _PKGBASE.search(package.srcinfo.read_text())
    if match is None:
        raise ValueError(".SRCINFO has no pkgbase line")
    if match.group(1).strip() != package.name:
        raise ValueError(
            f".SRCINFO pkgbase is {match.group(1).strip()!r}, expected {package.name!r}"
        )


def _check_gitignore(package: Package) -> None:
    path = package.directory / ".gitignore"
    if not path.exists():
        raise ValueError(".gitignore is missing")
    if path.read_text() != PACKAGE_GITIGNORE:
        raise ValueError(".gitignore does not match tools/templates.py")


def _check_update_config(package: Package) -> tuple[Updater[Any], Any]:
    updater = get_updater(package.updater_name)
    return updater, updater.parse_config(package.name, package.update)


def _check_source_drift(package: Package, updater: Updater[Any], config: Any) -> None:
    """A hand-edited source array would be silently reverted by the next update."""
    if not isinstance(updater, DeclarativeUpdater):
        return
    text = package.pkgbuild.read_text()
    version = read_assignment(text, config.version.variable)
    for field, expected in updater.static_source_entries(config, version).items():
        actual = read_array(text, field)
        if actual != expected:
            raise ValueError(
                f"{field} in PKGBUILD does not match update.toml:\n"
                f"  PKGBUILD:    {actual}\n"
                f"  update.toml: {expected}"
            )


def _check_srcinfo(package: Package, makepkg: str | None) -> None:
    if makepkg is None:
        return
    result = _run([makepkg, "--printsrcinfo"], cwd=package.directory)
    if result.returncode != 0:
        raise RuntimeError(f"makepkg --printsrcinfo failed: {result.stderr.strip()}")
    if package.srcinfo.read_text() != result.stdout:
        raise ValueError(".SRCINFO is not generated from PKGBUILD")


def _run(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--require-makepkg", action="store_true")


def run(args: argparse.Namespace) -> int:
    report = verify(repository_root(), require_makepkg=args.require_makepkg)
    report.raise_if_failed()
    LOGGER.info("all packages verified")
    return 0
