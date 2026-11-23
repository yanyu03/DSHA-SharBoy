# M8ven / MCP 验证说明（2026-11）

DSHA 的核心是本地 Agent 工具路由及权限控制，并不等同于仓库里作为第三方集成组件的 REA Android 桥接器。M8ven 的公开扫描目前只识别到 `rea_jvm_status`，因此不能从其工具列表推断 DSHA 只有一个工具。

## 本轮限定改动

- REA Android 桥接器对**所有当前导出的 MCP 工具**显式设置四项布尔注解：`readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`。
- `rea_jvm_status`、类与方法元数据读取、应用信息和 Manifest 读取视为对外只读，且不访问开放网络。
- `load_apk` 会替换当前分析会话，因此保守声明为非只读、可能破坏已有会话状态、非幂等、封闭环境。**注解是行为提示，不代替权限门禁或实测**。
- 对原生 upstream `get_app_info` 与 `get_android_manifest` 保留原有处理器，不接管业务逻辑。

## 验证层级与限制

| 层级 | 命令 | 说明 |
| --- | --- | --- |
| 静态回归 / 测试探针本身 | `python -m unittest discover -s scripts -p test_mcp_contract.py -v` | CI 可运行；不会启动真实 REA |
| 真实 stdio MCP 端到端探针 | `python scripts/mcp_stdio_smoke.py -- <实际 MCP 服务启动命令及参数>` | 需要宿主事先安装相关运行时；在本机启动真实进程，检查 initialize、tools/list 及所有工具注解，不调用工具 |
| 完整 REA / DSHA 功能测试 | 依据安装环境运行现有对应测试 | 本轮未宣称完成跨平台或外部目标验证 |

探针只读取工具声明，不会调用 `load_apk` 或其他执行工具；遇到无法启动、超时、工具声明缺失等情况会失败。传入的命令完全由操作者指定。真实环境通过前，不能把静态测试的 PASS 写成运行时 PASS。

M8ven 的动态启动失败、`playwright-core` 依赖标记以及 B 评级需要平台重新扫描或提供更细的扫描证据后再确认。本次修复不保证评级上升，也不盲目移除 REA 的依赖。
