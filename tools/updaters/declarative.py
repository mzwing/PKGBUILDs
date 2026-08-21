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
    package_dir = repository_root / str(config.get("directory", package_name))
    pkgbuild_path = package_dir / "PKGBUILD"
    original = pkgbuild_path.read_text()

    version_config = _required_mapping(config, "version")
    variable = _required_string(version_config, "variable")
    transform = _required_string(version_config, "transform")
    transformed_version(newver, transform)

    source_values: dict[str, list[str]] = {}
    checksum_values: dict[str, list[str]] = {}
    assets = config.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError(f"{package_name}: declarative updater requires assets")

    for asset in assets:
        if not isinstance(asset, Mapping):
            raise TypeError(f"{package_name}: invalid asset declaration")
        source_field = _required_string(asset, "source_field")
        checksum_field = _required_string(asset, "checksum_field")
        download_url, source_value = _resolve_asset(
            package_name,
            asset,
            newver,
            fetch_json_fn=fetch_json_fn,
        )
        source_values.setdefault(source_field, []).append(source_value)
        checksum_values.setdefault(checksum_field, []).append(hash_url_fn(download_url))

    updated = replace_assignment(original, variable, newver)
    updated = replace_assignment(
        updated,
        "pkgver",
        pkgver_expression(variable, transform),
        raw=True,
    )
    if read_assignment(original, variable) != newver:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)

    for field, values in source_values.items():
        updated = replace_array(updated, field, values, expand_shell=True)
    for field, values in checksum_values.items():
        updated = replace_array(updated, field, values)

    write_text_atomic(pkgbuild_path, updated)


def _resolve_asset(
    package_name: str,
    asset: Mapping[str, Any],
    version: str,
    *,
    fetch_json_fn: JsonFetcher,
) -> tuple[str, str]:
    kind = _required_string(asset, "kind")
    if kind == "url":
        download_url = _render(_required_string(asset, "url"), version=version)
        source_value = _render(
            _required_string(asset, "source_entry"),
            version=version,
            url=download_url,
        )
        return download_url, source_value

    if kind == "release_asset":
        index_url = _required_string(asset, "index_url")
        wanted_name = _render(_required_string(asset, "asset_name"), version=version)
        releases = fetch_json_fn(index_url)
        if not isinstance(releases, list):
            raise ValueError(f"{package_name}: JSON asset index is not a list")

        for release in releases:
            if not isinstance(release, Mapping):
                continue
            release_assets = release.get("assets")
            if not isinstance(release_assets, list):
                continue
            matches = [
                item
                for item in release_assets
                if isinstance(item, Mapping) and item.get("name") == wanted_name
            ]
            if len(matches) > 1:
                raise ValueError(
                    f"{package_name}: multiple {wanted_name!r} assets in one release"
                )
            if len(matches) == 1:
                selected = matches[0]
                download_url = selected.get("browser_download_url")
                if not isinstance(download_url, str) or not download_url:
                    raise ValueError(
                        f"{package_name}: matching asset has no download URL"
                    )
                source_value = _render(
                    _required_string(asset, "source_entry"),
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


def _required_mapping(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key)
    if not isinstance(value, Mapping):
        raise TypeError(f"missing or invalid configuration table: {key}")
    return value


def _required_string(config: Mapping[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing or invalid configuration value: {key}")
    return value
