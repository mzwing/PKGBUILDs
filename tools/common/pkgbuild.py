"""Textual edits to PKGBUILD files.

Only the fields this repository manages are rewritten; everything else in the
file (comments, layout, build functions) is preserved byte for byte.
"""

from __future__ import annotations

import re
import shlex

_SAFE_VALUE = re.compile(r"^[A-Za-z0-9._+:-]+$")


def read_assignment(text: str, name: str) -> str:
    match = _assignment_pattern(name).search(text)
    if match is None:
        raise ValueError(f"missing PKGBUILD assignment: {name}")
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def replace_assignment(text: str, name: str, value: str, *, raw: bool = False) -> str:
    replacement_value = value if raw else _format_scalar(value)
    pattern = _assignment_pattern(name)
    updated, count = pattern.subn(f"{name}={replacement_value}", text)
    if count != 1:
        raise ValueError(f"expected one PKGBUILD assignment for {name}, found {count}")
    return updated


def replace_array(
    text: str,
    name: str,
    values: list[str],
    *,
    expand_shell: bool = False,
) -> str:
    pattern = _array_pattern(name)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"expected one PKGBUILD array assignment for {name}, found {len(matches)}"
        )

    quote = _double_quote if expand_shell else _single_quote
    if len(values) == 1:
        replacement = f"{name}=({quote(values[0])})"
    else:
        body = "\n".join(f"    {quote(value)}" for value in values)
        replacement = f"{name}=(\n{body}\n)"
    return pattern.sub(replacement, text, count=1)


def has_array(text: str, name: str) -> bool:
    return _array_pattern(name).search(text) is not None


def read_array(text: str, name: str) -> list[str]:
    """Return the literal (unexpanded) elements of an array assignment."""
    match = _array_pattern(name).search(text)
    if match is None:
        raise ValueError(f"missing PKGBUILD array assignment: {name}")
    body = match.group(0)[len(name) + 2 : -1]
    # `#` is not a comment here: git sources use `#tag=`/`#commit=` fragments.
    lexer = shlex.shlex(body, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def source_url(entry: str) -> str:
    """Return the URL of a source entry, dropping any ``filename::`` prefix.

    Splitting on the first ``::`` is safe: a URL scheme only ever contains a
    single colon before its slashes.
    """
    return entry.split("::", 1)[-1]


def _assignment_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(name)}=(.*)$", flags=re.MULTILINE)


def _array_pattern(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"^{re.escape(name)}=\(.*?\)(?=\n|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )


def _format_scalar(value: str) -> str:
    if _SAFE_VALUE.fullmatch(value):
        return value
    return _single_quote(value)


def _single_quote(value: str) -> str:
    if "'" in value:
        raise ValueError("single quote is not supported in managed PKGBUILD values")
    return f"'{value}'"


def _double_quote(value: str) -> str:
    if any(character in value for character in ('"', "`", "\\")):
        raise ValueError("unsupported character in expandable PKGBUILD array value")
    return f'"{value}"'
