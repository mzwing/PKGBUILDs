from __future__ import annotations

from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Replace ``path`` in one step, leaving no partial file behind on failure."""
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
