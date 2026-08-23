"""The contract every updater implements.

An updater owns three things: how to read its own ``[update]`` section out of
``update.toml``, how to apply a new version to a PKGBUILD, and -- optionally --
how to look the latest version up when nvchecker cannot do it natively.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class UpdateContext:
    """Everything an updater needs about the package being updated."""

    name: str
    directory: Path
    oldver: str | None
    newver: str

    @property
    def pkgbuild(self) -> Path:
        return self.directory / "PKGBUILD"


class Updater[ConfigT](ABC):
    name: ClassVar[str]

    @abstractmethod
    def parse_config(self, package: str, raw: Mapping[str, Any]) -> ConfigT:
        """Validate the ``[update]`` table, raising ValueError with context."""

    @abstractmethod
    def apply(self, context: UpdateContext, config: ConfigT) -> None: ...

    def latest_version(self, config: ConfigT) -> str:
        raise NotImplementedError(
            f"the {self.name!r} updater cannot look up versions itself; "
            "let nvchecker do it"
        )


def require(
    raw: Mapping[str, Any],
    key: str,
    *,
    package: str,
    section: str = "update",
    kind: type = str,
) -> Any:
    """Read a required key, reporting the package and location on failure."""
    if key not in raw:
        raise ValueError(f"{package}: update.toml is missing [{section}].{key}")
    value = raw[key]
    if not isinstance(value, kind) or not value:
        raise ValueError(
            f"{package}: [{section}].{key} must be a non-empty {kind.__name__}"
        )
    return value


def reject_unknown(
    raw: Mapping[str, Any],
    allowed: set[str],
    *,
    package: str,
    section: str = "update",
) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(
            f"{package}: unknown [{section}] key(s): {', '.join(unknown)}; "
            f"expected any of: {', '.join(sorted(allowed))}"
        )
