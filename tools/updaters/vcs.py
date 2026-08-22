from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools.common.pkgbuild import read_assignment, replace_assignment, write_text_atomic


def apply_update(
    package_name: str,
    config: Mapping[str, Any],
    oldver: str | None,
    newver: str,
    repository_root: Path,
) -> None:
    del oldver, config
    pkgbuild_path = repository_root / package_name / "PKGBUILD"
    source = _read_named_source(pkgbuild_path, source_name=package_name)
    clone_url = _git_clone_url(source, package_name)

    with tempfile.TemporaryDirectory(prefix=f"{package_name}-") as temporary:
        srcdir = Path(temporary)
        checkout = srcdir / package_name
        _run(
            ["git", "clone", "--no-checkout", clone_url, str(checkout)],
            description=f"{package_name}: clone VCS source",
        )
        _run(
            ["git", "-C", str(checkout), "checkout", "--detach", newver],
            description=f"{package_name}: checkout nvchecker commit",
        )
        checked_out = _run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            description=f"{package_name}: read checked-out commit",
        ).strip()
        if checked_out.lower() != newver.lower():
            raise ValueError(
                f"{package_name}: checked out {checked_out}, expected {newver}"
            )
        generated_version = _run_pkgver(
            pkgbuild_path.resolve(),
            srcdir,
            package_name,
        )

    original = pkgbuild_path.read_text()
    current_version = read_assignment(original, "pkgver")
    updated = replace_assignment(original, "pkgver", generated_version)
    if current_version != generated_version:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)
    write_text_atomic(pkgbuild_path, updated)


def _read_named_source(pkgbuild_path: Path, *, source_name: str) -> str:
    script = r"""
set -eo pipefail
source "$1"
for item in "${source[@]}"; do
  case "$item" in
    "$2"::*) printf '%s\n' "$item" ;;
  esac
done
"""
    result = _run(
        [
            "bash",
            "-c",
            script,
            "vcs-source",
            str(pkgbuild_path.resolve()),
            source_name,
        ],
        description=f"read {source_name!r} from {pkgbuild_path}",
    )
    matches = [line for line in result.splitlines() if line]
    if len(matches) != 1:
        raise ValueError(
            f"expected one VCS source named {source_name!r}, found {len(matches)}"
        )
    return matches[0].split("::", 1)[1]


def _git_clone_url(source: str, package_name: str) -> str:
    if not source.startswith("git+"):
        raise ValueError(f"{package_name}: selected source is not a git source")
    return source.removeprefix("git+").split("#", 1)[0]


def _run_pkgver(
    pkgbuild_path: Path,
    srcdir: Path,
    package_name: str,
) -> str:
    script = r"""
set -eo pipefail
source "$1"
cd "$2"
"$3"
"""
    environment = os.environ.copy()
    environment["srcdir"] = str(srcdir)
    environment["pkgdir"] = str(srcdir / "pkgdir")
    output = _run(
        [
            "bash",
            "-c",
            script,
            "vcs-pkgver",
            str(pkgbuild_path),
            str(srcdir),
            "pkgver",
        ],
        description=f"{package_name}: run pkgver()",
        environment=environment,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"{package_name}: pkgver() must print exactly one version")
    return lines[0]


def _run(
    command: list[str],
    *,
    description: str,
    environment: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{description} failed: {detail}")
    return result.stdout
