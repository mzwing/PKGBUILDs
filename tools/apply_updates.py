#!/usr/bin/env python3
"""把 nvcmp 的 JSON 结果应用到对应包的 PKGBUILD。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.common.pkgbuild import write_text_atomic
from tools.packages import discover_packages
from tools.updaters import UPDATERS


def apply_updates(
    updates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Mapping[str, Any]],
    repository_root: Path,
) -> list[str]:
    applied: list[str] = []
    seen: set[str] = set()
    for update in updates:
        name, oldver, newver = _parse_update(update)
        if name in seen:
            raise ValueError(f"duplicate nvcmp result for {name}")
        seen.add(name)

        updater = UPDATERS[config[name]["updater"]]
        updater(name, config[name], oldver, newver, repository_root)
        applied.append(name)

    return applied


def _parse_update(update: Mapping[str, Any]) -> tuple[str, str | None, str]:
    name = update["name"]
    newver = update["newver"]
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(newver, str)
        or not newver
    ):
        raise ValueError(f"invalid nvcmp result: {update!r}")
    return name, update.get("oldver"), newver


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply standard nvcmp JSON results")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--applied-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    updates = json.loads(args.input.read_text())
    packages = discover_packages(repository_root)
    config = {name: package.update for name, package in packages.items()}
    applied = apply_updates(updates, config, repository_root)
    text = "".join(f"{name}\n" for name in applied)
    write_text_atomic(args.applied_output, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
