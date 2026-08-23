#!/usr/bin/env python3
"""pkgtool -- the entry point for every maintenance task in this repository."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    # The repository is not installed as a distribution, and this file doubles
    # as a plain script (nvchecker's `cmd` source invokes it by absolute path).
    # This is the only sys.path bootstrap in the tree; everything else imports
    # `tools.*` normally.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.commands import (
    apply_updates,
    check_version,
    generate_srcinfo,
    publish_aur,
    sync_nvchecker,
    verify,
)
from tools.reporting import LOGGER, configure_logging

COMMANDS = (
    ("sync", sync_nvchecker, "Regenerate nvchecker.toml from every update.toml"),
    ("apply", apply_updates, "Apply nvcmp results to the affected PKGBUILDs"),
    ("srcinfo", generate_srcinfo, "Regenerate .SRCINFO for the given packages"),
    ("verify", verify, "Check PKGBUILD, .SRCINFO and update.toml invariants"),
    ("publish", publish_aur, "Push updated packages to the AUR"),
    ("version", check_version, "Print a package's latest upstream version"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pkgtool", description=__doc__, allow_abbrev=False
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, module, help_text in COMMANDS:
        subparser = subparsers.add_parser(name, help=help_text, description=help_text)
        module.add_arguments(subparser)
        subparser.set_defaults(handler=module.run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    try:
        return args.handler(args)
    except Exception as error:  # noqa: BLE001 - the CLI boundary reports, not traces
        LOGGER.error("%s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
