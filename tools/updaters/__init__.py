"""Updater registry: maps the ``updater`` name in update.toml to an implementation."""

from __future__ import annotations

from typing import Any

from tools.updaters.apt import AptUpdater
from tools.updaters.base import UpdateContext, Updater
from tools.updaters.declarative import DeclarativeUpdater
from tools.updaters.vcs import VcsUpdater

__all__ = ["UPDATERS", "UpdateContext", "Updater", "get_updater"]

UPDATERS: dict[str, Updater[Any]] = {
    updater.name: updater
    for updater in (DeclarativeUpdater(), VcsUpdater(), AptUpdater())
}


def get_updater(name: str) -> Updater[Any]:
    try:
        return UPDATERS[name]
    except KeyError:
        supported = ", ".join(sorted(UPDATERS))
        raise ValueError(
            f"unknown updater {name!r}; expected one of: {supported}"
        ) from None
