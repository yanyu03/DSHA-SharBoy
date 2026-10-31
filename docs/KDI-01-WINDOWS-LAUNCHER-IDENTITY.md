# KDI-01 / Windows .cmd launcher identity: Stage 5→6 design gate

> Status: DESIGN ONLY / NOT IMPLEMENTED / NOT SECURITY-APPROVED  
> Branch: `fatfish` exclusively; PR: #6 (Draft)  
> Protocol: DSHA private `v1.2.0-std` (unchanged)  
> Baseline: `b43df4ac0bee4df9bdc06c5eac3c3cbaf587de94`  
> Scope: Windows batch launchers only; no changes to Gate, request/response/receipt, seven stages, or other branches.

## Observed baseline (not a proposed guarantee)

- `scripts/base_tool.py` resolves an executable path and applies `assert_target_contained(exec_path)` in Stage 5, then constructs a command list and calls `subprocess.run(...)` in Stage 6. The executable is **not bound to an already-validated file object**.
- The Windows negative integration test `test_launcher_replacement_after_stage5_is_not_yet_blocked` is marked `expectedFailure`; CI reproduced `stage5=PASS, receipt=PASS, replacement_executed=True` ([run 40798784353](https://github.com/yanyu03/DSHA-SharBoy/actions/runs/40798784353)).
- The independent feasibility test `test_windows_read_handle_blocks_launcher_mutation` uses `CreateFileW(GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING)`; Windows CI confirmed the tested in-place rewrite and `os.replace` were denied, and a read-only `cmd.exe /d /c` invocation still ran ([run 40855606898](https://github.com/yanyu03/DSHA-SharBoy/actions/runs/40855606898)). This is **not** a production fix or a general identity guarantee.

## Threat model and required invariant

Assume a local actor can change files in a launcher directory during the Stage 5→6 interval. A successful Stage 5 path check must not be treated as proof that Stage 6 executes the same file bytes. The desired invariant is: **the launched batch content corresponds to the object validated under the trusted-root policy, or execution is refused**. Path-string equality, a second hash, or an earlier `Path.resolve()` check alone cannot establish this invariant.

`.cmd` is interpreted by `cmd.exe`; Windows does not expose a direct `CreateProcess`-from-file-handle path for executing batch contents. Keeping a handle to the original batch file does not automatically force `cmd.exe` to read that handle rather than reopen a pathname. Handle-sharing behavior is a mitigation candidate, not proof of handle-to-child identity binding.

## Candidate A: acquire/validate/hold (first isolated prototype only)

1. Resolve a candidate without trusting it. Open its file handle **before** accepting the Stage 5 decision, requesting read access and disallowing write/delete sharing. If opening fails, the opt-in prototype must refuse, not silently fall back.
2. Obtain canonical path and stable file identity from the opened handle (e.g. `GetFinalPathNameByHandleW` plus volume/file ID where available). Validate trusted-root containment against the handle-derived target, not only the original string. Define handling of reparse points, junctions, hard links and inaccessible metadata before production use.
3. Retain the handle across the entire child launch and completion, including timeout/error paths; close it in `finally`. Preserve existing Stage 4 authorization and Stage 5 refusal semantics; do not weaken them.
4. Test whether directory renames, reparse-point changes, alternate path aliases, or a pre-existing writable handle can redirect the pathname that `cmd.exe` actually opens. A blocked direct file rewrite is **insufficient**. If any redirect works, reject Candidate A as a complete mitigation.
5. Do not change default `BaseTool.execute()` or the mirrored plugin implementation until native Windows positive/negative tests and Linux regressions pass.

## Candidate B: verified private snapshot (fallback to evaluate separately)

Read the validated file into a uniquely named, access-controlled staging location, verify that the bytes being launched are the bytes reviewed, and launch that snapshot instead of the mutable original path. The staging directory must have enforced ACL ownership and secure creation/cleanup. This may change batch semantics (`%~dp0`, relative paths, sibling resources, signatures and launcher discovery), so it is **not** automatically backward compatible. It requires its own compatibility study and cannot be silently enabled.

## Junction/reparse-point trust-boundary decision (KDI-01 Round 21; design only)

**Evidence:** The Windows temporary-directory experiment `test_junction_alias_retarget_under_held_launcher_handle` observed `capable=True, retargeted=True, redirected=True` while an original launcher read handle remained open ([Windows/Linux CI run 40938799893](https://github.com/yanyu03/DSHA-SharBoy/actions/runs/40938799893), [test commit 09c93e60](https://github.com/yanyu03/DSHA-SharBoy/commit/09c93e605f56686b271bea6b75e2aa674658f3c9)). This demonstrates a **candidate-A design bypass in the fixture**, not exploitation of a deployed trusted root. The test passing means the observation was reproduced, not that the security property passed.

**Current code boundary:** In `scripts/base_tool.py`, `resolve_executable()` may return a path string; `assert_target_contained()` calls `Path(exec_path).resolve()` and checks it against resolved built-in roots (`bin/`, `~/.gemini/config/`) or configured extension roots. Stage 6 still launches the resolver's `exec_path` pathname with `subprocess.run()`. The mirrored `plugins/dsh-permissions/scripts/base_tool.py` must retain the same semantics. A junction targeting an external directory *at the instant of resolution* can fail containment, but a trusted-looking alias can be retargeted after Stage 5; `Path.resolve()` is not an identity binding.

**Proposed fail-closed constraint for a future opt-in Windows hardened mode (NOT implemented):**

1. Treat any junction, symlink or other reparse point in the complete path chain from the volume root through each trusted-root ancestor to the launcher as an **untrusted alias**. Reject the launch when any component is a reparse point, inaccessible, ambiguous, or cannot be inspected reliably; do not silently fall back to ambient PATH or legacy launching in hardened mode. Windows file attributes/reparse tags must be examined without following the alias when deciding whether a component is itself a reparse point.
2. This component policy is a **necessary screening condition, not a sufficient TOCTOU fix**: a check followed by pathname reopening remains racy. Production acceptance also requires a demonstrable binding between the object validated and the bytes consumed by `cmd.exe`, or a securely created immutable private snapshot with compatible invocation semantics. If neither can be established, refuse rather than claim isolation.
3. Keep existing default and legacy extension behavior unchanged until explicit compatibility review. Do not alter Stage 4 permission Gate, Stage 5 error code/receipt semantics, seven-stage lifecycle, or `v1.2.0-std`. Reparse-aware hardening must not silently disable supported installations using symlinks or junctions.
4. Before any production patch, independently test direct trusted launcher acceptance; junctions inside and outside trusted roots; retargeting after validation; reparse metadata access failure; cleanup and error paths; and unchanged Linux regression. A refusal should retain `ERR_TARGET_OUTSIDE_SANDBOX`/Stage 5 semantics only where the refusal is a containment-policy decision. Preserve the existing Windows TOCTOU XFAIL until an actual security assertion passes.

**Decision:** Candidate A (read-handle lock alone) is **rejected as a complete mitigation**. No production patch or security PASS claim is authorized by this document. Next independent change should be a Windows-only isolated negative test of reparse-component fail-closed classification, without changing the default execution path.

## Minimum acceptance gate before any production patch

- Windows: real trusted `scribe.cmd` positive execution and seven-stage receipt still pass.
- Windows: post-Stage-5 replacement is prevented or refused; the existing TOCTOU `XFAIL` becomes an ordinary **PASS** only when the negative assertion succeeds without `expectedFailure`.
- Windows: test parent-directory rename/path redirection and reparse-point/alias behavior while a handle is held; test error and timeout cleanup. Do not infer results before running these tests.
- Linux: Stage 5 focused regression and full runtime contract suite remain green; platform-specific guard does not change Linux execution.
- Both mirrored `base_tool.py` implementations remain consistent if production code eventually changes; protocol `v1.2.0-std`, permission Gate, `DSHARequest`, `DSHAResponse`, `TraceReceipt` and seven-stage lifecycle remain compatible.
- CI logs and branch HEAD are verified before any security PASS claim. No OS-level sandbox claim.

## Decision and rollback

**Decision: no production implementation.** The parent-directory and junction experiments now show why file-handle locking alone cannot establish launcher identity. Follow the Round 21 fail-closed design gate above; the next independent step is an isolated Windows reparse-component classification test, not a runtime change. This design note can be reverted by a single non-force commit on `fatfish` after checking the latest remote HEAD. Do not merge PR #6 automatically.
