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

## Follow-up checkpoint — SDK/build-path discovery (2026-11-03)

**Branch heads at inspection:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=1bf84fec0525d5a9f72323784e2fa5ee84c13cef`. PR #6 remains open and Draft; GitHub reports `mergeable=false` at this snapshot. The branches have diverged (fatfish 66 commits ahead, 8 behind), so an unconditional branch merge is not acceptable.

**Build and catalog distinction (verified from repository):** `bridge/android/` currently contains `ReaJadxBridge.java` only, and no `bridge/android/build.gradle.kts`. The REA `scripts/rea.mjs mcp` entrypoint launches the JavaScript production MCP runtime at `dist/mcp/main.js`, while `package.json` also ships `bridge/android/ReaJadxBridge.java`. Therefore a scan of the production MCP catalog must not be conflated with this separate Java bridge's `rea_jvm_status` registration. The correct SDK binary/compile path has **not** yet been established, so constructor position and actual serialized behavior remain **SKIP**, not PASS. Existing earlier CI runs are not evidence for the new fatfish HEAD.

**Next narrow test:** locate the bridge build invocation and the exact versioned `io.modelcontextprotocol.kotlin.sdk.types.Tool` binary (including `ToolAnnotations`); inspect its JVM constructor signature or source, compile the unchanged bridge first, and capture the bridge's own `tools/list` before editing. Only then consider a minimal annotation patch and rerun compile/runtime tests. Keep the Gate and protocol untouched.

## Follow-up checkpoint — SDK ownership and release separation (2026-11-03)

**Remote heads:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=c6649809c0bd61c4557a9b71545819b9eb72b212` before this documentation update. PR #6 remains open/Draft and reports `mergeable=false`. GitHub V1.1 Release exists for the Kaeru mainline; this does not validate the Java bridge on Fatfish.

**New source-level distinction:** `ReaJadxBridge.java` imports `com.atxx.jhmcp.*` for its upstream session integration, while MCP tool model classes come from `io.modelcontextprotocol.kotlin.sdk.types.*` and server classes from `io.modelcontextprotocol.kotlin.sdk.server.*`. The bridge's own header describes a metadata boundary for the unmodified `jadx-headless-mcp 0.7.1` JAR. **That 0.7.1 label is not proof of the Kotlin MCP SDK version or constructor signature**. The REA npm package's `mcpName` and `scripts/rea.mjs` entrypoint refer to the separate JavaScript server, not a validated Java bridge runtime. Consequently the four-hint patch must not be inferred from JavaScript server metadata.

**Evidence status:** source import/ownership and remote release separation PASS (static); exact Kotlin SDK artifact, Java compilation, bridge `tools/list` serialization, runtime behavior, and cross-platform regression SKIP. No permission, Gate, or protocol changes. **Next:** identify the actual `jadx-headless-mcp` JAR/classpath and inspect `Tool`/`ToolAnnotations` via `javap` or matching versioned source, then compile unchanged bridge before any annotations patch. **Rollback:** revert this documentation-only change; no branch merge or tag movement.

## Follow-up checkpoint — complete Git tree build-artifact inventory (2026-11-03)

**Read-only inventory baseline:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=6530ec1430fd866433f6cbe35c82ce0aa5f951f9`; PR #6 open/Draft and `mergeable=false`. The GitHub recursive tree API returned **2043 entries**, `truncated=false`. Across all tracked blobs, no `*.jar`, `pom.xml`, `build.gradle[.kts]`, `settings.gradle[.kts]`, `gradlew` or `mvnw` files were present; under `skills/reverse-engineer-anything/tools/rea/bridge/android/`, the only tracked file was `ReaJadxBridge.java`. This is evidence about **tracked repository files only**, not proof that users lack local JARs, external Gradle/Maven builds, or a CI download procedure. The bridge's upstream `jadx-headless-mcp` classpath and versioned Kotlin MCP SDK remain unresolved. The mainline V1.1 release is not a substitute for Java bridge compilation.

**Gate:** repository-wide tracked build-artifact inventory PASS; exact SDK binary signature, Java compile, bridge `tools/list`, error paths and Windows/Linux runtime SKIP; merge/release for Fatfish BLOCKED. **Next:** obtain an authoritative upstream artifact coordinate and pinned digest from build documentation or external upstream, then inspect `Tool`/`ToolAnnotations` signatures via `javap` and compile the unchanged bridge. Do not add guessed annotations. **Rollback:** revert this documentation-only commit after verifying current `fatfish` HEAD; no changes to `main`, Gate or protocol.

## Follow-up checkpoint — upstream v0.7.1 Gradle provenance (2026-11-03)

**Read-only baseline:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=34b06ec77b076abd063e601243109c85c5167af9`; PR #6 remains open/Draft, `mergeable=false`. The most recent visible Fatfish workflow success was for an older commit (`123fd05e19ba...`), not the current HEAD; it does not validate this bridge.

