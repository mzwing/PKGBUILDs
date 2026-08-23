"""Apply nvcmp JSON results to each package's PKGBUILD."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.common.fsutil import write_text_atomic
from tools.packages import Package, discover_packages
from tools.paths import repository_root
from tools.reporting import LOGGER, PackageReport
from tools.updaters import UpdateContext, get_updater


def apply_updates(
    updates: Sequence[Mapping[str, Any]],
    packages: Mapping[str, Package],
) -> tuple[list[str], PackageReport]:
    """Update every package named in ``updates``, collecting per-package failures.

    Malformed input (a bad record, a duplicate, an unmanaged package) raises
    immediately -- that is a bug in the caller, not an upstream hiccup.
    """
    report = PackageReport("update")
    applied: list[str] = []
    seen: set[str] = set()

    for update in updates:
        name, oldver, newver = _parse_update(update)
        if name in seen:
            raise ValueError(f"duplicate nvcmp result for {name}")
        seen.add(name)
        package = packages[name]

        with report.package(name):
            updater = get_updater(package.updater_name)
            updater.apply(
                UpdateContext(
                    name=name,
                    directory=package.directory,
                    oldver=oldver,
                    newver=newver,
                ),
                updater.parse_config(name, package.update),
            )
            LOGGER.info("%s: %s -> %s", name, oldver or "(new)", newver)
            applied.append(name)

    return applied, report


def _parse_update(update: Mapping[str, Any]) -> tuple[str, str | None, str]:
    name = update.get("name")
    newver = update.get("newver")
    if not isinstance(name, str) or not name:
        raise ValueError(f"invalid nvcmp result: {update!r}")
    if not isinstance(newver, str) or not newver:
        raise ValueError(f"invalid nvcmp result: {update!r}")
    return name, update.get("oldver"), newver


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--applied-output", type=Path, required=True)


def run(args: argparse.Namespace) -> int:
    root = repository_root()
    updates = json.loads(args.input.read_text())
    applied, report = apply_updates(updates, discover_packages(root))
    write_text_atomic(args.applied_output, "".join(f"{name}\n" for name in applied))
    LOGGER.info("applied %d update(s)", len(applied))
    report.raise_if_failed()
    return 0
