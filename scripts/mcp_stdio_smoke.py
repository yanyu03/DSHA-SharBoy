#!/usr/bin/env python3
"""Probe a REAL stdio MCP server's initialize/tools/list contract (stdlib only).

This script does not create a substitute DSHA server or execute any tools.
Provide the server's existing start command after "--".
"""
import argparse
import json
import queue
import subprocess
import sys
import tempfile
import threading
import time

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
PROTOCOL_VERSION = "2025-06-18"


class ProbeError(Exception):
    pass


def inspect_server(command, timeout=20.0):
    if not command:
        raise ProbeError("Specify the actual MCP server command after '--'")
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as error_log:
        try:
            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=error_log, bufsize=0,
            )
        except OSError as exc:
            raise ProbeError(f"Server could not start: {exc}") from exc
        received = queue.Queue()

        def reader():
            try:
                for raw in proc.stdout:
                    received.put(raw)
            finally:
                received.put(None)

        threading.Thread(target=reader, daemon=True).start()
        request_id = 0

        def send(message):
            try:
                proc.stdin.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
                proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise ProbeError("Server exited before accepting an MCP message") from exc

        def request(method, params=None):
            nonlocal request_id
            request_id += 1
            current_id = request_id
            payload = {"jsonrpc": "2.0", "id": current_id, "method": method}
            if params is not None:
                payload["params"] = params
            send(payload)
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeError(f"Timed out waiting for {method}")
                try:
                    raw = received.get(timeout=remaining)
                except queue.Empty as exc:
                    raise ProbeError(f"Timed out waiting for {method}") from exc
                if raw is None:
                    raise ProbeError(f"Server closed stdout during {method} (exit={proc.poll()})")
                try:
                    response = json.loads(raw)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ProbeError("Server emitted non-JSON data on stdout") from exc
                if response.get("id") != current_id:
                    if "id" in response:
                        raise ProbeError("Server returned an unexpected request ID")
                    continue  # MCP notification, not a response
                if "error" in response:
                    raise ProbeError(f"Server rejected {method}: {response['error']}")
                if not isinstance(response.get("result"), dict):
                    raise ProbeError(f"Invalid MCP result for {method}")
                return response["result"]

        try:
            init = request("initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "dsha-mcp-contract-probe", "version": "1.0"},
            })
            if not isinstance(init.get("capabilities"), dict):
                raise ProbeError("initialize result has no capabilities object")
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            names = set()
            cursor = None
            while True:
                params = {"cursor": cursor} if cursor is not None else {}
                page = request("tools/list", params)
                tools = page.get("tools")
                if not isinstance(tools, list):
                    raise ProbeError("tools/list returned no tool array")
                for tool in tools:
                    if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                        raise ProbeError("tools/list contains an invalid tool")
                    name = tool["name"]
                    if not name or name in names:
                        raise ProbeError(f"Empty or duplicate MCP tool name: {name!r}")
                    names.add(name)
                    hints = tool.get("annotations")
                    if not isinstance(hints, dict):
                        raise ProbeError(f"{name}: missing annotations object")
                    missing = [key for key in HINTS if type(hints.get(key)) is not bool]
                    if missing:
                        raise ProbeError(f"{name}: missing/non-boolean hints: {', '.join(missing)}")
                cursor = page.get("nextCursor")
                if cursor is None:
                    break
                if not isinstance(cursor, str) or not cursor:
                    raise ProbeError("Invalid tools/list pagination cursor")
                if len(names) > 10000:
                    raise ProbeError("Unbounded tools/list pagination")
            if not names:
                raise ProbeError("MCP server exported no tools")
            return sorted(names)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            proc.stdin.close()
            proc.stdout.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        if not 0 < args.timeout <= 300:
            raise ProbeError("timeout must be in (0, 300] seconds")
        names = inspect_server(command, args.timeout)
    except ProbeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {len(names)} MCP tools have all four boolean hints: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
