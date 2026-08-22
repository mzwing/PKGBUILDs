from __future__ import annotations

import io
import unittest
from pathlib import Path

import tomli_w

from tools.packages import Package
from tools.sync_nvchecker import build_nvchecker_config


def make_package(name: str) -> Package:
    return Package(
        name=name,
        directory=Path(name),
        check={"source": "github", "github": f"so1ve/{name}"},
        update={"updater": "vcs"},
    )


class SyncNvcheckerTest(unittest.TestCase):
    def test_header_first_then_sorted_packages(self) -> None:
        packages = {
            name: make_package(name) for name in ("xwayclip", "hfd-git", "serenity-bin")
        }
        buffer = io.BytesIO()
        tomli_w.dump(build_nvchecker_config(packages), buffer)
        self.assertEqual(
            buffer.getvalue().decode(),
            "[__config__]\n"
            'oldver = ".nvchecker/oldver.json"\n'
            'newver = ".nvchecker/newver.json"\n'
            "\n"
            "[hfd-git]\n"
            'source = "github"\n'
            'github = "so1ve/hfd-git"\n'
            "\n"
            "[serenity-bin]\n"
            'source = "github"\n'
            'github = "so1ve/serenity-bin"\n'
            "\n"
            "[xwayclip]\n"
            'source = "github"\n'
            'github = "so1ve/xwayclip"\n',
        )

    def test_output_is_deterministic(self) -> None:
        packages = {name: make_package(name) for name in ("b", "a", "c")}
        first = io.BytesIO()
        second = io.BytesIO()
        tomli_w.dump(build_nvchecker_config(packages), first)
        tomli_w.dump(
            build_nvchecker_config(dict(reversed(list(packages.items())))), second
        )
        self.assertEqual(first.getvalue(), second.getvalue())


if __name__ == "__main__":
    unittest.main()
