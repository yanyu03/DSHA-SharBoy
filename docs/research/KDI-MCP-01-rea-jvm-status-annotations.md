# KDI-MCP-01 — REA JVM status tool annotations: evidence checkpoint

**Checked:** 2026-11-03. **Branch:** `fatfish`. **Baseline:** `9532960b487345aa0a36716f2141930f2f922f1e`. **Scope:** one documentation-only investigation; no implementation or authorization change.

## Observed source facts

- `skills/reverse-engineer-anything/tools/rea/bridge/android/ReaJadxBridge.java` registers `rea_jvm_status` with `new Tool(..., null, null, null, null, null, null)`; the source does not supply explicit four MCP behavior hints.
- The handler for this name returns JSON containing `BuildInfo.VERSION`, JVM maximum heap, available processors, Java version and the literal metadata scope `parsed_members`. No file, network, or process mutation is visible **in this handler**. It runs before `session()`, so an APK is not required for this status path.
- The same Java bridge also replaces other tools with `new Tool(..., null, null, null, null, null, null)`. Thus a report saying “1/1 tools” is a scan-scope statement, **not evidence that every tool exposed by this bridge has been audited**.
- Source-level read-only behavior is not an authorization grant. DSHA's trusted tool registry and Gate must remain fail-closed, independent of MCP hints.

## Proposed behavior hints (not yet approved)

For the narrowly scoped `rea_jvm_status` tool only, `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=false` appear consistent with the handler's observed work. **Do not apply these values until verifying the exact Kotlin MCP SDK `Tool` constructor argument ordering, `ToolAnnotations` type, and serialized `tools/list` response.** No API compatibility assertion is established by the current static review.

## Evidence and gates

| Check | Result | Explanation |
| --- | --- | --- |
| Remote branch and Java handler read | PASS | Read at the baseline above |
| Local side effects in status handler | PASS (static scope only) | No explicit mutation observed in handler; not a process-wide proof |
| Exact SDK constructor / ToolAnnotations mapping | SKIP | SDK source/binary signature not yet inspected |
| Java compile and runtime `tools/list` JSON | SKIP | No verified bridge build/runtime in this iteration |
| Status/error-path behavior and Python/Windows/Linux regression | SKIP | No execution performed |
| OpenAI directory requirement for all four hints | UNVERIFIED | Third-party claim; do not treat as a normative requirement without official evidence |
| Merge/release readiness | BLOCKED | Required executable and compatibility gates remain open |

## Next isolated iteration

Locate the exact versioned `io.modelcontextprotocol.kotlin.sdk.types.Tool` and `ToolAnnotations` definitions used by the REA bridge, prove constructor and JSON serialization behavior, then add the smallest possible Java change on `fatfish`. Validate compilation, `tools/list` fields, read-only status output, error path and existing regressions. If no executable environment is available, retain SKIP and do not claim a fix.

**Rollback:** revert this documentation-only commit on `fatfish`; no changes to `main`, Gate, protocol `v1.2.0-std`, or PR #6 merge state.
