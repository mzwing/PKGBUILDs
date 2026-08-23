"""Debian version comparison (deb-version(7)).

Pure string algorithm with no repository or PKGBUILD knowledge.
"""

from __future__ import annotations


def compare_debian_versions(left: str, right: str) -> int:
    left_epoch, left_upstream, left_revision = split_version(left)
    right_epoch, right_upstream, right_revision = split_version(right)

    if left_epoch != right_epoch:
        return _sign(left_epoch - right_epoch)

    upstream_result = _compare_part(left_upstream, right_upstream)
    if upstream_result:
        return upstream_result
    return _compare_part(left_revision, right_revision)


def split_version(version: str) -> tuple[int, str, str]:
    """Split ``[epoch:]upstream[-revision]`` into its three components."""
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


def _compare_part(left: str, right: str) -> int:
    left_index = 0
    right_index = 0

    while left_index < len(left) or right_index < len(right):
        while (left_index < len(left) and not left[left_index].isdigit()) or (
            right_index < len(right) and not right[right_index].isdigit()
        ):
            left_order = _char_order(left[left_index] if left_index < len(left) else "")
            right_order = _char_order(
                right[right_index] if right_index < len(right) else ""
            )
            if left_order != right_order:
                return _sign(left_order - right_order)
            if left_index < len(left):
                left_index += 1
            if right_index < len(right):
                right_index += 1

        while left_index < len(left) and left[left_index] == "0":
            left_index += 1
        while right_index < len(right) and right[right_index] == "0":
            right_index += 1

        left_start = left_index
        right_start = right_index
        while left_index < len(left) and left[left_index].isdigit():
            left_index += 1
        while right_index < len(right) and right[right_index].isdigit():
            right_index += 1

        left_digits = left[left_start:left_index]
        right_digits = right[right_start:right_index]
        if len(left_digits) != len(right_digits):
            return _sign(len(left_digits) - len(right_digits))
        if left_digits != right_digits:
            return 1 if left_digits > right_digits else -1

    return 0


def _char_order(char: str) -> int:
    """Order letters before non-letters, and ``~`` before everything."""
    if char == "~":
        return -1
    if char == "":
        return 0
    if char.isalnum():
        return ord(char)
    return ord(char) + 256


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)
