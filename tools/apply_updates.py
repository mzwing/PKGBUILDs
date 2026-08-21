#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.common.pkgbuild import write_text_atomic
from tools.updaters import declarative, vcs


def apply_updates(
    updates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    repository_root: Path,
) -> list[str]:
    packages = config.get("packages")
    if not isinstance(packages, Mapping):
        raise TypeError("updaters.toml must contain a [packages] table")

    applied: list[str] = []
    seen: set[str] = set()
    for update in updates:
        name, oldver, newver = _parse_update(update)
        if name in seen:
            raise ValueError(f"duplicate nvcmp result for {name}")
        seen.add(name)
        package_config = packages.get(name)
        if not isinstance(package_config, Mapping):
            raise TypeError(f"no updater configured for {name}")

        updater = package_config.get("updater")
        if updater == "declarative":
            declarative.apply_update(
                name,
                package_config,
                oldver,
                newver,
                repository_root,
            )
        elif updater == "vcs":
            vcs.apply_update(
                name,
                package_config,
                oldver,
                newver,
                repository_root,
            )
        elif updater == "command":
            _run_command_updater(
                name,
                package_config,
                oldver,
                newver,
                repository_root,
            )
        else:
            raise ValueError(f"{name}: unsupported updater type {updater!r}")
        applied.append(name)

    return applied


def _parse_update(update: Mapping[str, Any]) -> tuple[str, str | None, str]:
    name = update.get("name")
    oldver = update.get("oldver")
    newver = update.get("newver")
    delta = update.get("delta")
    if not isinstance(name, str) or not name:
        raise ValueError("nvcmp result has an invalid name")
    if oldver is not None and not isinstance(oldver, str):
        raise ValueError(f"{name}: nvcmp oldver is invalid")
    if not isinstance(newver, str) or not newver:
        raise ValueError(f"{name}: nvcmp newver is invalid")
    if delta not in {"new", "old", "added"}:
        raise ValueError(f"{name}: unexpected nvcmp delta {delta!r}")
    return name, oldver, newver


def _run_command_updater(
    name: str,
    config: Mapping[str, Any],
    oldver: str | None,
    newver: str,
    repository_root: Path,
) -> None:
    configured = config.get("command")
    if not isinstance(configured, list) or not all(
        isinstance(item, str) and item for item in configured
    ):
        raise ValueError(f"{name}: command updater requires a command array")
    command = [sys.executable if item == "{python}" else item for item in configured]
    command.extend(["--newver", newver, "--package-dir", str(config["directory"])])
    if oldver is not None:
        command.extend(["--oldver", oldver])
    result = subprocess.run(command, cwd=repository_root, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{name}: command updater failed with {result.returncode}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispatch standard nvcmp JSON results")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("updaters.toml"))
    parser.add_argument("--applied-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    updates = json.loads(args.input.read_text())
    if not isinstance(updates, list) or not all(
        isinstance(update, Mapping) for update in updates
    ):
        raise ValueError("nvcmp input must be a JSON array of objects")
    with args.config.open("rb") as config_file:
        config = tomllib.load(config_file)
    applied = apply_updates(updates, config, repository_root)
    text = "".join(f"{name}\n" for name in applied)
    write_text_atomic(args.applied_output, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
