"""Print a package's latest upstream version, for nvchecker's `cmd` source.

Stdout must stay exactly one version string: nvchecker consumes it directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.packages import discover_packages
from tools.paths import repository_root
from tools.updaters import get_updater


def package_version(root: Path, name: str) -> str:
    packages = discover_packages(root)
    if name not in packages:
        raise ValueError(f"unknown package: {name}")
    package = packages[name]
    updater = get_updater(package.updater_name)
    return updater.latest_version(updater.parse_config(name, package.update))


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("package")


def run(args: argparse.Namespace) -> int:
    print(package_version(repository_root(), args.package))
    return 0
