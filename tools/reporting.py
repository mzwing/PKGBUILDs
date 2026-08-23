"""Logging and per-package error collection.

A nightly run touches every managed package. One package failing upstream must
not stop the others, and a single run should surface every problem at once
instead of only the first one.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

LOGGER = logging.getLogger("pkgtool")


def configure_logging(*, verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


@dataclass(frozen=True)
class Failure:
    package: str
    detail: str


@dataclass
class PackageReport:
    """Runs an action over several packages, collecting failures as it goes."""

    action: str
    failures: list[Failure] = field(default_factory=list)

    @contextmanager
    def package(self, name: str) -> Iterator[None]:
        try:
            yield
        except Exception as error:  # noqa: BLE001 - one package must not abort the run
            LOGGER.error("%s: %s failed: %s", name, self.action, error)
            self.failures.append(Failure(package=name, detail=str(error)))

    def raise_if_failed(self) -> None:
        if not self.failures:
            return
        detail = "\n".join(
            f"  {failure.package}: {failure.detail}" for failure in self.failures
        )
        raise RuntimeError(
            f"{self.action} failed for {len(self.failures)} package(s):\n{detail}"
        )
