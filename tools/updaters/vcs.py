"""Updater for -git packages: check out the commit nvchecker found, then ask
the PKGBUILD's own ``pkgver()`` what that commit is called."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.common.fsutil import write_text_atomic
from tools.common.pkgbuild import read_assignment, replace_assignment, source_url
from tools.common.pkgbuild_eval import call_function, read_variables
from tools.updaters.base import UpdateContext, Updater, reject_unknown


@dataclass(frozen=True)
class VcsConfig:
    """The VCS updater is driven entirely by the PKGBUILD; nothing to configure."""


class VcsUpdater(Updater[VcsConfig]):
    name = "vcs"

    def parse_config(self, package: str, raw: Mapping[str, Any]) -> VcsConfig:
        reject_unknown(raw, set(), package=package)
        return VcsConfig()

    def apply(self, context: UpdateContext, config: VcsConfig) -> None:
        del config
        clone_url = _clone_url(context)

        with tempfile.TemporaryDirectory(prefix=f"{context.name}-") as temporary:
            srcdir = Path(temporary)
            checkout = srcdir / context.name
            _git(
                ["clone", "--no-checkout", clone_url, str(checkout)],
                description=f"{context.name}: clone VCS source",
            )
            _git(
                ["-C", str(checkout), "checkout", "--detach", context.newver],
                description=f"{context.name}: checkout nvchecker commit",
            )
            checked_out = _git(
                ["-C", str(checkout), "rev-parse", "HEAD"],
                description=f"{context.name}: read checked-out commit",
            ).strip()
            if checked_out.lower() != context.newver.lower():
                raise ValueError(
                    f"{context.name}: checked out {checked_out}, "
                    f"expected {context.newver}"
                )
            generated = _run_pkgver(context, srcdir)

        original = context.pkgbuild.read_text()
        updated = replace_assignment(original, "pkgver", generated)
        if read_assignment(original, "pkgver") != generated:
            updated = replace_assignment(updated, "pkgrel", "1", raw=True)
        write_text_atomic(context.pkgbuild, updated)


def _clone_url(context: UpdateContext) -> str:
    sources = read_variables(context.pkgbuild, ["source"]).get("source", [])
    prefix = f"{context.name}::"
    matches = [entry for entry in sources if entry.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(
            f"{context.name}: expected one source named {context.name!r}, "
            f"found {len(matches)}"
        )
    source = source_url(matches[0])
    if not source.startswith("git+"):
        raise ValueError(f"{context.name}: selected source is not a git source")
    return source.removeprefix("git+").split("#", 1)[0]


def _run_pkgver(context: UpdateContext, srcdir: Path) -> str:
    environment = os.environ.copy()
    environment["srcdir"] = str(srcdir)
    environment["pkgdir"] = str(srcdir / "pkgdir")
    output = call_function(
        context.pkgbuild,
        "pkgver",
        cwd=srcdir,
        environment=environment,
        description=f"{context.name}: run pkgver()",
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{context.name}: pkgver() must print exactly one version")
    return lines[0]


def _git(arguments: list[str], *, description: str) -> str:
    result = subprocess.run(
        ["git", *arguments], text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{description} failed: {detail}")
    return result.stdout
