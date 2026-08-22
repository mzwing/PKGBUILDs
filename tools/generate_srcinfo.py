#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.common.pkgbuild import write_text_atomic

_MANAGED_SRCINFO_FIELD = re.compile(
    r"^(?:source(?:_[A-Za-z0-9_]+)?|sha256sums(?:_[A-Za-z0-9_]+)?|noextract)$"
)


def generate_for_packages(
    package_names: list[str],
    repository_root: Path,
    *,
    require_makepkg: bool,
) -> None:
    config = _load_config(repository_root / "updaters.toml")
    makepkg = shutil.which("makepkg")
    if require_makepkg and makepkg is None:
        raise RuntimeError("makepkg is required but was not found")

    for name in package_names:
        package_dir = _package_directory(config, name, repository_root)
        srcinfo_path = package_dir / ".SRCINFO"
        if makepkg is not None:
            result = subprocess.run(
                [makepkg, "--printsrcinfo"],
                cwd=package_dir,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"{name}: makepkg --printsrcinfo failed: {result.stderr.strip()}"
                )
            generated = result.stdout
        else:
            generated = fallback_srcinfo(package_dir)
        write_text_atomic(srcinfo_path, generated)


def fallback_srcinfo(package_dir: Path) -> str:
    srcinfo_path = package_dir / ".SRCINFO"
    original = srcinfo_path.read_text()
    fields = ["pkgver", "pkgrel", *_managed_fields(original)]
    values = _read_pkgbuild_values(package_dir / "PKGBUILD", fields)

    replacements: dict[str, list[str]] = {}
    for field in fields:
        field_values = values.get(field)
        if not field_values:
            raise ValueError(f"{package_dir.name}: PKGBUILD did not define {field}")
        replacements[field] = field_values

    seen: set[str] = set()
    output: list[str] = []
    for line in original.splitlines(keepends=True):
        match = re.match(r"^(\s*)([A-Za-z0-9_]+) = .*(\n?)$", line)
        if match is None or match.group(2) not in replacements:
            output.append(line)
            continue
        indent, field, newline = match.groups()
        if field not in seen:
            ending = newline or "\n"
            output.extend(
                f"{indent}{field} = {value}{ending}" for value in replacements[field]
            )
            seen.add(field)

    missing = set(replacements) - seen
    if missing:
        raise ValueError(
            f"{package_dir.name}: .SRCINFO lacks fields: {', '.join(sorted(missing))}"
        )
    return "".join(output)


def _managed_fields(srcinfo: str) -> list[str]:
    fields: list[str] = []
    for line in srcinfo.splitlines():
        stripped = line.lstrip()
        field, separator, _value = stripped.partition(" = ")
        if (
            separator
            and _MANAGED_SRCINFO_FIELD.fullmatch(field)
            and field not in fields
        ):
            fields.append(field)
    return fields


def _read_pkgbuild_values(pkgbuild: Path, fields: list[str]) -> dict[str, list[str]]:
    script = r"""
set -eo pipefail
source "$1"
shift
for key in "$@"; do
  if [[ "$key" == pkgver || "$key" == pkgrel ]]; then
    eval 'value=${'"$key"'}'
    printf '%s\0%s\0' "$key" "$value"
    continue
  fi
  declare -p "$key" >/dev/null 2>&1 || continue
  eval 'items=("${'"$key"'[@]}")'
  for value in "${items[@]}"; do
    printf '%s\0%s\0' "$key" "$value"
  done
done
"""
    result = subprocess.run(
        ["bash", "-c", script, "srcinfo-fallback", str(pkgbuild.resolve()), *fields],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"failed to evaluate {pkgbuild}: {result.stderr.decode().strip()}"
        )
    chunks = result.stdout.split(b"\0")
    if chunks and chunks[-1] == b"":
        chunks.pop()
    if len(chunks) % 2:
        raise RuntimeError(f"invalid PKGBUILD evaluation output for {pkgbuild}")
    values: dict[str, list[str]] = {}
    for index in range(0, len(chunks), 2):
        key = chunks[index].decode()
        value = chunks[index + 1].decode()
        values.setdefault(key, []).append(value)
    return values


def _load_config(path: Path) -> dict:
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def _package_directory(config: dict, name: str, repository_root: Path) -> Path:
    package = config.get(name)
    if not isinstance(package, dict):
        raise TypeError(f"no package directory configured for {name}")
    return repository_root / str(package.get("directory", name))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate .SRCINFO after updates")
    parser.add_argument("--packages-file", type=Path, required=True)
    parser.add_argument("--require-makepkg", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    names = [
        line.strip()
        for line in args.packages_file.read_text().splitlines()
        if line.strip()
    ]
    generate_for_packages(
        names,
        Path(__file__).resolve().parents[1],
        require_makepkg=args.require_makepkg,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
