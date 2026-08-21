#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.deepin_wine10_stable.apt_metadata import select_latest_record
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


def check_version() -> str:
    repository = Repository(
        root=DEFAULT_REPO_ROOT,
        distribution=DEFAULT_DISTRIBUTION,
        component=DEFAULT_COMPONENT,
        architecture=DEFAULT_ARCH,
        user_agent=DEFAULT_USER_AGENT,
    )
    records = read_records_from_text(load_packages_text(repository))
    return select_latest_record(records, DEFAULT_PACKAGE, DEFAULT_ARCH).version


def main() -> int:
    print(check_version())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
