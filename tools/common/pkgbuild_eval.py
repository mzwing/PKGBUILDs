"""Evaluate a PKGBUILD with bash.

Several tasks need the *expanded* value of a PKGBUILD variable rather than its
literal text -- resolving ``$url``/``$_pkgver`` inside a source entry, reading
pkgver/pkgrel for .SRCINFO, running a VCS package's ``pkgver()``. All of them go
through this module so there is one bash contract to reason about instead of a
snippet per caller.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

# `declare -p` fails for names that were never set, which lets callers ask for
# optional fields (source_aarch64, noextract, ...) without knowing in advance
# which ones the PKGBUILD defines. Scalars are read through "${name[@]}" too:
# bash treats a plain assignment as a one-element array.
_READ_VARIABLES = r"""
set -eo pipefail
source "$1"
shift
for key in "$@"; do
  declare -p "$key" >/dev/null 2>&1 || continue
  eval 'items=("${'"$key"'[@]}")'
  for value in "${items[@]}"; do
    printf '%s\0%s\0' "$key" "$value"
  done
done
"""

_CALL_FUNCTION = r"""
set -eo pipefail
source "$1"
cd "$2"
"$3"
"""


def read_variables(pkgbuild: Path, names: Sequence[str]) -> dict[str, list[str]]:
    """Return the expanded values of ``names``; absent variables are omitted."""
    if not names:
        return {}
    output = _run(
        [
            "bash",
            "-c",
            _READ_VARIABLES,
            "pkgbuild-eval",
            str(pkgbuild.resolve()),
            *names,
        ],
        description=f"evaluate {pkgbuild}",
    )
    return _parse_nul_pairs(output, pkgbuild)


def read_variables_from_text(
    text: str, names: Sequence[str], *, directory: Path
) -> dict[str, list[str]]:
    """Like :func:`read_variables`, for PKGBUILD text that is not on disk yet.

    Used to resolve the sources of an update before committing it, so the
    checksums always describe the entries that actually get written.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=directory,
        prefix=".PKGBUILD.",
        suffix=".eval",
        delete=True,
    ) as handle:
        handle.write(text)
        handle.flush()
        return read_variables(Path(handle.name), names)


def call_function(
    pkgbuild: Path,
    function: str,
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    description: str,
) -> str:
    output = _run(
        [
            "bash",
            "-c",
            _CALL_FUNCTION,
            "pkgbuild-eval",
            str(pkgbuild.resolve()),
            str(cwd),
            function,
        ],
        description=description,
        environment=environment,
    )
    return output.decode()


def _parse_nul_pairs(output: bytes, pkgbuild: Path) -> dict[str, list[str]]:
    chunks = output.split(b"\0")
    if chunks and chunks[-1] == b"":
        chunks.pop()
    if len(chunks) % 2:
        raise RuntimeError(f"invalid PKGBUILD evaluation output for {pkgbuild}")
    values: dict[str, list[str]] = {}
    for index in range(0, len(chunks), 2):
        key = chunks[index].decode()
        values.setdefault(key, []).append(chunks[index + 1].decode())
    return values


def _run(
    command: list[str],
    *,
    description: str,
    environment: Mapping[str, str] | None = None,
) -> bytes:
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=dict(environment) if environment is not None else None,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise RuntimeError(f"{description} failed: {detail}")
    return result.stdout
