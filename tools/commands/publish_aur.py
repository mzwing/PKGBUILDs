"""Push updated packages to their AUR repositories.

Lives here rather than inline in the workflow so it can be linted, unit tested,
and rehearsed locally with --dry-run.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from tools.packages import Package, discover_packages
from tools.paths import repository_root
from tools.reporting import LOGGER, PackageReport
from tools.templates import AUR_GITIGNORE

AUR_REMOTE = "ssh://aur@aur.archlinux.org"
PUBLISHED_FILES = ("PKGBUILD", ".SRCINFO")


def publish(
    names: list[str],
    packages: dict[str, Package],
    *,
    work_dir: Path,
    dry_run: bool = False,
) -> PackageReport:
    report = PackageReport("publish to AUR")
    for name in names:
        with report.package(name):
            _publish_one(packages[name], work_dir / f"aur-{name}", dry_run=dry_run)
    return report


def _publish_one(package: Package, checkout: Path, *, dry_run: bool) -> None:
    version = srcinfo_version(package.srcinfo.read_text())
    if checkout.exists():
        shutil.rmtree(checkout)
    _git(["clone", f"{AUR_REMOTE}/{package.name}.git", str(checkout)])

    for filename in PUBLISHED_FILES:
        shutil.copyfile(package.directory / filename, checkout / filename)
    (checkout / ".gitignore").write_text(AUR_GITIGNORE)

    _git(["-C", str(checkout), "add", *PUBLISHED_FILES, ".gitignore"])
    staged = _git(
        ["-C", str(checkout), "diff", "--cached", "--quiet"], check=False
    ).returncode
    if staged == 0:
        LOGGER.info("%s: AUR is already up to date", package.name)
        return

    message = f"{package.name}: update to {version}"
    if dry_run:
        LOGGER.info("%s: would commit and push %r", package.name, message)
        return
    _git(["-C", str(checkout), "commit", "-m", message])
    _git(["-C", str(checkout), "push", "origin", "master"])
    LOGGER.info("%s: pushed %s", package.name, version)


def srcinfo_version(text: str) -> str:
    """Return the full `[epoch:]pkgver-pkgrel` recorded in a .SRCINFO."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.strip().partition(" = ")
        if separator and key not in fields:
            fields[key] = value.strip()
    missing = [key for key in ("pkgver", "pkgrel") if key not in fields]
    if missing:
        raise ValueError(f".SRCINFO is missing {', '.join(missing)}")
    version = f"{fields['pkgver']}-{fields['pkgrel']}"
    return f"{fields['epoch']}:{version}" if "epoch" in fields else version


def _git(
    arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments], text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(arguments)} failed: {detail}")
    return result


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--packages-file", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")


def run(args: argparse.Namespace) -> int:
    names = [
        line.strip()
        for line in args.packages_file.read_text().splitlines()
        if line.strip()
    ]
    args.work_dir.mkdir(parents=True, exist_ok=True)
    report = publish(
        names,
        discover_packages(repository_root()),
        work_dir=args.work_dir,
        dry_run=args.dry_run,
    )
    report.raise_if_failed()
    return 0
