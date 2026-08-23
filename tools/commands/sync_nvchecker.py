"""Build the root nvchecker.toml from each package's update.toml [check] section."""

from __future__ import annotations

import argparse
import shlex
import sys
from typing import Any

import tomli_w

from tools.packages import Package, discover_packages
from tools.paths import repository_root
from tools.reporting import LOGGER

HEADER: dict[str, Any] = {
    "__config__": {
        "oldver": ".nvchecker/oldver.json",
        "newver": ".nvchecker/newver.json",
    }
}


def build_nvchecker_config(
    packages: dict[str, Package],
    *,
    interpreter: str | None = None,
    cli_path: str | None = None,
) -> dict[str, Any]:
    interpreter = interpreter or sys.executable
    cli_path = cli_path or str(repository_root() / "tools" / "cli.py")
    return HEADER | {
        name: _check_section(packages[name], interpreter, cli_path)
        for name in sorted(packages)
    }


def _check_section(package: Package, interpreter: str, cli_path: str) -> dict[str, Any]:
    """Fill in the command for `source = "cmd"` entries that do not spell one out.

    Keeps update.toml free of a hardcoded interpreter and script path, and stops
    the package name from being repeated inside its own configuration.
    """
    check = dict(package.check)
    if check.get("source") == "cmd" and "cmd" not in check:
        check["cmd"] = shlex.join([interpreter, cli_path, "version", package.name])
    return check


def add_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def run(args: argparse.Namespace) -> int:
    del args
    root = repository_root()
    packages = discover_packages(root)
    destination = root / "nvchecker.toml"
    with destination.open("wb") as config_file:
        tomli_w.dump(build_nvchecker_config(packages), config_file)
    LOGGER.info("wrote %s for %d package(s)", destination.name, len(packages))
    return 0
