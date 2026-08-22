#!/usr/bin/env python3
"""聚合各包的 update.toml [check] 节，生成根目录 nvchecker.toml。"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tomli_w

from tools.packages import Package, discover_packages

HEADER = {
    "__config__": {
        "oldver": ".nvchecker/oldver.json",
        "newver": ".nvchecker/newver.json",
    }
}


def build_nvchecker_config(packages: dict[str, Package]) -> dict:
    return HEADER | {name: packages[name].check for name in sorted(packages)}


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    config = build_nvchecker_config(discover_packages(repository_root))
    with (repository_root / "nvchecker.toml").open("wb") as config_file:
        tomli_w.dump(config, config_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
