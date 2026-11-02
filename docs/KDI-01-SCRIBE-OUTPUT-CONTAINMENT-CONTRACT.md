# KDI-01 / Scribe dossier output containment contract (design only)

Status: **PROPOSED / NOT ENFORCED** · Scope: `fatfish` P01/P04 security boundary · Baseline: `a3cd90e0bef23e34732c620452466d7a53dcfcea` · DSHA private protocol: `v1.2.0-std` unchanged.

## Evidence and threat model

- At this baseline, `scripts/scribe.py` parses `dossier --out PATH` and directly invokes `out_p.parent.mkdir(...)` followed by `open(out_p, "w", ...)`; `plugins/dsh-permissions/scripts/scribe.py` is a second Scribe implementation and must be assessed before a runtime change.
- `scripts/test_runtime_contracts.py::RuntimeContractTests.test_scribe_dossier_out_outside_repo_currently_accepted` reproduces the current external-absolute-path acceptance with mocked writes. This is a **known failing security boundary**, even though the reproduction test passes.
- Scribe's tool-level `RiskLevel.MEDIUM` prevents use under the DSHA read-only tier; it does **not** constrain file destinations under a write-capable tier.
- `harvest` and `status` also write `.scribe/latest_harvest.json`. This contract's first implementation slice concerns only **`dossier --out`**; it must not be described as a general Scribe filesystem sandbox.

## Compatibility decision

1. Introduce a **trusted, opt-in managed-output policy** for the DSHA-managed Scribe entrypoint before enforcing it by default. Do not silently change the existing standalone `scribe.py dossier --out` CLI contract in this first slice.
2. The trusted output root must come from an administrator-controlled registration/configuration, **not** the model's JSON arguments, `DSHARequest.context`, arbitrary environment variables, or caller-controlled working directory. A model cannot nominate or enlarge its own trusted root.
3. Under the managed policy, `--out` is interpreted as a **relative path beneath a configured export root** (proposed default: `<repo>/.scribe/exports`). The existing no-`--out` cache behavior remains separate. Explicit absolute paths, including absolute paths *inside* the root, are rejected in the first slice to avoid cross-platform ambiguity.
4. For the initial implementation, fail closed on all ambiguous cases. No implicit fallback to legacy unrestricted output when policy validation fails. The standalone legacy path must remain clearly documented as **uncontained**, not as a security guarantee.
5. Never change `DSHARequest`, `DSHAResponse`, `TraceReceipt`, stage numbering, or the permission Gate to carry output-path policy. The trusted policy is an internal, opt-in execution configuration.

## Trusted host root registration (design-only)

The following **host-side trust preconditions are proposed, not enforced** by `scripts/kdi_scribe_output.py`. The previous rename and replacement tests show that a pre-opened directory fd pins an inode but cannot prove its original pathname is stable. `fstat()` identity equality alone is not a containment guarantee.

