"""Static REA annotation regression + self-contained stdio probe tests.

A mock process tests only the probe client; it is NOT a live DSHA/REA test.
"""
import sys
import unittest
from pathlib import Path

from mcp_stdio_smoke import ProbeError, inspect_server

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "skills/reverse-engineer-anything/tools/rea/bridge/android/ReaJadxBridge.java"

FAKE_MCP = r'''
import json, sys
for line in sys.stdin:
    msg = json.loads(line)
    if "id" not in msg:
        continue
    if msg["method"] == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "mock", "version": "1.0"}}
    elif msg["method"] == "tools/list":
        hints = {"readOnlyHint": True, "destructiveHint": False,
                 "idempotentHint": True, "openWorldHint": False}
        if "--drop-hint" in sys.argv:
            hints.pop("openWorldHint")
        result = {"tools": [{"name": "mock_status", "annotations": hints}]}
    else:
        raise SystemExit("unexpected method")
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
'''


class ReaAnnotationsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = JAVA.read_text(encoding="utf-8")

    def test_explicit_four_hints_in_tool_descriptor(self):
        self.assertIn("new ToolAnnotations(null, readOnly, destructive, idempotent, openWorld)", self.source)
        self.assertIn("new ToolAnnotations(null, true, false, true, false)", self.source)
        self.assertIn("original.getExecution(), original.getMeta()", self.source)

    def test_session_load_is_not_misrepresented_as_read_only(self):
        self.assertIn('withHints(server.getTools().get("load_apk").getTool(),', self.source)
        self.assertIn("false, true, false, false);", self.source)

    def test_upstream_readers_preserve_original_handlers(self):
        self.assertIn('List.of("get_app_info", "get_android_manifest")', self.source)
        self.assertIn("server.addTool(withHints(registered.getTool(), true, false, true, false),", self.source)
        self.assertIn("registered.getHandler());", self.source)

    def test_diagnostic_and_narrowed_tools_are_annotated(self):
        self.assertIn('Tool diagnostics = new Tool("rea_jvm_status"', self.source)
        self.assertIn('Tool narrowed = new Tool(name,', self.source)
        self.assertGreaterEqual(self.source.count("new ToolAnnotations(null, true, false, true, false)"), 2)

    def test_real_stdio_probe_protocol_with_mock_only(self):
        names = inspect_server([sys.executable, "-u", "-c", FAKE_MCP], timeout=5)
        self.assertEqual(names, ["mock_status"])

    def test_real_stdio_probe_rejects_missing_hint(self):
        with self.assertRaisesRegex(ProbeError, "openWorldHint"):
            inspect_server([sys.executable, "-u", "-c", FAKE_MCP, "--drop-hint"], timeout=5)


if __name__ == "__main__":
    unittest.main()
