from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools.common.pkgbuild import (
    read_assignment,
    replace_assignment,
    write_text_atomic,
)


def apply_update(
    package_name: str,
    config: Mapping[str, Any],
    oldver: str | None,
    newver: str,
    repository_root: Path,
) -> None:
    del oldver
    backend = _required_string(config, "backend")
    if backend != "git":
        raise ValueError(f"{package_name}: unsupported VCS backend {backend!r}")

    package_dir = repository_root / str(config.get("directory", package_name))
    pkgbuild_path = package_dir / "PKGBUILD"
    source_array = str(config.get("source_array", "source"))
    source_name = _required_string(config, "source_name")
    version_function = str(config.get("version_function", "pkgver"))
    source = _read_named_source(
        pkgbuild_path, source_array=source_array, source_name=source_name
    )
    clone_url = _git_clone_url(source, package_name)

    with tempfile.TemporaryDirectory(prefix=f"{package_name}-") as temporary:
        srcdir = Path(temporary)
        checkout = srcdir / source_name
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
            version_function,
            package_name,
        )

    original = pkgbuild_path.read_text()
    current_version = read_assignment(original, "pkgver")
    updated = replace_assignment(original, "pkgver", generated_version)
    if current_version != generated_version:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)
    write_text_atomic(pkgbuild_path, updated)


def _read_named_source(
    pkgbuild_path: Path,
    *,
    source_array: str,
    source_name: str,
) -> str:
    script = r"""
set -eo pipefail
source "$1"
array_name=$2
wanted=$3
eval 'items=("${'"$array_name"'[@]}")'
for item in "${items[@]}"; do
  case "$item" in
    "$wanted"::*) printf '%s\n' "$item" ;;
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
            source_array,
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
    version_function: str,
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
            version_function,
        ],
        description=f"{package_name}: run {version_function}()",
        environment=environment,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(
            f"{package_name}: {version_function}() must print exactly one version"
        )
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


def _required_string(config: Mapping[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid configuration value: {key}")
    return value
