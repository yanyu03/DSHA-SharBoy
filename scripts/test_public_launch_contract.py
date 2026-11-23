"""Public launch contract guards: assertions about source/docs, no installation."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicLaunchContracts(unittest.TestCase):
    def test_safe_default_and_validation(self):
        installer = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
        self.assertRegex(installer, r"\[string\]\$Tier\s*=\s*'read-only'")
        self.assertIn("[ValidateSet('read-only', 'workspace-write', 'danger-full-access', 'auto')]", installer)
        self.assertIn("if ($effectiveTier -eq 'danger-full-access')", installer)
        self.assertIn("Host native permissions", installer)

    def test_dry_run_before_any_write_and_prior_tier_snapshot(self):
        script = (ROOT / "install.ps1").read_text(encoding="utf-8-sig")
        dry = script.index("if ($WhatIfOnly) {")
        write = script.index('New-Item -ItemType Directory -Force -Path "$bak')
        self.assertLess(dry, write)
        prior = script.index("$previousTier = $null")
        self.assertLess(prior, script.index("robocopy (Join-Path $root 'plugins"))
        self.assertIn("$effectiveTier = if ($null -ne $previousTier)", script)

    def test_template_baseline_read_only(self):
        template = json.loads((ROOT / "plugins/dsh-permissions/tier.json").read_text(encoding="utf-8"))
        hooks = json.loads((ROOT / "plugins/dsh-permissions/hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(template["tier"], "read-only")
        self.assertTrue(hooks["dsh-permissions"]["enabled"])

    def test_release_not_misrepresented(self):
        main = (ROOT / "README.md").read_text(encoding="utf-8")
        english = (ROOT / "docs/README.en.md").read_text(encoding="utf-8")
        self.assertIn("V1.1", main)
        self.assertIn("V1.1", english)
        self.assertIn("main", english)
        self.assertIn("原生", main)
        self.assertIn("native", english)
        self.assertEqual(main.count("[![M8ven Verified]"), 1)

    def test_required_launch_docs_present(self):
        for path in [
            "docs/PUBLIC_LAUNCH_KIT.md", "docs/README.en.md",
            "docs/DEMO_60S.md", "docs/INSTALL_SAFETY.md"
        ]:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())
        demo = (ROOT / "docs/DEMO_60S.md").read_text(encoding="utf-8")
        self.assertIn("ERR_NO_MATCH", demo)
        self.assertIn("mock", demo)
        self.assertIn("录制尚未完成", demo)


if __name__ == "__main__":
    unittest.main()
