"""Files this repository generates verbatim for every package."""

from __future__ import annotations

# Package directories are allow-lists: build artifacts from a local makepkg run
# are ignored without having to enumerate them.
PACKAGE_GITIGNORE = """**/*
!.SRCINFO
!.gitignore
!PKGBUILD
!update.toml
"""

# AUR repositories carry no update.toml -- that file is this repository's own
# bookkeeping.
AUR_GITIGNORE = """**/*
!.SRCINFO
!.gitignore
!PKGBUILD
"""
