"""Generate .SRCINFO for updated packages.

Uses `makepkg --printsrcinfo` where it is available. The fallback exists so the
tools stay usable on a machine without pacman; it only refreshes the fields this
repository manages, and refuses to run when the PKGBUILD grew a managed field
the existing .SRCINFO does not have -- silently emitting a stale .SRCINFO would
be worse than stopping.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from tools.common.fsutil import write_text_atomic
from tools.common.pkgbuild_eval import read_variables
from tools.packages import Package, discover_packages
from tools.paths import repository_root
from tools.reporting import LOGGER, PackageReport

_MANAGED_PREFIXES = ("source", "sha256sums", "noextract")
_MANAGED_SRCINFO_FIELD = re.compile(
    r"^(?:source(?:_[A-Za-z0-9_]+)?|sha256sums(?:_[A-Za-z0-9_]+)?|noextract)$"
)
_SRCINFO_LINE = re.compile(r"^(\s*)([A-Za-z0-9_]+) = .*(\n?)$")


def generate_for_packages(
    package_names: list[str],
    packages: dict[str, Package],
    *,
    require_makepkg: bool,
) -> PackageReport:
    makepkg = shutil.which("makepkg")
    if makepkg is None:
        if require_makepkg:
            raise RuntimeError("makepkg is required but was not found")
        LOGGER.warning(
            "makepkg not found; patching managed .SRCINFO fields only "
            "(other fields will not be refreshed)"
        )

    report = PackageReport("generate .SRCINFO")
    for name in package_names:
        with report.package(name):
            package = packages[name]
            generated = (
                _run_makepkg(makepkg, package)
                if makepkg is not None
                else fallback_srcinfo(package.directory)
            )
            write_text_atomic(package.srcinfo, generated)
    return report


def _run_makepkg(makepkg: str, package: Package) -> str:
    result = subprocess.run(
        [makepkg, "--printsrcinfo"],
        cwd=package.directory,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"makepkg --printsrcinfo failed: {result.stderr.strip()}")
    return result.stdout


def fallback_srcinfo(package_dir: Path) -> str:
    pkgbuild = package_dir / "PKGBUILD"
    srcinfo_path = package_dir / ".SRCINFO"
    original = srcinfo_path.read_text()

    known = _managed_fields(original)
    missing = [
        field for field in managed_pkgbuild_fields(pkgbuild) if field not in known
    ]
    if missing:
        raise ValueError(
            f"{package_dir.name}: PKGBUILD defines {', '.join(missing)} but .SRCINFO "
            "does not; regenerate it with makepkg --printsrcinfo"
        )

    fields = ["pkgver", "pkgrel", *known]
    values = read_variables(pkgbuild, fields)
    replacements: dict[str, list[str]] = {}
    for field in fields:
        field_values = values.get(field)
        if not field_values:
            raise ValueError(f"{package_dir.name}: PKGBUILD did not define {field}")
        replacements[field] = field_values

    seen: set[str] = set()
    output: list[str] = []
    for line in original.splitlines(keepends=True):
        match = _SRCINFO_LINE.match(line)
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

    unmatched = set(replacements) - seen
    if unmatched:
        raise ValueError(
            f"{package_dir.name}: .SRCINFO lacks fields: {', '.join(sorted(unmatched))}"
        )
    return "".join(output)


def managed_pkgbuild_fields(pkgbuild: Path) -> list[str]:
    """Managed fields the PKGBUILD actually defines, including per-arch variants."""
    arches = [
        arch
        for arch in read_variables(pkgbuild, ["arch"]).get("arch", [])
        if arch != "any"
    ]
    candidates = [
        name
        for prefix in _MANAGED_PREFIXES
        for name in (prefix, *(f"{prefix}_{arch}" for arch in arches))
    ]
    defined = read_variables(pkgbuild, candidates)
    return [name for name in candidates if name in defined]


def _managed_fields(srcinfo: str) -> list[str]:
    fields: list[str] = []
    for line in srcinfo.splitlines():
        field, separator, _value = line.lstrip().partition(" = ")
        if (
            separator
            and _MANAGED_SRCINFO_FIELD.fullmatch(field)
            and field not in fields
        ):
            fields.append(field)
    return fields


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--packages-file", type=Path, required=True)
    parser.add_argument("--require-makepkg", action="store_true")


def run(args: argparse.Namespace) -> int:
    names = [
        line.strip()
        for line in args.packages_file.read_text().splitlines()
        if line.strip()
    ]
    report = generate_for_packages(
        names,
        discover_packages(repository_root()),
        require_makepkg=args.require_makepkg,
    )
    report.raise_if_failed()
    return 0
