"""更新器注册表：update.toml 里的 updater 名到实现的映射。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tools.updaters import apt, declarative, vcs

Updater = Callable[[str, Mapping[str, Any], str | None, str, Path], None]

UPDATERS: dict[str, Updater] = {
    "declarative": declarative.apply_update,
    "vcs": vcs.apply_update,
    "apt": apt.apply_update,
}
