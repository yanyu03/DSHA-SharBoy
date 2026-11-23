# DSHA 60 秒真实演示录制脚本（拍摄指引，不是成品视频）

**目标**：向外部开发者展示“面对未知意图拒绝调用工具”和“先观察再安装”的路径。**只使用本机实录，不拼接虚构 PASS 输出，不执行真实高风险工具。**

推荐环境：Windows x64、Python 3.10+、PowerShell 7 / `pwsh`；当前 `main` 代码已在本机克隆。录制前检查终端与屏幕中无账号、token、真实用户路径或私密日志。

| 秒数 | 画面 | 实际动作 | 证据边界 |
| --- | --- | --- | --- |
| 0–8 | 仓库首页与英文入口 | 展示 `README.md`、`docs/README.en.md` | 代码和文档可见，不代表安装已验证 |
| 8–20 | PowerShell 终端 | `pwsh -NoProfile -File .\install.ps1 -WhatIfOnly` | 只应输出环境和拟执行操作；不写配置 |
| 20–32 | Python 终端 | `python scripts/router.py route zzzyyyxxx-no-registered-tool` | **预期** `ERR_NO_MATCH`、退出码 2；以实测为准 |
| 32–44 | Python 回归测试 | `python -m unittest discover -s scripts -p test_kaeru_router_safety.py -v` | 只能证明所列测试通过 |
| 44–53 | MCP 契约测试 | `python -m unittest discover -s scripts -p test_mcp_contract.py -v` | 测试使用 mock stdio，不等于真实 REA 启动 |
| 53–60 | GitHub Issues 和安全声明 | 展示 `docs/INSTALL_SAFETY.md`、`Issues` 入口 | 邀请可复现反馈，不宣称无漏洞 |

## 上屏文字（推荐）

- `Local AI Agent tool orchestration`
- `Discover → Check prerequisites → Gate → Result/Trace`
- `Unknown route? Refuse and explain.`
- `Default plugin tier on main: read-only (native host permission requires manual sync)`
- `Try it • Report a reproducible issue • Contribute`

## 录制验收

- 每条命令可在当前仓库实际执行并保留进程退出码，尤其 `ERR_NO_MATCH` 为**预期拒绝**而不是失败演示。
- 如有预期之外错误，原样保留和解释；不能用模拟输出替代实测。
- 不展示 `danger-full-access` 的自动执行，不在敏感真实文件上试验。
- 视频或 GIF 录制尚未完成时，宣传材料仅称“已提供录制脚本”，**不得称已经发布视频**。
- M8ven 的 B 等级不等于安全认证或运行时测试通过；它仅代表平台自身扫描结果。
