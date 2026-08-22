#!/usr/bin/env python3
"""打印 apt 型包的上游最新版本，供 nvchecker 的 cmd 源调用。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.packages import discover_packages
from tools.updaters import apt


def package_version(repository_root: Path, name: str) -> str:
    package = discover_packages(repository_root)[name]
    return apt.latest_version(package.update)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the latest upstream version")
    parser.add_argument("package")
    args = parser.parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    print(package_version(repository_root, args.package))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
