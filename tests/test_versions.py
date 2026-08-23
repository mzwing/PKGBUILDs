from __future__ import annotations

import subprocess
import unittest

from tools.common.versions import TRANSFORMS, get_transform


class VersionTransformTest(unittest.TestCase):
    def test_python_and_shell_halves_agree(self) -> None:
        """Both halves of every transform must describe the same rewrite."""
        cases = {
            "identity": ("1.1.0-beta.3", "1.1.0-beta.3"),
            "hyphen_to_underscore": ("4.8.1-console2", "4.8.1_console2"),
            "remove_hyphen": ("1.1.0-beta.3", "1.1.0beta.3"),
        }
        self.assertEqual(set(cases), set(TRANSFORMS))
        for name, (raw, expected) in cases.items():
            transform = get_transform(name)
            self.assertEqual(transform.to_pkgver(raw), expected, name)
            self.assertEqual(
                _expand(transform.to_shell("_pkgver"), raw), expected, name
            )

    def test_unknown_transform_lists_supported_ones(self) -> None:
        with self.assertRaisesRegex(ValueError, "hyphen_to_underscore"):
            get_transform("nope")


def _expand(expression: str, value: str) -> str:
    result = subprocess.run(
        ["bash", "-c", f'_pkgver="$1"; printf "%s" "{expression}"', "expand", value],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


if __name__ == "__main__":
    unittest.main()
