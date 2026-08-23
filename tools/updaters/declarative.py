"""Updater for packages whose sources are a fixed template of the version.

Checksums are taken from the source entries *after* they have been written and
shell-expanded, so the sha256sums always describe exactly what makepkg will
download. There is deliberately no second URL in update.toml to keep in sync.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from tools.common.downloads import fetch_json, sha256_url
from tools.common.fsutil import write_text_atomic
from tools.common.pkgbuild import (
    read_assignment,
    replace_array,
    replace_assignment,
    source_url,
)
from tools.common.pkgbuild_eval import read_variables_from_text
from tools.common.versions import VersionTransform, get_transform
from tools.updaters.base import UpdateContext, Updater, reject_unknown, require

JsonFetcher = Callable[[str], Any]
Hasher = Callable[[str], str]


@dataclass(frozen=True)
class VersionSpec:
    variable: str
    transform: VersionTransform


@dataclass(frozen=True)
class Asset:
    source_entry: str
    arches: tuple[str | None, ...]
    arch_aliases: Mapping[str, str]


@dataclass(frozen=True)
class UrlAsset(Asset):
    """A source whose URL is fully determined by the PKGBUILD itself."""


@dataclass(frozen=True)
class ReleaseAsset(Asset):
    """A source whose URL has to be looked up in a release index."""

    index_url: str
    asset_name: str


@dataclass(frozen=True)
class DeclarativeConfig:
    version: VersionSpec
    assets: tuple[Asset, ...]


class DeclarativeUpdater(Updater[DeclarativeConfig]):
    name = "declarative"

    def __init__(
        self,
        *,
        fetch_json_fn: JsonFetcher = fetch_json,
        hash_url_fn: Hasher = sha256_url,
    ) -> None:
        self._fetch_json = fetch_json_fn
        self._hash_url = hash_url_fn

    # -- configuration ----------------------------------------------------

    def parse_config(self, package: str, raw: Mapping[str, Any]) -> DeclarativeConfig:
        reject_unknown(raw, {"version", "assets"}, package=package)
        return DeclarativeConfig(
            version=self._parse_version(
                package, require(raw, "version", package=package, kind=dict)
            ),
            assets=tuple(
                self._parse_asset(package, index, entry)
                for index, entry in enumerate(
                    require(raw, "assets", package=package, kind=list)
                )
            ),
        )

    @staticmethod
    def _parse_version(package: str, raw: Mapping[str, Any]) -> VersionSpec:
        reject_unknown(
            raw, {"variable", "transform"}, package=package, section="update.version"
        )
        return VersionSpec(
            variable=require(
                raw, "variable", package=package, section="update.version"
            ),
            transform=get_transform(
                require(raw, "transform", package=package, section="update.version")
            ),
        )

    @staticmethod
    def _parse_asset(package: str, index: int, raw: Mapping[str, Any]) -> Asset:
        section = f"update.assets[{index}]"
        kind = require(raw, "kind", package=package, section=section)
        common = {
            "source_entry": require(
                raw, "source_entry", package=package, section=section
            ),
            "arches": tuple(raw.get("arches", [None])),
            "arch_aliases": dict(raw.get("arch_aliases", {})),
        }
        shared = {"kind", "source_entry", "arches", "arch_aliases"}

        if kind == "url":
            reject_unknown(raw, shared, package=package, section=section)
            return UrlAsset(**common)
        if kind == "release_asset":
            reject_unknown(
                raw,
                shared | {"index_url", "asset_name"},
                package=package,
                section=section,
            )
            return ReleaseAsset(
                **common,
                index_url=require(raw, "index_url", package=package, section=section),
                asset_name=require(raw, "asset_name", package=package, section=section),
            )
        raise ValueError(
            f"{package}: {section}.kind must be 'url' or 'release_asset', got {kind!r}"
        )

    # -- applying ---------------------------------------------------------

    def apply(self, context: UpdateContext, config: DeclarativeConfig) -> None:
        original = context.pkgbuild.read_text()
        updated = _apply_version(original, config.version, context.newver)

        entries: dict[str | None, list[str]] = {}
        for asset in config.assets:
            for arch in asset.arches:
                entries.setdefault(arch, []).append(
                    self._source_entry(context.name, _for_arch(asset, arch), context)
                )

        for arch, values in entries.items():
            updated = replace_array(
                updated, _field("source", arch), values, expand_shell=True
            )

        updated = self._apply_checksums(updated, context, entries)
        write_text_atomic(context.pkgbuild, updated)

    @staticmethod
    def static_source_entries(
        config: DeclarativeConfig, version: str
    ) -> dict[str, list[str]]:
        """Source entries derivable without network access, keyed by array name.

        Architectures fed by a release index are omitted: their URLs only exist
        upstream. Used by `pkgtool verify` to detect a PKGBUILD whose source
        array has drifted away from update.toml and would be silently reverted
        by the next run.
        """
        entries: dict[str, list[str]] = {}
        needs_network: set[str] = set()
        for asset in config.assets:
            for arch in asset.arches:
                field = _field("source", arch)
                if isinstance(asset, ReleaseAsset):
                    needs_network.add(field)
                    continue
                entries.setdefault(field, []).append(
                    _render(_for_arch(asset, arch).source_entry, version=version)
                )
        return {
            field: values
            for field, values in entries.items()
            if field not in needs_network
        }

    def _apply_checksums(
        self,
        text: str,
        context: UpdateContext,
        entries: Mapping[str | None, list[str]],
    ) -> str:
        expanded = read_variables_from_text(
            text,
            [_field("source", arch) for arch in entries],
            directory=context.directory,
        )
        for arch, values in entries.items():
            field = _field("source", arch)
            resolved = expanded.get(field, [])
            if len(resolved) != len(values):
                raise ValueError(
                    f"{context.name}: {field} expanded to {len(resolved)} entries, "
                    f"expected {len(values)}"
                )
            text = replace_array(
                text,
                _field("sha256sums", arch),
                [self._hash_url(source_url(entry)) for entry in resolved],
            )
        return text

    def _source_entry(self, package: str, asset: Asset, context: UpdateContext) -> str:
        version = context.newver
        if isinstance(asset, ReleaseAsset):
            filename = _render(asset.asset_name, version=version)
            return _render(
                asset.source_entry,
                version=version,
                filename=filename,
                url=self._find_release_asset(package, asset.index_url, filename),
            )
        return _render(asset.source_entry, version=version)

    def _find_release_asset(self, package: str, index_url: str, wanted: str) -> str:
        for release in self._fetch_json(index_url):
            matches = [
                item for item in release.get("assets", []) if item.get("name") == wanted
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"{package}: multiple {wanted!r} assets in one release"
                )
            if matches:
                download_url = matches[0].get("browser_download_url")
                if not download_url:
                    raise ValueError(f"{package}: asset {wanted!r} has no download URL")
                return download_url
        raise ValueError(f"{package}: asset {wanted!r} was not found")


def _apply_version(text: str, spec: VersionSpec, newver: str) -> str:
    updated = replace_assignment(text, spec.variable, newver)
    updated = replace_assignment(
        updated, "pkgver", spec.transform.to_shell(spec.variable), raw=True
    )
    if read_assignment(text, spec.variable) != newver:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)
    return updated


def _for_arch(asset: Asset, arch: str | None) -> Asset:
    """Substitute the {arch}/{alias} placeholders for one architecture."""
    if arch is None:
        return asset
    alias = asset.arch_aliases.get(arch, arch)

    def substitute(text: str) -> str:
        return text.replace("{alias}", alias).replace("{arch}", arch)

    changes: dict[str, Any] = {"source_entry": substitute(asset.source_entry)}
    if isinstance(asset, ReleaseAsset):
        changes["index_url"] = substitute(asset.index_url)
        changes["asset_name"] = substitute(asset.asset_name)
    return replace(asset, **changes)


def _field(prefix: str, arch: str | None) -> str:
    return prefix if arch is None else f"{prefix}_{arch}"


def _render(template: str, **values: str) -> str:
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"{{{name}}}", value)
    return rendered
