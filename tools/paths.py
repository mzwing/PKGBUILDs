"""The one place that knows where the repository root is."""

from __future__ import annotations

from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]
