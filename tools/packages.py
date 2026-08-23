"""Discover managed packages: any directory with an update.toml is a package."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPDATE_FILE = "update.toml"
_SECTIONS = {"check", "update"}


@dataclass(frozen=True)
class Package:
    name: str
    directory: Path
    check: dict[str, Any]  # nvchecker config section, passed through verbatim
    updater_name: str
    update: dict[str, Any]  # updater config, without the `updater` key itself

    @property
    def pkgbuild(self) -> Path:
        return self.directory / "PKGBUILD"

    @property
    def srcinfo(self) -> Path:
        return self.directory / ".SRCINFO"


def discover_packages(repository_root: Path) -> dict[str, Package]:
    packages: dict[str, Package] = {}
    for update_path in sorted(repository_root.glob(f"*/{UPDATE_FILE}")):
        name = update_path.parent.name
        packages[name] = _load(name, update_path)
    return packages


def _load(name: str, update_path: Path) -> Package:
    try:
        config = tomllib.loads(update_path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{name}: {UPDATE_FILE} is not valid TOML: {error}") from error

    unknown = sorted(set(config) - _SECTIONS)
    if unknown:
        raise ValueError(
            f"{name}: {UPDATE_FILE} has unknown section(s): {', '.join(unknown)}"
        )
    for section in sorted(_SECTIONS):
        if section not in config:
            raise ValueError(f"{name}: {UPDATE_FILE} is missing a [{section}] table")
        if not isinstance(config[section], dict):
            raise TypeError(f"{name}: {UPDATE_FILE} [{section}] must be a table")

    update = dict(config["update"])
    updater_name = update.pop("updater", None)
    if not isinstance(updater_name, str) or not updater_name:
        raise ValueError(f"{name}: [update].updater must be a non-empty string")

    return Package(
        name=name,
        directory=update_path.parent,
        check=config["check"],
        updater_name=updater_name,
        update=update,
    )
