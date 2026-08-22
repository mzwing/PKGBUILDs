from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tools.common.downloads import fetch_json, sha256_url
from tools.common.pkgbuild import (
    pkgver_expression,
    read_assignment,
    replace_array,
    replace_assignment,
    transformed_version,
    write_text_atomic,
)

JsonFetcher = Callable[[str], Any]
Hasher = Callable[[str], str]


def apply_update(
    package_name: str,
    config: Mapping[str, Any],
    oldver: str | None,
    newver: str,
    repository_root: Path,
    *,
    fetch_json_fn: JsonFetcher = fetch_json,
    hash_url_fn: Hasher = sha256_url,
) -> None:
    del oldver
    pkgbuild_path = repository_root / package_name / "PKGBUILD"
    original = pkgbuild_path.read_text()

    version_config = config["version"]
    variable = version_config["variable"]
    transform = version_config["transform"]
    transformed_version(newver, transform)

    sources: dict[str, list[str]] = {}
    checksums: dict[str, list[str]] = {}
    for asset in config["assets"]:
        for arch in asset.get("arches", [None]):
            alias = asset.get("arch_aliases", {}).get(arch, arch)
            concrete = _with_arch(asset, arch, alias)
            download_url, entry = _resolve_asset(
                package_name, concrete, newver, fetch_json_fn=fetch_json_fn
            )
            suffix = "" if arch is None else f"_{arch}"
            sources.setdefault(f"source{suffix}", []).append(entry)
            checksums.setdefault(f"sha256sums{suffix}", []).append(
                hash_url_fn(download_url)
            )

    updated = replace_assignment(original, variable, newver)
    updated = replace_assignment(
        updated,
        "pkgver",
        pkgver_expression(variable, transform),
        raw=True,
    )
    if read_assignment(original, variable) != newver:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)

    for field, values in sources.items():
        updated = replace_array(updated, field, values, expand_shell=True)
    for field, values in checksums.items():
        updated = replace_array(updated, field, values)

    write_text_atomic(pkgbuild_path, updated)


def _with_arch(
    asset: Mapping[str, Any], arch: str | None, alias: str | None
) -> dict[str, Any]:
    """把模板中的 {arch}/{alias} 占位符替换为具体值。"""
    if arch is None:
        return dict(asset)
    return {
        key: value.replace("{alias}", alias).replace("{arch}", arch)
        if isinstance(value, str)
        else value
        for key, value in asset.items()
    }


def _resolve_asset(
    package_name: str,
    asset: Mapping[str, Any],
    version: str,
    *,
    fetch_json_fn: JsonFetcher,
) -> tuple[str, str]:
    kind = asset["kind"]
    if kind == "url":
        download_url = _render(asset["url"], version=version)
        source_value = _render(asset["source_entry"], version=version, url=download_url)
        return download_url, source_value

    if kind == "release_asset":
        wanted_name = _render(asset["asset_name"], version=version)
        releases = fetch_json_fn(asset["index_url"])
        for release in releases:
            matches = [
                item
                for item in release.get("assets", [])
                if item.get("name") == wanted_name
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"{package_name}: multiple {wanted_name!r} assets in one release"
                )
            if matches:
                download_url = matches[0].get("browser_download_url")
                if not download_url:
                    raise ValueError(
                        f"{package_name}: asset {wanted_name!r} has no download URL"
                    )
                source_value = _render(
                    asset["source_entry"],
                    version=version,
                    filename=wanted_name,
                    url=download_url,
                )
                return download_url, source_value

        raise ValueError(f"{package_name}: asset {wanted_name!r} was not found")

    raise ValueError(f"{package_name}: unsupported asset kind {kind!r}")


def _render(template: str, **values: str) -> str:
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"{{{name}}}", value)
    return rendered
