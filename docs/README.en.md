# DSHA-SharBoy — Local AI Agent Tool Orchestration

[简体中文](../README.md) · [Release V1.1](https://github.com/yanyu03/DSHA-SharBoy/releases/tag/V1.1) · [60-second demo](DEMO_60S.md) · [Safe install](INSTALL_SAFETY.md) · [GitHub Issues](https://github.com/yanyu03/DSHA-SharBoy/issues)

**A local, inspectable tool orchestration and execution-tracing engineering project for AI agents.** DSHA explores how to route tool requests through environment checks and permission checks rather than having an agent execute guessed commands immediately.

## Who is it for?

Developers experimenting with Windows-based agent workflows, tool routing, reproducible failure handling, and boundaries around external tools. It is not a new LLM, a universal auto-installer, or an operating-system security sandbox.

### Architecture in brief

| Component | Intended role |
| --- | --- |
| Index / Router | Discover candidate tools and choose a route |
| EnvFeel | Inspect local runtime prerequisites |
| Gate / BaseTool | Validate parameters, permissions, and execution targets |
| Execution result / TraceReceipt | Collect outcomes and diagnostic evidence for reproducibility |
| REA integration | Optional third-party analysis integration; separate from the DSHA core |

This is an architecture/protocol overview, **not a claim that every entry point implements every stage end to end**. REA's embedded Android MCP bridge is not the same thing as DSHA's primary routing layer.

## Versions and validated scope

- **Latest tagged GitHub release:** [V1.1](https://github.com/yanyu03/DSHA-SharBoy/releases/tag/V1.1), published November 3, 2026.
- **Current main:** contains fixes after the V1.1 tag. Do not treat the tagged release as incorporating all current main changes.
- **Machine-version caveat:** the legacy root `VERSION` file still says `1.0.0`; see [versioning notes](../VERSION_SCHEME.md).
- **Primary validation environment:** Windows x64 with Antigravity and Python 3.10+.
- **REA prerequisites:** Node.js, and optional additional analysis backends such as Java/Ghidra depending on the task.
- **Verification:** static tests, live tool startup, operating-system isolation, and third-party directory scores are different evidence levels. Never interpret an M8ven badge as full security certification.

## Safe-first quick start (current `main`)

Clone and inspect before installing:

```powershell
git clone https://github.com/yanyu03/DSHA-SharBoy.git
cd DSHA-SharBoy
pwsh -NoProfile -File .\install.ps1 -WhatIfOnly
```

After checking the intended changes, choose the plugin tier explicitly:

```powershell
pwsh -NoProfile -File .\install.ps1 -Tier read-only
pwsh -NoProfile -File .\verify.ps1
```

**Critical limitation:** `install.ps1` configures DSHA's plugin tier and hooks, but does **not** automatically align Antigravity's native permission settings. Review the interruption/restart implications, then manually apply and inspect the native read-only preset using the installed `agy-tier.ps1`:

```powershell
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" -Status
# Only after explicit user review/approval; this may stop/restart the host:
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" read-only -Yes
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" -Status
```

Even with that preset, the read-only policy is **an approximation** in this host. Some writes may require confirmation rather than becoming technically impossible. Full installation can modify local configuration, user PATH, and the PowerShell execution policy; a dependency download may require network access. Never run it blindly on a sensitive workstation. See [installation details](../安装教程.md) and [risk disclosure](../默认全权警告.md).

### Safe non-executing demonstration

```powershell
python scripts/router.py route zzzyyyxxx-no-registered-tool
```

**Expected**: `ERR_NO_MATCH` with exit code `2`, showing refusal to execute an unknown intent. Verify the result on your own environment; the guide does not claim an unobserved live run. More in the [60-second recording script](DEMO_60S.md).

## Contributing

We value **reproducible issues and meaningful outside testing** over inflated claims. Include OS and runtime versions, commit SHA, sanitized logs, exact steps, expected result, observed result, and a PASS/FAIL/SKIP note. Never post tokens or credentials. Security-sensitive bugs should be reported privately rather than including exploit details in a public issue.

[Open an Issue](https://github.com/yanyu03/DSHA-SharBoy/issues) · [Project home](https://github.com/yanyu03/DSHA-SharBoy) · [Protocol specification](../DSHA_OPEN_PROTOCOL_SPEC.md) · [M8ven scan notes](M8VEN_VALIDATION.md)

**License:** MIT for first-party code. Vendored third-party components have their own applicable licenses; see [NOTICE](../NOTICE.md).
