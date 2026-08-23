from __future__ import annotations

import io
import unittest
from pathlib import Path

import tomli_w

from tools.commands.sync_nvchecker import build_nvchecker_config
from tools.packages import Package


def make_package(name: str, check: dict | None = None) -> Package:
    return Package(
        name=name,
        directory=Path(name),
        check=check or {"source": "github", "github": f"so1ve/{name}"},
        updater_name="vcs",
        update={},
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

    def test_fills_in_the_command_for_cmd_sources(self) -> None:
        packages = {"deepin": make_package("deepin", {"source": "cmd"})}
        config = build_nvchecker_config(
            packages, interpreter="/venv/bin/python", cli_path="/repo/tools/cli.py"
        )
        self.assertEqual(
            config["deepin"]["cmd"],
            "/venv/bin/python /repo/tools/cli.py version deepin",
        )

    def test_keeps_an_explicit_command(self) -> None:
        packages = {
            "deepin": make_package("deepin", {"source": "cmd", "cmd": "echo 1"})
        }
        config = build_nvchecker_config(
            packages, interpreter="/venv/bin/python", cli_path="/repo/tools/cli.py"
        )
        self.assertEqual(config["deepin"]["cmd"], "echo 1")

    def test_does_not_mutate_the_package(self) -> None:
        package = make_package("deepin", {"source": "cmd"})
        build_nvchecker_config({"deepin": package}, interpreter="/p", cli_path="/c.py")
        self.assertNotIn("cmd", package.check)


if __name__ == "__main__":
    unittest.main()
