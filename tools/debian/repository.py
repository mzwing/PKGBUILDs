"""Locating and fetching a Debian repository's binary package index."""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from urllib.parse import urljoin

from tools.common.downloads import fetch_bytes
from tools.debian.control import decode_metadata

DEFAULT_USER_AGENT = "Debian APT-HTTP/1.3"
_CHECKSUM_SECTIONS = frozenset({"SHA256", "SHA1", "MD5Sum"})


@dataclass(frozen=True)
class Repository:
    root: str
    distribution: str
    component: str
    architecture: str
    user_agent: str = DEFAULT_USER_AGENT


def load_packages_text(repository: Repository, packages_url: str | None = None) -> str:
    url = packages_url or discover_packages_url(repository)
    data = fetch_bytes(url, user_agent=repository.user_agent)
    if url.endswith(".gz"):
        data = gzip.decompress(data)
    return decode_metadata(data)


def discover_packages_url(repository: Repository) -> str:
    dists_root = _dists_root(repository)
    release_text = decode_metadata(
        fetch_bytes(urljoin(dists_root, "Release"), user_agent=repository.user_agent)
    )
    paths = parse_release_packages_paths(
        release_text, repository.component, repository.architecture
    )
    return urljoin(dists_root, best_packages_path(paths))


def parse_release_packages_paths(
    text: str, component: str, architecture: str
) -> list[str]:
    wanted_prefix = f"{component}/binary-{architecture}/"
    paths: list[str] = []
    in_checksum_section = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.endswith(":"):
            in_checksum_section = line[:-1] in _CHECKSUM_SECTIONS
            continue
        if not in_checksum_section:
            continue

        parts = line.split()
        if len(parts) != 3:
            continue
        path = parts[2]
        if path.startswith(wanted_prefix) and path.endswith(
            ("Packages.gz", "Packages")
        ):
            paths.append(path)

    return list(dict.fromkeys(paths))


def best_packages_path(paths: list[str]) -> str:
    for suffix in ("Packages.gz", "Packages"):
        for path in paths:
            if path.endswith(suffix):
                return path
    raise ValueError("Release metadata did not list a Packages index")


def _dists_root(repository: Repository) -> str:
    return urljoin(as_directory(repository.root), f"dists/{repository.distribution}/")


def as_directory(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"
