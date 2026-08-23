"""Parsing and selection over Debian ``Packages`` control files."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key

from tools.debian.version import compare_debian_versions

_REQUIRED_FIELDS = ("package", "version", "architecture", "filename", "sha256")


@dataclass(frozen=True)
class PackageRecord:
    package: str
    version: str
    architecture: str
    filename: str
    sha256: str


def decode_metadata(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def parse_packages(text: str) -> list[PackageRecord]:
    records: list[PackageRecord] = []
    for paragraph in _split_paragraphs(text):
        fields = _parse_paragraph(paragraph)
        if not all(fields.get(key) for key in _REQUIRED_FIELDS):
            continue
        records.append(
            PackageRecord(
                package=fields["package"],
                version=fields["version"],
                architecture=fields["architecture"],
                filename=fields["filename"],
                sha256=fields["sha256"],
            )
        )
    return records


def select_latest_record(
    records: list[PackageRecord], package: str, architecture: str
) -> PackageRecord:
    candidates = _candidates(records, package, architecture)
    if not candidates:
        raise ValueError(
            f"package {package!r} for architecture {architecture!r} not found"
        )
    return max(candidates, key=cmp_to_key(_compare_records))


def select_record_by_version(
    records: list[PackageRecord],
    package: str,
    architecture: str,
    version: str,
) -> PackageRecord:
    candidates = [
        record
        for record in _candidates(records, package, architecture)
        if record.version == version
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"expected one {package!r} record for {architecture!r} at "
            f"version {version!r}, found {len(candidates)}"
        )
    return candidates[0]


def _candidates(
    records: list[PackageRecord], package: str, architecture: str
) -> list[PackageRecord]:
    return [
        record
        for record in records
        if record.package == package and record.architecture in (architecture, "all")
    ]


def _compare_records(left: PackageRecord, right: PackageRecord) -> int:
    return compare_debian_versions(left.version, right.version)


def _split_paragraphs(text: str) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _parse_paragraph(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in lines:
        if line.startswith((" ", "\t")):
            if current_key is not None:
                fields[current_key] = f"{fields[current_key]}\n{line}"
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.lower()
        fields[current_key] = value.strip()
    return fields
