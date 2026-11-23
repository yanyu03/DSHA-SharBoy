# DSHA 安全安装与权限同步 / Safe installation

**适用范围：当前 `main` 分支（2026-11），不是 V1.1 旧标签的安装结果。**

## 首次试用顺序

1. 阅读仓库 [README](../README.md)、[安装教程](../安装教程.md) 和 [全权风险说明](../默认全权警告.md)，确认目标宿主为 Windows Antigravity + Python 3.10+；不要在生产机或含敏感凭据的宿主直接试验。
2. 先只读检查，并确认将会改动的路径。主分支已修复 `-WhatIfOnly` 在退出前创建配置目录的问题。
3. 明确选择本地插件 `read-only` 档位，安装后运行体检。
4. **单独核对原生宿主权限**。插件的 `tier.json` 和 `hooks.json` 无法证明 Antigravity 的原生 `autoExecutionPolicy`、`internetAccessPolicy` 等选项已同步。
5. 阅读切档警告、接受可能中断/重启宿主后，才运行 `agy-tier.ps1 ... -Yes`。执行后再次读取状态，观察是否存在项目级覆盖配置。

```powershell
git clone https://github.com/yanyu03/DSHA-SharBoy.git
cd DSHA-SharBoy
pwsh -NoProfile -File .\install.ps1 -WhatIfOnly
# Review path/permissions and backup location; then:
pwsh -NoProfile -File .\install.ps1 -Tier read-only
pwsh -NoProfile -File .\verify.ps1
# Inspect current native host settings; do not assume success:
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" -Status
# Explicitly approved, restarts/interferes with running Antigravity sessions:
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" read-only -Yes
pwsh -NoProfile -File "$env:USERPROFILE\.gemini\config\agy-tier.ps1" -Status
```

**关于限制**：这是由钩子 + 宿主原生控制组合的*近似只读*。普通写入在某些路径仍可能转成审批请求；没有 OS 沙箱保证。命令可拒绝，不等于整个宿主绝无副作用。工程锁是输出/证据纪律，不是文件隔离。

**关于安装副作用**：完整 `install.ps1` 可能创建配置目录、复制插件与 REA 文件、生成启动器、调整用户 PATH、设置 PowerShell 执行策略、下载运行时和注册插件。因此 **`-WhatIfOnly` 可以用于先观察，但实际安装并非只读**。

**关于升级**：安装器在复制模板前读取原有有效 `tier.json`，`-KeepTier` 保留旧插件档位。它不会替你调整宿主原生权限；如果原有档位就是 `danger-full-access`，它仍被保留。无效的旧档位将触发错误，避免悄悄降级成未知状态。

**关于回滚**：`pwsh -NoProfile -File .\install.ps1 -Uninstall` 从最近备份恢复已覆盖的部分文件。它并不保证回滚全部主机级别副作用（PATH、执行策略、外部下载、宿主项目级设置等），请先记录当前配置，必要时人工恢复。

**关于权限升级**：仅在可信、明确授权、备份完整的情况下，显式执行 `-Tier danger-full-access` 或后续原生切档；不要在初次使用时全权执行陌生代码。

检验方法分层：`-WhatIfOnly` 实机无写入检查 / 静态契约回归 / 原生宿主配置核验 / 实际使用功能验收。每种只支持其自身结论。
