from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .apt_metadata import (
    best_packages_path,
    decode_metadata,
    parse_packages,
    parse_release_packages_paths,
)
from .config import DEFAULT_USER_AGENT


@dataclass(frozen=True)
class Repository:
    root: str
    distribution: str
    component: str
    architecture: str
    user_agent: str = DEFAULT_USER_AGENT


def load_packages_text(repository: Repository, packages_url: str | None = None) -> str:
    url = packages_url or discover_packages_url(repository)
    data = fetch_url(url, repository.user_agent)
    if url.endswith(".gz"):
        data = gzip.decompress(data)
    return decode_metadata(data)


def load_packages_file(path: Path) -> str:
    data = path.read_bytes()
    if path.name.endswith(".gz"):
        data = gzip.decompress(data)
    return decode_metadata(data)


def discover_packages_url(repository: Repository) -> str:
    release_url = urljoin(_dists_root(repository), "Release")
    release_text = decode_metadata(fetch_url(release_url, repository.user_agent))
    paths = parse_release_packages_paths(
        release_text, repository.component, repository.architecture
    )
    return urljoin(_dists_root(repository), best_packages_path(paths))


def read_records_from_text(text: str):
    return parse_packages(text)


def fetch_url(url: str, user_agent: str) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request) as response:
        return response.read()


def _dists_root(repository: Repository) -> str:
    root = repository.root if repository.root.endswith("/") else f"{repository.root}/"
    return urljoin(root, f"dists/{repository.distribution}/")
