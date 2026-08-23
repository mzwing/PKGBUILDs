"""Updater for packages repackaged from a Debian apt repository."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from tools.common.fsutil import write_text_atomic
from tools.common.pkgbuild import read_assignment, replace_array, replace_assignment
from tools.debian.control import (
    PackageRecord,
    parse_packages,
    select_latest_record,
    select_record_by_version,
)
from tools.debian.repository import Repository, as_directory, load_packages_text
from tools.updaters.base import UpdateContext, Updater, reject_unknown, require

_KEYS = {
    "repo_root",
    "distribution",
    "component",
    "architecture",
    "package",
    "variable",
}


@dataclass(frozen=True)
class AptConfig:
    repository: Repository
    package: str
    variable: str


class AptUpdater(Updater[AptConfig]):
    name = "apt"

    def parse_config(self, package: str, raw: Mapping[str, Any]) -> AptConfig:
        reject_unknown(raw, _KEYS, package=package)

        def read(key: str) -> str:
            return require(raw, key, package=package)

        return AptConfig(
            repository=Repository(
                root=read("repo_root"),
                distribution=read("distribution"),
                component=read("component"),
                architecture=read("architecture"),
            ),
            package=read("package"),
            variable=read("variable"),
        )

    def latest_version(self, config: AptConfig) -> str:
        return select_latest_record(
            self._records(config), config.package, config.repository.architecture
        ).version

    def apply(self, context: UpdateContext, config: AptConfig) -> None:
        record = select_record_by_version(
            self._records(config),
            config.package,
            config.repository.architecture,
            context.newver,
        )
        original = context.pkgbuild.read_text()
        updated = update_pkgbuild_text(
            original, record, config.repository.root, config.variable
        )
        write_text_atomic(context.pkgbuild, updated)

    @staticmethod
    def _records(config: AptConfig) -> list[PackageRecord]:
        return parse_packages(load_packages_text(config.repository))


def update_pkgbuild_text(
    text: str, record: PackageRecord, repo_root: str, variable: str
) -> str:
    updated = replace_assignment(text, variable, record.version)
    if read_assignment(text, variable) != record.version:
        updated = replace_assignment(updated, "pkgrel", "1", raw=True)

    concrete_url = urljoin(as_directory(repo_root), record.filename)
    source_entry = concrete_url.replace(record.version, f"${{{variable}}}")
    filename = f"{record.package}_${{{variable}}}_{record.architecture}.deb"
    updated = replace_array(updated, "source", [source_entry], expand_shell=True)
    updated = replace_array(updated, "noextract", [filename], expand_shell=True)
    return replace_array(updated, "sha256sums", [record.sha256])
