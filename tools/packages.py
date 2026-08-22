"""扫描仓库发现受管包：含 update.toml 的目录即一个包。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPDATE_FILE = "update.toml"


@dataclass(frozen=True)
class Package:
    name: str
    directory: Path
    check: dict[str, Any]  # nvchecker 配置节
    update: dict[str, Any]  # 更新器配置节


def discover_packages(repository_root: Path) -> dict[str, Package]:
    packages: dict[str, Package] = {}
    for update_path in sorted(repository_root.glob(f"*/{UPDATE_FILE}")):
        config = tomllib.loads(update_path.read_text())
        name = update_path.parent.name
        packages[name] = Package(
            name=name,
            directory=update_path.parent,
            check=config["check"],
            update=config["update"],
        )
    return packages
