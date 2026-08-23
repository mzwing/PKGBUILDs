from __future__ import annotations

import unittest

from tools.common.pkgbuild import (
    read_array,
    read_assignment,
    replace_array,
    replace_assignment,
    source_url,
)


class PkgbuildTextTest(unittest.TestCase):
    def test_reads_and_replaces_scalars(self) -> None:
        text = "_pkgver='1.0-beta'\npkgrel=2\n"
        self.assertEqual(read_assignment(text, "_pkgver"), "1.0-beta")
        self.assertEqual(
            replace_assignment(text, "pkgrel", "1", raw=True),
            "_pkgver='1.0-beta'\npkgrel=1\n",
        )

    def test_reads_array_literals_without_expanding_them(self) -> None:
        text = 'source=(\n    "a::$url/one"\n    "b::$url/two"\n)\n'
        self.assertEqual(read_array(text, "source"), ["a::$url/one", "b::$url/two"])

    def test_keeps_git_fragments_intact(self) -> None:
        text = 'source=("pkg::git+https://example.invalid/r.git#tag=v1")\n'
        self.assertEqual(
            read_array(text, "source"),
            ["pkg::git+https://example.invalid/r.git#tag=v1"],
        )

    def test_round_trips_through_replace_array(self) -> None:
        original = 'source=("old")\n'
        values = ["a::$url/one", "b::$url/two"]
        updated = replace_array(original, "source", values, expand_shell=True)
        self.assertEqual(read_array(updated, "source"), values)

    def test_source_url_drops_the_filename_prefix(self) -> None:
        self.assertEqual(
            source_url("LICENSE::https://example.invalid/LICENSE"),
            "https://example.invalid/LICENSE",
        )
        self.assertEqual(
            source_url("https://example.invalid/x.tar.gz"),
            "https://example.invalid/x.tar.gz",
        )

    def test_rejects_ambiguous_assignments(self) -> None:
        with self.assertRaises(ValueError):
            replace_assignment("pkgrel=1\npkgrel=2\n", "pkgrel", "3", raw=True)


if __name__ == "__main__":
    unittest.main()