1. **Authority and lifetime.** Only a host administrator or trusted bootstrap may register an absolute canonical export root, the expected owner/service identity and permitted output policy. Register before processing untrusted requests and freeze the registration for that process lifetime. Reject missing, changed or unverifiable registrations. Do not accept roots, descriptors, ownership claims or policy overrides from model JSON, `DSHARequest.context`, argv, arbitrary environment variables or caller-controlled `cwd`. Standalone legacy CLI remains explicitly uncontained.
2. **POSIX registration evidence.** Traverse from a trusted host-owned anchor with directory-relative, no-follow opens; record `(st_dev, st_ino, st_uid, st_mode)` for the root and relevant ancestors. Require an administrator-approved root owner (such as root or a dedicated service identity). Compare opened directory identities with registration on use; reject mismatches. These checks alone do **not** prevent renames, bind-mount substitution or concurrent mutation.
3. **Ancestor mutation boundary.** Every parent whose directory entries can rename or replace the root or a descendant must be protected from adversarial writes. Conservatively reject group/world-writable ancestors unless an independently audited trust policy proves every principal with effective mutation rights is trusted. Sticky-bit directories do not automatically establish this guarantee. The export root can be service-writable to create files, but untrusted writers must not be able to replace its directory components.
4. **Effective permissions, not mode bits alone.** Account for effective UID/GID, supplementary groups, POSIX ACLs, capabilities, privileged actors, user/mount namespaces and shared service identities. An owner/mode-only check is not sufficient evidence against these actors. If effective mutation rights cannot be audited, managed output must fail closed; do not call it an OS sandbox.
5. **Inode vs pathname.** A trusted pre-opened fd prevents subsequent name substitution from changing the fd's target, but cannot prevent the inode being moved elsewhere. Stable pathname containment additionally requires non-adversary-mutable ancestors and mount topology. A post-open string check does not repair TOCTOU. If the attacker can rename parents, alter mounts or act as the trusted service identity, pathname containment is unproven.
6. **Windows remains unsupported.** POSIX owner/mode rules do not substitute for Windows ACL effective access, reparse-point/junction handling and verified native handle-relative opens. Continue rejecting Windows managed writes until a separate Windows design and tests pass.

## Effective-rights audit and registration proof (design-only)

This section defines the **next trust decision**, not a permission grant or a deployed verifier. The current `inspect_posix_root_mode_preconditions()` returns owner/mode evidence only; `open_managed_output()` does not consume that evidence. Neither function may claim effective-rights containment.

**Authority separation.** A trusted host bootstrap, outside the model-controlled request path, owns a process-local `TrustedRootRegistration`. The model may supply only the relative output filename. The bootstrap selects a pre-opened root directory handle, approved service identity, trusted principal set, policy revision, and an independently audited enforcement environment. Never deserialize a registration, proof, root fd, allowed UID list, audit status or override from `DSHARequest`, `context`, argv, caller environment or working directory. A signature on caller-supplied JSON alone is not an authorization boundary.

**Proposed evidence envelope (internal only, no protocol/schema changes):**

| Evidence field | Requirement / reason |
| --- | --- |
| `registration_id`, `policy_revision`, `issuer` | Opaque process-local identity; issuer must be the trusted bootstrap, not the caller |
| `root_handle`, `root_identity` | Pre-opened handle and `(st_dev, st_ino)` identity; never accept a pathname re-open as equivalent |
| `ancestor_identities` | Ordered `(st_dev, st_ino, st_uid, st_mode)` observations from a trusted anchor; detect replacement, not rename safety |
| `service_identity`, `trusted_principals` | Effective UID/GID, supplementary groups and explicitly authorized principals; account for privilege escalation |
| `effective_rights_audit` | Named trusted audit backend, scope, observed ACL/default ACL, mutation-capable principals, verdict and evidence digest |
| `mount_context`, `enforcement_claim` | Namespace/mount identity and independently enforced restrictions on rename, mount and identity changes |
| `issued_at`, `validity_scope`, `revocation_state` | Limit evidence reuse to the registered process/handle and unchanged enforcement context; time alone cannot prevent races |

**Registration decision:** return **REFUSE** unless every applicable ancestor and export directory has verifiable effective mutation rights limited to approved principals, the opened root identity matches the trusted registration, and the host can enforce the required stability of parent entries and mount topology for the entire open/write operation. An ACL or capability audit returning *unknown*, missing namespace visibility, unsupported filesystem semantics, a changed handle/identity, stale evidence, revocation or an untrusted issuer is **REFUSE**, not `mode-only PASS`. Do not treat `os.access()`, `st_mode`, `fstat()`, a short expiry, or an after-the-fact path comparison as sufficient.

**Trust model limit:** if an adversary can act as an approved principal, modify an ancestor's directory entries, change the mount namespace, or race the trusted bootstrap, path-name containment is unproven. A host with no independently verified effective-rights auditor and enforcement mechanism must not issue an affirmative registration. A process-local proof is an audit artifact, **not** a cryptographic or OS sandbox guarantee.