**New independently located upstream evidence:** GitHub repository [1013503897/jadx-headless-mcp](https://github.com/1013503897/jadx-headless-mcp) has an existing annotated `v0.7.1` tag ([tag ref](https://github.com/1013503897/jadx-headless-mcp/tree/v0.7.1)); its [version-pinned build.gradle.kts](https://github.com/1013503897/jadx-headless-mcp/blob/v0.7.1/build.gradle.kts) explicitly declares `group=com.atxx`, `version=0.7.1`, `io.modelcontextprotocol:kotlin-sdk:0.15.0`, `jadx=1.5.6`, `Ktor=3.5.1`, Kotlin plugin `2.4.10` and JVM toolchain 17. This provides a **specific candidate upstream build coordinate and SDK version**, rather than inferring them from the Java bridge's comment. The tag is an annotated tag pointing to Git tag object `4585a943c5769253c56d897e432d16478b34d4d1`; Gradle file blob SHA is `377ec590a97238aee3ee208c45e3568be0d59439`.

**Important provenance limitation:** The REA Java bridge's comment mentions an *unmodified* upstream 0.7.1 JAR, but no vendored binary or checksum ties any user's actual JAR to this tag. Do not claim the local binary is identical or that `ToolAnnotations` JVM constructor mapping is now verified. Next: resolve the tagged commit and a verifiable release artifact/digest, inspect Kotlin MCP SDK 0.15.0 `Tool` and `ToolAnnotations` via matching source or `javap`, compile the original bridge with a pinned classpath, and capture bridge `tools/list`. No guessed Java patch or Gate change.

**Checks:** upstream tag and pinned Gradle source PASS; actual JAR identity, Kotlin SDK constructor and serializer, Java compilation, MCP runtime and Windows/Linux regressions SKIP; Fatfish merge gate BLOCKED. **Rollback:** revert this documentation-only update after checking the current `fatfish` HEAD.

## Follow-up checkpoint — pinned Kotlin MCP SDK 0.15.0 source signature (2026-11-03)

**Read-only baseline:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=928595cff9912adb3760cdb7726bcd4f6e5f6081`; PR #6 remains Draft and unmergeable. This checkpoint inspects upstream **source**, not a verified runtime binary.

**Pinned SDK provenance:** [modelcontextprotocol/kotlin-sdk tag `0.15.0`](https://github.com/modelcontextprotocol/kotlin-sdk/tree/0.15.0) resolves to commit `76b8e7d63aac39fe41e03684e3b91a6c3724a8da`. Its [`kotlin-sdk-core/.../types/tools.kt`](https://github.com/modelcontextprotocol/kotlin-sdk/blob/0.15.0/kotlin-sdk-core/src/commonMain/kotlin/io/modelcontextprotocol/kotlin/sdk/types/tools.kt) defines `Tool(name, inputSchema, description, outputSchema, title, annotations, icons, execution, meta)` and `ToolAnnotations(title: String? = null, readOnlyHint: Boolean? = null, destructiveHint: Boolean? = null, idempotentHint: Boolean? = null, openWorldHint: Boolean? = null)`, both annotated `@Serializable`. The tracked Fatfish Java `new Tool(...)` passes `null` in the sixth position (annotations), consistent with the M8ven missing-hints observation. The actual Java/JVM overload and ABI compatibility remain **unverified** until the pinned SDK JAR is inspected with `javap` or compiled against it.

**Handler evidence:** `rea_jvm_status` returns `BuildInfo.VERSION`, JVM max heap, available processors, `java.version` and `metadata_scope`; it does not explicitly mutate application state or contact external services. This supports a **candidate** readOnly=true, destructive=false, idempotent=true, openWorld=false, but the SDK's documentation treats destructive/idempotent hints as relevant primarily for non-read-only tools. Treat these values as a hypothesis, not an approved patch or proof of security. Annotations are descriptive and cannot authorize operations or bypass the DSHA Gate.

**Checks:** versioned SDK tag and source declaration PASS; source handler and constructor argument position PASS (static); actual binary provenance, Java constructor ABI, `tools/list` serialization, unchanged bridge compilation, runtime/error-path and Windows/Linux regression SKIP. **Merge gate BLOCKED.** Next: resolve exact SDK 0.15.0 artifacts and compile the unchanged bridge before a single-tool patch. **Rollback:** revert this documentation-only commit; no runtime or protocol changes.

## Follow-up checkpoint — MCP list serialization source contract (2026-11-04)

**Read-only branch snapshot:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=09ae90d52f8737d6d0252882ffbc0dafd3c37711` before this update. PR #6 remains open/Draft and reports `mergeable=false`. The latest inspected successful Fatfish CI run targets an older commit (`123fd05e19ba...`), not this HEAD.

**New narrow source-level result:** The pinned [Kotlin SDK 0.15.0 `tools.kt`](https://github.com/modelcontextprotocol/kotlin-sdk/blob/0.15.0/kotlin-sdk-core/src/commonMain/kotlin/io/modelcontextprotocol/kotlin/sdk/types/tools.kt) declares `@Serializable data class ListToolsResult(val tools: List<Tool>, ...)`, `@Serializable data class Tool(..., val annotations: ToolAnnotations? = null, ...)`, and `@Serializable data class ToolAnnotations(..., val readOnlyHint: Boolean? = null, val destructiveHint: Boolean? = null, val idempotentHint: Boolean? = null, val openWorldHint: Boolean? = null)`. Therefore the **source-level intended wire location** of the four booleans is nested under `tools[i].annotations`, not four top-level properties on `tools[i]`. The current bridge passes `null` at the `Tool.annotations` position, so it cannot supply explicit values through that constructor argument. This is a static contract check, **not** a captured `tools/list` payload; Kotlin serialization configuration may affect null/default omission, and binary compatibility is still untested.

**Build artifact blocker:** This execution environment could not resolve `repo.maven.apache.org` (DNS lookup failed). No version-matched SDK JAR was retrieved, no digest or `javap` signature was verified, and no Java bridge compilation was attempted. Do not treat source declarations as a substitute for JVM ABI proof. This is an environment/network blocker, not a failed test of the code.

**Checks:** source declarations and intended nested JSON field path PASS (static); artifact provenance, JVM ABI, actual `tools/list` payload, bridge compilation, runtime/error-path, Python/Windows/Linux regression SKIP. **Merge/release BLOCKED.** Next: obtain the version-pinned JVM artifact via an accessible trusted source, verify its checksum and constructor with `javap`, compile the unmodified Java bridge, then capture real `tools/list`. Do not add guessed hints or weaken Gate. **Rollback:** revert this documentation-only commit after checking the latest branch SHA; `main` and `v1.2.0-std` remain untouched.


## Follow-up checkpoint — upstream v0.7.1 release artifact provenance (2026-11-04)

**Pre-write remote heads:** `main=5ef66ae6bd001b5038dd743ae9b9b1e7d6d30a4b`, `fatfish=a8de8cd7bcc6cd2043461cd29a3dc38e89224a9b`. PR [#6](https://github.com/yanyu03/DSHA-SharBoy/pull/6) remains open/Draft, `mergeable=false`, `mergeable_state=dirty`; its returned base SHA `e24abe7d4e7fa6a82967af8972de0e11bf6cf5d4` differs from the independently fetched current main ref. Do not treat stale PR metadata as proof of an up-to-date merge base. The current Fatfish commit status endpoint returned no status contexts (`pending`); the latest observed successful workflow run was for older SHA `123fd05e...`, not current HEAD.

**New verified provenance:** GitHub's [upstream v0.7.1 Release API](https://api.github.com/repos/1013503897/jadx-headless-mcp/releases/tags/v0.7.1) lists the following assets, published 2026-09-18 06:16:12 UTC:

| Release asset | Reported size | GitHub asset digest (SHA-256) |
| --- | ---: | --- |
| [jadx-headless-mcp-0.7.1-all.jar](https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp-0.7.1-all.jar) | 42,619,858 bytes | `6e5eacf500b64292bfb73c49797c1958f6ee44646e43e868039ae7feb573ff75` |
| [jadx-headless-mcp-0.7.1.zip](https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp-0.7.1.zip) | 39,114,881 bytes | `f7246667a35de234d20f5503b8593462b8003eb9a23830e4fb6f53d9f12b5e6d` |
| [jadx-headless-mcp.sha256](https://github.com/1013503897/jadx-headless-mcp/releases/download/v0.7.1/jadx-headless-mcp.sha256) | 98 bytes | `e50e16d97c5892805b7c279ca9fbd41b0468ea43af13b7e4691b179f30d0f93b` |

These are **publisher-hosted GitHub asset metadata digests**, not hashes independently calculated from downloaded bytes, nor a signature attesting to trust. No binary was downloaded, compiled, executed, or linked to a user's local JAR in this iteration. The SHA-256 of the checksum *file* is not the checksum value inside that file.

**Next independent verification:** download the specific JAR in a controlled build environment, calculate `sha256sum jadx-headless-mcp-0.7.1-all.jar` (or Windows `Get-FileHash -Algorithm SHA256`), compare with the digest above, inspect embedded `Tool`/`ToolAnnotations` using `javap`, compile the unmodified REA bridge against that exact artifact, then capture the Java bridge's actual `tools/list`. Do not infer ABI compatibility merely from upstream Gradle source.

**Gates:** release asset metadata and digest provenance PASS; independently hashed artifact, ABI, bridge compilation, MCP runtime, Python/Windows/Linux regression SKIP. PR merge/release BLOCKED. **Rollback:** revert only this documentation update on fatfish. No code, protocol, Gate, main, tags, or other branches modified.
