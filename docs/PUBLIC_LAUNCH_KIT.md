# DSHA Public Launch Kit 1.0（内容包，不代表已在平台发布）

**Repository**: https://github.com/yanyu03/DSHA-SharBoy  
**Latest tagged release**: https://github.com/yanyu03/DSHA-SharBoy/releases/tag/V1.1  
**Safe install (current main)**: [INSTALL_SAFETY.md](INSTALL_SAFETY.md)  
**Demo recording plan**: [DEMO_60S.md](DEMO_60S.md)  
**Issue feedback**: https://github.com/yanyu03/DSHA-SharBoy/issues

## 一句话定位

> DSHA helps local AI agents discover tools, check prerequisites, enforce local permission boundaries, and record execution outcomes. It is an engineering toolkit, **not an OS-level sandbox** or a universal MCP server.

## 中文首发（V2EX 分享创造 / 掘金）

**标题：** 我开源了一个本地 AI Agent 工具调度工程 DSHA，想邀请大家测试权限与调用边界

在折腾本地 Agent 时，我发现“模型选好了工具”只是第一步。工具有没有安装、参数能不能用、是否具有权限、出错后能否复现，往往决定了体验是否可靠。

我把这些问题收敛到 DSHA-SharBoy：Index/Router 做工具路由，EnvFeel 看依赖，Gate/BaseTool 管调用边界，再用结果记录帮助排错。它还包含部分第三方 REA 集成。

目前已发布 V1.1，`main` 继续做安全与可测试性修复。主要验证环境是 Windows；它不是操作系统沙箱，也没有承诺全平台通用。

更希望收到真实试用和可复现问题，而不是单纯求 Star。欢迎在 GitHub 提 Issue/PR： https://github.com/yanyu03/DSHA-SharBoy

## English launch (DEV.to / Show HN, only after live demo validation)

**Title:** Show HN: DSHA — experimenting with safer local AI agent tool orchestration

I built DSHA-SharBoy to explore a practical gap in local agent workflows: choosing a tool isn't the same as checking its prerequisites, permission boundaries, and failure evidence.

The project includes an Index/Router layer, environment checks, Gate/BaseTool execution boundaries, and tracing concepts. A separate REA integration explores third-party tooling.

Windows is the primary validated environment. The architecture is still being refined, and DSHA is not an operating-system sandbox or a fully verified universal MCP server.

Latest tagged release: V1.1, with further work on `main`. I'm looking for real installation feedback and reproducible bugs: https://github.com/yanyu03/DSHA-SharBoy

## 阶段门槛

| 阶段 | 发什么 | 发布条件 |
| --- | --- | --- |
| GitHub | README + 英文入口 + 安全安装 + 演示脚本 | 内容与链接可审查 |
| 中文社区 | 技术问题 + 最小复现 | 至少完成本机演示并明确 SKIP 项 |
| 英文社区 | Show-and-tell + 真正的录屏 | 先核对命令、视频、功能、许可 |
| MCP 目录 | 仅申报确有可运行启动入口的服务器 | 有公开可安装或可访问的真实 MCP 端点、对应 `tools/list` 证据 |

请勿群发广告、购买 Star、夸大 B/A 扫描成绩、或把静态测试和 mock 服务称为真实运行通过。

## 一周观察指标（目标，不是实际数据）

- 至少 5 名自愿实际试用者
- 至少 3 条含版本、环境、复现步骤的有效 Issue/反馈
- 至少 1 次独立环境从安装到拒绝/结果日志的成功复现

复盘只记录可证实的事实：访问来源/反馈内容、issue 处理状态、已运行测试范围；不采集、公开用户的敏感环境数据。
