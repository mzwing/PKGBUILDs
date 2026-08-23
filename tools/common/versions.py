"""Version transforms shared by ``update.toml`` and the generated PKGBUILD.

Each transform has to be expressed twice: once in Python (to know what pkgver
will become) and once as a shell parameter expansion (what gets written into the
PKGBUILD). Keeping both halves in one table means adding a transform is a single
edit and the two halves cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class VersionTransform:
    name: str
    to_pkgver: Callable[[str], str]
    to_shell: Callable[[str], str]


TRANSFORMS: dict[str, VersionTransform] = {
    transform.name: transform
    for transform in (
        VersionTransform("identity", lambda v: v, lambda name: f"${name}"),
        VersionTransform(
            "hyphen_to_underscore",
            lambda v: v.replace("-", "_"),
            lambda name: f"${{{name}//-/_}}",
        ),
        VersionTransform(
            "remove_hyphen",
            lambda v: v.replace("-", ""),
            lambda name: f"${{{name}//-/}}",
        ),
    )
}


def get_transform(name: str) -> VersionTransform:
    try:
        return TRANSFORMS[name]
    except KeyError:
        supported = ", ".join(sorted(TRANSFORMS))
        raise ValueError(
            f"unsupported version transform {name!r}; expected one of: {supported}"
        ) from None
