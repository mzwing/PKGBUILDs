from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key


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
        fields = _parse_control_paragraph(paragraph)
        required = ("package", "version", "architecture", "filename", "sha256")
        if not all(fields.get(key) for key in required):
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
    candidates = [
        record
        for record in records
        if record.package == package and record.architecture in (architecture, "all")
    ]
    if not candidates:
        raise ValueError(
            f"package {package!r} for architecture {architecture!r} not found"
        )
    return max(candidates, key=cmp_to_key(_compare_package_records))


def select_record_by_version(
    records: list[PackageRecord],
    package: str,
    architecture: str,
    version: str,
) -> PackageRecord:
    candidates = [
        record
        for record in records
        if record.package == package
        and record.architecture in (architecture, "all")
        and record.version == version
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"expected one {package!r} record for {architecture!r} at "
            f"version {version!r}, found {len(candidates)}"
        )
    return candidates[0]


def arch_pkgver(debian_version: str) -> str:
    return debian_version.replace("-", "_")


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
            in_checksum_section = line[:-1] in {"SHA256", "SHA1", "MD5Sum"}
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

    return _dedupe(paths)


def best_packages_path(paths: list[str]) -> str:
    for path in paths:
        if path.endswith("Packages.gz"):
            return path
    for path in paths:
        if path.endswith("Packages"):
            return path
    raise ValueError("Release metadata did not list a Packages index")


def _split_paragraphs(text: str) -> list[list[str]]:
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _parse_control_paragraph(lines: list[str]) -> dict[str, str]:
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


def _compare_package_records(left: PackageRecord, right: PackageRecord) -> int:
    return compare_debian_versions(left.version, right.version)


def compare_debian_versions(left: str, right: str) -> int:
    left_epoch, left_upstream, left_revision = _split_debian_version(left)
    right_epoch, right_upstream, right_revision = _split_debian_version(right)

    if left_epoch != right_epoch:
        return (left_epoch > right_epoch) - (left_epoch < right_epoch)

    upstream_result = _compare_version_part(left_upstream, right_upstream)
    if upstream_result:
        return upstream_result
    return _compare_version_part(left_revision, right_revision)


def _split_debian_version(version: str) -> tuple[int, str, str]:
    if ":" in version:
        epoch_text, rest = version.split(":", 1)
        epoch = int(epoch_text)
    else:
        epoch = 0
        rest = version

    if "-" in rest:
        upstream, revision = rest.rsplit("-", 1)
    else:
        upstream = rest
        revision = "0"
    return epoch, upstream, revision


def _compare_version_part(left: str, right: str) -> int:
    left_index = 0
    right_index = 0

    while left_index < len(left) or right_index < len(right):
        while (left_index < len(left) and not left[left_index].isdigit()) or (
            right_index < len(right) and not right[right_index].isdigit()
        ):
            left_order = _version_char_order(
                left[left_index] if left_index < len(left) else ""
            )
            right_order = _version_char_order(
                right[right_index] if right_index < len(right) else ""
            )
            if left_order != right_order:
                return (left_order > right_order) - (left_order < right_order)
            if left_index < len(left):
                left_index += 1
            if right_index < len(right):
                right_index += 1

        while left_index < len(left) and left[left_index] == "0":
            left_index += 1
        while right_index < len(right) and right[right_index] == "0":
            right_index += 1

        left_digit_start = left_index
        right_digit_start = right_index
        while left_index < len(left) and left[left_index].isdigit():
            left_index += 1
        while right_index < len(right) and right[right_index].isdigit():
            right_index += 1

        left_digits = left[left_digit_start:left_index]
        right_digits = right[right_digit_start:right_index]
        if len(left_digits) != len(right_digits):
            return (len(left_digits) > len(right_digits)) - (
                len(left_digits) < len(right_digits)
            )
        if left_digits != right_digits:
            return (left_digits > right_digits) - (left_digits < right_digits)

    return 0


def _version_char_order(char: str) -> int:
    if char == "~":
        return -1
    if char == "":
        return 0
    if char.isalnum():
        return ord(char)
    return ord(char) + 256


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
