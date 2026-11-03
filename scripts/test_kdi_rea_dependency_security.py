"""Guard the vendored REA Zod dependency against GHSA-mrhx-c7xc-m3w5 regression."""
import json
from pathlib import Path
import unittest


class ReaDependencySecurityTests(unittest.TestCase):
    def test_zod_pin_is_patched(self):
        manifest = (Path(__file__).resolve().parents[1] / "skills" /
                    "reverse-engineer-anything" / "tools" / "rea" / "package.json")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["dependencies"]["zod"], "4.6.6")


if __name__ == "__main__":
    unittest.main()
