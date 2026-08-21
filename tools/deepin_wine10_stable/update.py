#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urljoin

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.common.pkgbuild import (
    read_assignment,
    replace_array,
    replace_assignment,
    write_text_atomic,
)
from tools.deepin_wine10_stable.apt_metadata import (
    PackageRecord,
    select_record_by_version,
)
from tools.deepin_wine10_stable.config import (
    DEFAULT_ARCH,
    DEFAULT_COMPONENT,
    DEFAULT_DISTRIBUTION,
    DEFAULT_PACKAGE,
    DEFAULT_REPO_ROOT,
    DEFAULT_USER_AGENT,
)
from tools.deepin_wine10_stable.repository import (
    Repository,
    load_packages_text,
    read_records_from_text,
)


def update_pkgbuild_text(
    text: str,
    record: PackageRecord,
    repo_root: str = DEFAULT_REPO_ROOT,
) -> str:
    current_version = read_assignment(text, "_pkgver")
    updated = replace_assignment(text, "_pkgver", record.version)
    if current_version != record.version:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)

    root = repo_root if repo_root.endswith("/") else f"{repo_root}/"
    concrete_url = urljoin(root, record.filename)
    source_url = concrete_url.replace(record.version, "${_pkgver}")
    filename = f"{record.package}_${{_pkgver}}_{record.architecture}.deb"
    updated = replace_array(updated, "source", [source_url], expand_shell=True)
    updated = replace_array(updated, "noextract", [filename], expand_shell=True)
    return replace_array(updated, "sha256sums", [record.sha256])


def apply_update(newver: str, package_dir: Path) -> None:
    repository = Repository(
        root=DEFAULT_REPO_ROOT,
        distribution=DEFAULT_DISTRIBUTION,
        component=DEFAULT_COMPONENT,
        architecture=DEFAULT_ARCH,
        user_agent=DEFAULT_USER_AGENT,
    )
    records = read_records_from_text(load_packages_text(repository))
    record = select_record_by_version(
        records,
        DEFAULT_PACKAGE,
        DEFAULT_ARCH,
        newver,
    )
    pkgbuild_path = package_dir / "PKGBUILD"
    updated = update_pkgbuild_text(pkgbuild_path.read_text(), record)
    write_text_atomic(pkgbuild_path, updated)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply one nvchecker result to deepin-wine10-stable"
    )
    parser.add_argument("--oldver")
    parser.add_argument("--newver", required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    apply_update(args.newver, args.package_dir)
    print(f"updated deepin-wine10-stable to {args.newver}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