**Future isolated verification matrix:** positive issuance only with a controlled trusted host and enforceable parent stability; negative tests for forged caller proof, unknown ACL backend, group/ACL write access, root inode substitution, namespace/mount changes, expired/revoked evidence and root rename after registration. Windows continues fail-closed until a separate native ACL/handle implementation is verified. Do not connect to production Scribe, Router or Gate on the strength of this document.

**Required later tests (not run here):** positive trusted-parent registration; rejection of attacker-writable parents, substituted root identities and untrusted registry inputs; preservation of existing root-rename/replacement reproductions as known failing security boundaries; Linux and Windows regression before production integration. Passing a vulnerability-reproduction test is **not** passing the containment requirement.

## Proposed validation contract (not implemented)

For managed `dossier --out`:
- Accept only a nonempty relative string without NUL; reject `.`, empty components where ambiguous, and any `..` component. Resolve against the trusted root, not `cwd`.
- Reject POSIX absolute paths, Windows drive-absolute (`C:\\x`), drive-relative (`C:x`), rooted (`\\x`), UNC (`\\\\server\\share`), and extended/device (`\\\\?\\`, `\\\\.\\`) syntax on **both** Linux and Windows. Do not let host-specific `Path` interpretation silently accept foreign-platform path forms.
- Canonicalize the trusted root and candidate, and require the candidate to be a strict descendant of the root. Reject existing symlink/reparse-point ancestors and an existing symlink/reparse-point output leaf; do not follow links to a different target.
- Reject directories as output leaves. File replacement is not allowed in the first managed slice: use exclusive create semantics so an existing dossier is not overwritten. Decide separately whether named overwrites should be introduced with explicit authority.
- Avoid creating parent directories or opening files until all validation passes. Validate the **actual opened target** when possible, not merely a previously resolved string.
- A path-based precheck alone cannot prevent a concurrent directory swap (TOCTOU). Race-resistant directory-handle/no-follow operations require separate OS-specific implementation and testing. If the host cannot enforce the promised property, refuse the managed operation or require a separately validated OS sandbox. Do not claim OS-level isolation.

## Acceptance matrix for the next isolated implementation

| Input / condition | Managed policy expectation |
| --- | --- |
| `reports/incident.md` below trusted root, absent file | ACCEPT only after safe open |
| `incident.md` with empty parent path | ACCEPT only after safe open |
| `../outside.md`, `reports/../../outside.md` | REJECT |
| `/tmp/out.md`, `C:\\temp\\out.md`, `C:out.md` | REJECT |
| `\\\\server\\share\\out.md`, `\\\\?\\C:\\out.md` | REJECT |
| Existing symlink ancestor or output leaf / Windows junction | REJECT |
| Existing ordinary file / directory as output leaf | REJECT |
| Missing trusted root / untrusted caller-provided root | REJECT |
| Validation/open race or unverifiable containment | REJECT |
| Standalone legacy `--out` without managed policy | UNCHANGED, explicitly **not contained** |

## Required verification and release gate

- First isolate a **pure validator and open contract**; do not wire it to the production Router until the test matrix is covered on Linux and Windows, including negative cases and actual temporary-directory writes.
- Review **both** Scribe copies and their launcher call paths. Confirm the managed policy cannot be disabled through `context`, argv, `custom_env`, or PATH fallback.
- Re-run P01/P02/P03, runtime contracts, Stage 5 and Windows launcher suites. Retain known Windows Stage 5→6 TOCTOU XFAIL as an explicit unresolved issue; no blanket PASS claims.
- No change to existing permission Gate or other branches. If managed containment cannot be proven, retain the present rejection of experimental `null` mapping and do not connect the adapter to production.
- Rollback for this design-only commit: after confirming the current `fatfish` HEAD, create a normal revert commit. Never force push.

**This document records a proposed boundary, not a deployed mitigation or a passing containment test.**
