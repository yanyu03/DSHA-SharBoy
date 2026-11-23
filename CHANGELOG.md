# CHANGELOG

## main（V1.1 发布后，尚未打新标签）— 2026-11

- 发布前门面整理：中英文介绍、可复现 60 秒演示录制脚本、外部传播文案与安全边界说明。
- 安装器插件默认权限从 `danger-full-access` 调整为 `read-only`；修复 `-WhatIfOnly` 提前创建目录的问题，并确保 `-KeepTier` 在覆写模板前读取旧档位。
- 安装流程仍须经用户确认再通过 `agy-tier.ps1` 同步宿主原生设置；插件档位**不是** OS 级沙箱证明。
- MCP 工具注解与 stdio 检查脚本在先前 PR #7 合入；真实运行需目标环境验证。

## V1.1 — 2026-11-03（Kaeru 选择性吸收 FatFish，已创建 GitHub Release）

- 改进上手文档、Agent 接入提示与可复现反馈入口。
- 合并 Kaeru Router 安全收紧与回归工作流，固定 REA Zod `4.6.6` 并增加防回退测试。
- 不包含后续 main 修复；V1.1 GitHub Release 不提供独立上传的定制源码资产。

## V1.0 — 2026-10-19（主线整理发行，机器版本1.0.0）

- 统一README、版本方案、发布标题与源码包名称，保留历史标签。
- 删除当前README中的绝对保证、沙箱及全平台可用性暗示，明确网络、运行时、权限与验证边界。
- Programer规范与入口采用独立整理版本，当前树移除旧课程蒸馏正文；不重写历史。
- 补充随附REA的许可证与准确分发说明。
- 提供同提交ZIP/TAR、SHA256及源码清单；验证结果见docs/releases/V1.0.md。
- 未合并本地维护分支的运行时改动；本次不改变工具协议或执行实现。

## 历史记录

以下保留历史版本描述和当时的实验记录；其中宣传性措辞、性能数字与旧测试结论不构成本次发行承诺。

> ## 版本线重置说明
> 本仓库存在两条版本线，**两者不比较大小**：
> - **实验线** `2.x`（`2.0.0` → `2.4.0-testweb`）：Antigravity 侧的功能论证分支。
> - **正式线** `1.x`（`1.0.0` 起）：面向开源分发的主线首发，自 2026-10-19 起。
>
> 因此阅读顺序请**以本文件从上到下为准**，不要按版本号大小推断新旧。详见 `VERSION_SCHEME.md`。

## v1.2.0-std — 2026-10-19
**DSHA 开放协议全面标准化对齐与双向接口穿透回溯 (Open Protocol v1.2.0-std)**
- **DSHA 开放协议标准与 JSON Schema 规范 (`DSHA_OPEN_PROTOCOL_SPEC.md`)**：正式确立 DSHA Open Protocol 工业级数据契约，严格遵循 OpenRPC / JSON Schema 标准草案。规范化定义请求包络 `DSHARequest`、响应包络 `DSHAResponse`、执行收据 `TraceReceipt`、阶段断言记录 `StageRecord` 与拒绝凭据 `ErrBlock`。
- **顺着接口到底 (7 阶段确定性正向执行流水线)**：构建端到端不可绕过的生命周期控制面：
  1. `ingress_validation`（入站校验与参数合法性）
  2. `intent_routing`（意图加权路由与元数据绑定）
  3. `envfeel_prerequisites`（宿主环境自感知与依赖探针前置阻断）
  4. `tier_authorization`（权限档位断言与防越权拦截）
  5. `catalog_containment`（类目寻址与防目录逃逸沙箱断言）
  6. `sandbox_execution`（单向受限执行与轻量捕获）
  7. `egress_packaging`（出站标准化封包与 TraceReceipt 盖戳归档）
- **顺着接口回溯 (AI 逆向因果归因引擎 `retrace`)**：提供自 Stage 7 至 Stage 1 的逆序因果树遍历引擎。在工具拒绝或异常中断时，自动化定位根因阶段，输出取证快照、治理建议、L4 标准复现指令（`reproducer`）与受控回滚方案（`rollback`）。
- **收据自动持久化与安全轮转 (`TraceStore`)**：自动持久化执行收据至 `logs/traces/tr_<timestamp>_<hash>.json`，内置 100 份最大保留滑动窗口与自动清理淘汰机制。
- **统一 CLI 接口扩充 (`dsha` / `dsha-index`)**：新增 `trace <trace_id>`（检索执行收据）、`retrace <target>`（逆向因果回溯研判）以及 `schema`（导出机器可读 Open Protocol JSON Schema 规范定义）。
- **自动化测试全景通过**：新增 4 项运行时合约测试，`verify.ps1` 扩展至 67 项体检检查全量通过（PASS 67 / FAIL 0 / WARN 2）。

## v1.0.0 — 2026-10-19
**DSHA-SharBoy 1.0 正式版全景发布 (Official Release v1.0.0 · 全开源 Public 启动)**
- **宿主环境自感知与穿透引擎 (`HostEnvPerceiver`)**：移除硬编码盘符路径，动态感知系统盘、Program Files、AppData、Scoop、Chocolatey、Pyenv 等包管理器运行时并自动注入 PATH，过滤 0 字节 WindowsApps 别名陷阱，确保跨机器与跨盘迁移即插即用。
- **单向传参与受限执行包络 (`ExecutionEnvelope`)**：阻断父进程敏感 Secret/Token 污染泄露，仅向下传递经过白名单净化的受控环境变量、安全工作区与超时约束。
- **感知宿主环境后动态激活路由 (`router.py`)**：意图分析联动前置依赖自检，命中候选工具依据本地就绪状态打标 `ACTIVATED`（🟢 已就绪激活）或 `PREREQ_REQUIRED`（🟡 待激活需补齐依赖），并在决策报告中即时给出修复指引（自检 8/8 通过，n=8）。
- **DSHA-Index 顶层能力目录与元数据事实源 (`bin\dsha-index.cmd` / `scripts/index.py`)**：正式确立全系统 7 大平行工具（CF、REA、Scribe、Pwsh、Sh、Tier、Meter）的顶层索引与契约规范。
- **`Call_Tools` 统合拉取协议**：建立统一函数调用管道，实现底层二进制自动寻址、UTF-8 字符沙箱、网络代理环境注入与执行结果标准化结构回收。
- **DSHA-Router 核心意图路由**：多因子智能评分引擎（内置 8 条路由自检用例，8/8 通过；n=8，不构成准确率），支持直接穿透调用 `Call_Tools`。
- **Cloudflare 全系 CLI 生态直通 (`bin\cf.cmd`)**：全面接通新一代 Cloudflare Forge OpenAPI CLI (2900+ API、`cf mcp`、Agent search) 与 Wrangler/Workerd 本地运行栈。
- **专职档案官 DSHA Scribe (`bin\scribe.cmd`)**：6 段式问题研究简报生成器，为多 Agent 协同提供毫秒级诊断支持。
- **防括号撕裂 Shell 矩阵**：专用 PowerShell 7 独立运行时、加固 `dsha-pwsh` 与 GNU Bash 统一环境。
- **全系自动化体检套件 (`verify.ps1`)**：以 `FAIL = 0` 为通过条件；检查项按 behavior / contract / existence 三类分别计数，总数以脚本自身打印为准。

## v2.4.0-testweb — 2026-10-19
**Cloudflare 直通引擎并入与 DSHA 智能情境路由层 (DHSA-TestWeb 论证分支)**
- **Cloudflare CLI 工具直通引擎 (`bin\cf.cmd`)**：全面整合本地已就绪的 Wrangler (v4.151.1) 与 Cloudflare Tunnels，支持 `status`、`whoami`、`dev`、`deploy`、`pages`、`tunnel`，解决 Windows GBK 编码崩溃与代理自适应。
- **DSHA 智能情境路由层 (`bin\dsha.cmd` / `scripts/router.py`)**：根据开发者意图、目标文件后缀与关键特征，基于 7 大子系统（CF、REA、Scribe、Pwsh、Sh、Tier、Meter）实施多因子加权评分并输出决策依据与推荐命令。
- **8 大场景测试矩阵全通过**：内置路由自检算法（涵盖逆向、边缘部署、日志提纯、系统管理、权限与额度），8/8 用例通过（n=8，不构成准确率）。
- **自动化测试扩充**：新增 Section 11，测试套件扩充至 51 项 (`verify.ps1` 51/51 PASS)。
- **新建实验论证分支**：独立签出 `DHSA-TestWeb` 分支用于前沿 Web 工具链集成论证。

## v2.3.0 — 2026-10-19
**DSHA 书记官智能体 (The Scribe) · 日志收录、情报整理与快速研判简报**
- **DSHA 书记官智能体注册**：新增专职档案与情报整理 Subagent `scribe`，只读无破坏性，专为多 Agent 与 ChatGPT 供给高密度研判材料。
- **纯 Python 标准库情报引擎 (`scripts/scribe.py`)**：自动化收录 Gate 门禁拦截、Antigravity 后台任务退出码、Git 变更足迹与宿主环境指纹。
- **高密度研究简报 (`bin\scribe.cmd dossier`)**：标准化输出 6 段式研判简报，将上万 Token 原始日志提纯为核心态势、报错索引与突破切入点。
- **纯 ASCII 启动器与验证扩充**：新增 `bin/scribe.cmd`，自动化测试套件扩充至 43 项 (`verify.ps1` 43/43 PASS)。
- **ChatGPT 客户端专属书记官提示词**：新增 `chatgpt/SCRIBE_PROMPT.md`。

## v2.2.0 — 2026-10-19
**DSHA-SharBoy 品牌确立与全平台生态分发（支持 Antigravity & ChatGPT 双平台）**
- **品牌全面更名为 DSHA-SharBoy**：GitHub 开源仓库同步更新为 [https://github.com/yanyu03/DSHA-SharBoy](https://github.com/yanyu03/DSHA-SharBoy)。
- **分享至 ChatGPT 桌面客户端**：新增 `chatgpt/SHARBOY_PROMPT.md` 与桌面直接可用的 `DSHA-SharBoy_ChatGPT提示词.txt`，一键注入 Custom Instructions。
- **MCP (Model Context Protocol) 工具支持**：新增 `chatgpt/mcp_config.json`，支持外部客户端挂载本地 REA 静态逆向引擎。
- **Programer 13 章 10,211 行笔记脱敏蒸馏**：蒸馏报告升级至 v2.2（264,700+ 字符语料认知沉淀，公开版本仅保留脱敏提纯成果）。

## v2.0.0 — 2026-10-18
**DSHA-Anty 家族全功能矩阵成型（四位一体：Gate + EngLock + Meter + Programer Mindset）**

**1. DSHA-Meter（额度与 Token 监视器）**
- **5H / 7D 双重配额与单轮上下文追踪**：解析 Antigravity 本地 JSONL 事务日志，计算 5H（200次/100万 tok）与 7D（1500次/1000万 tok）滚动水位。
- **动态回血倒计时预测**：基于滑动窗口首次请求时间戳，精准预测 5H 首笔释放与完全回满倒计时、7D 周额度刷新倒计时。
- **高分屏硬件级物理渲染**：调用 Windows User32 `SetProcessDpiAwareness(2)` 与高精字体平滑，彻底消除 4K / 高 DPI 下窗口与文本模糊发虚。
- **高内聚多进程并发架构**：GUI 独占主线程，后台守护线程 2s 轮询，跨线程共享缓存严格使用 `threading.Lock()` 互斥保护。
- **控制器脚本 `agy-meter.ps1`**：提供 `-Start` / `-Stop` / `-Restart` / `-Status` 标准幂等运维界面，脱壳常驻桌面。

**2. Programer 系统级编程思维与工程导师模式 (Programer Mindset)**
- **系统级课件深度语料蒸馏**：提取自 14 门系统级架构 PPT、980+ 幻灯片、17,600+ 文本词条（Linux、数据容器、闭包装饰器、文件 I/O、异常、面向对象、进程、线程、Socket、标准库、正则）。
- **五步启发认知脚手架**：痛点启发 (Socratic Inquiry) -> 本质穿透 -> 步骤拆解 -> 避坑防线 (110+ 处陷阱预警) -> 运行实证。
- **系统级五大支柱确立**：系统底层穿透律、防御性契约与生命周期、并发选型与锁纪律、高内聚与无侵入切面、精炼范式与量化实证。
- **完整工程产物与导师提示词**：新增 `docs/PROGRAMER_DISTILLATION.md`、`docs/PROGRAMER_MINDSET.md` 与 Agent 指南 `skills/DSHA/programer.md`。

**3. 开源与隐私安全加固**
- **个人路径彻底脱敏**：消除所有硬编码 `Users/admin` 路径，采用 `$env:USERPROFILE` 动态解析与自适应 Python/Pythonw 探测。
- **严密 `.gitignore` 规则**：隔离本地门禁日志、运行时状态、历史备份、node_modules 与字节码，确保开源仓库零隐私泄露。
- **Git 开源结构对齐**：全面适配上游 `DSHA-Anty` 开源仓库标准。

**4. REA 逆向工程与证据抽取工具集就地调用 (Reverse Engineer Anything)**
- **代码库就地引入**：引入 `morluto/rea` 核心静态分析与 MCP 引擎，作为 Skill 专属工具集常驻 `skills/reverse-engineer-anything/tools/rea/`。
- **150+ 逆向分析指令**：涵盖 JavaScript / Electron ASAR 解包与语义追踪、PE / ELF / Mach-O 节表与哈希证据图、Android APK 资源清单及 SQLite 分析。
- **Programer 风味 Python 驱动器 (`dsha_rea_driver.py`)**：底层自适应探测 Node.js；目标存在性前置断言；缺少 Ghidra/Hopper 时自动安全降级至纯静态提取；180s 超时隔离，永不假死。
- **全局与就地双通道调用**：支持 `rea.cmd <command>`、`rea --self-test` 与 MCP stdio 服务就地唤起。

**5. 合规防咬人 Shell 环境 (No Parenthesis Biting)**
- **根治语法咬人陷阱**：彻底解决 Windows PowerShell 5.1 对圆括号 `()`、嵌套括号及单双引号的解析器报错 (`ParserError`, `Missing closing ')'`)。
- **解除脚本权限拦截**：CurrentUser 作用域合规置为 `RemoteSigned`，解决 `npm.ps1` 等脚本的 `UnauthorizedAccess`。
- **GNU Bash 5.3 接入全局环境**：将 Git Bash 核心加入全局 User PATH，并提供 `bash.cmd`、`sh.cmd`、`dsha-sh.cmd` 统一启动器。
- **零圆括号批处理架构**：所有 cmd 脚本重构为标签跳转，规避 `if (...)` 块被未闭合括号撕裂的 Windows 经典缺陷。

**6. 专用 Pwsh 运行时环境（彻底摆脱 Windows 原厂 PowerShell 5.1）**
- **原生 PowerShell 7.6 独立运行时**：集成自包含 .NET Core 运行时，彻底解决 Windows 原厂 PowerShell 5.1 内置别名冲突（`curl`、`wget`、`R`）、GBK 编码破坏、管道括号咬人等顽疾。
- **零圆括号与加固启动器 (`pwsh.cmd` / `dsha-pwsh.cmd`)**：提供无括号块语法转发与 `-NoProfile -ExecutionPolicy Bypass` 预置安全调用。
- **自举式镜像拉取脚本 (`scripts/fetch-pwsh.ps1`)**：基于 Programer 底层穿透原则，支持 npmmirror/npmjs 多通道秒级自举与无污染安装。
- **安装器与体检流水线升级**：`install.ps1` 自动分发与注册 User PATH；`verify.ps1` 新增 Section 9 专用体检，39 项检查全通过。

## v1.0.0 — 2026-10-05
首个可分发版本。

**权限档位（移植自 DSH）**
- 四级预设：read-only / workspace-write / danger-full-access / auto
- `scripts/gate.py`：PreToolUse 钩子，62 项自检全通过
- `agy-tier.ps1`：唯一事实源，未加 `-Yes` 不修改任何文件；切换端到端约 7 秒
- `skills/DSHA/`：档位说明 + 四档警告全文 + 内联选择器 widget

**工程锁（L1–L9）**
- L1 出处锁 / L2 样本锁 / L3 撤回锁 / L4 三件套锁 / L5 报告头锁 / L6 措辞锁 / L7 断拍锁 / L8 外部审查锁
- **L9 语言规范锁**：L9.1 禁用词（硬锁）、L9.2 无据权威、L9.3 伪精确、L9.4 假完成、L9.5 术语漂移、L9.6 引用不可解析、L9.7 未来态无标记
- `scripts/englock.py` v2：19 项自检；与 `gate.py` 同协议、**fail-open**
- `lexicon.json`：L9 词表（9 组约 120 条），改词表即改行为

**工程化**
- `install.ps1`：幂等安装、时间戳备份、按本机 Python 重写钩子包装器、`-WhatIfOnly` 预演、`-Uninstall` 回滚
- `verify.ps1`：七项只读体检
- 已知坑写进文档：`cmd /c` 剥引号、提权启动 `requestSingleInstanceLock` 静默退出、`AGENTS.md` 必须纯 ASCII、`englock.json` 的 BOM 问题

### 打包前修复（自测发现）
- **verify.ps1 函数名与 PowerShell 内置别名冲突**：`R` 是 `Invoke-History` 的别名，优先级高于函数，导致 29 项检查全部被劫持 → 改名 `Check` / `Note`，现 PASS 29 / FAIL 0。
- **安装器调用了不存在的入口**：`gate.py --selftest` 并非有效入口（自检在独立 `selftest.py`）→ 改为调用 `selftest.py`，现正确输出 `pass=62 fail=0`。

## v1.1.0 — 2026-10-06
- **出厂默认档位改为 `danger-full-access`（全权）**，并新增 `默认全权警告.md`（安装器每次打印警告横幅）；支持 `-Tier <name>` / `-KeepTier` 覆盖
- **UI 权限调节面板**：`skills/DSHA/widget.html` 升级为可交互面板 —— 四档卡片（含风险/是否需重启/当前标记）、每档「复制切换命令」「复制请求 agent 切换」、工程锁模式切换命令、状态重读命令、全权风险横幅
- **工程锁加固（被真实语料逼出来的两处修复）**
  - 新增 `mask_quoted()`：代码围栏 / 引用块 / `【原文】` 段**不计分**，避免"引用别人"被当成"自己这么说"
  - **L9.3 收窄**：只对"精度主张"（`xx.xx%` 或"提升/占比+两位小数"）触发，不再把 `3.67W`、`639.02MB` 这类仪器读数当伪精度
- 新增 `防胡言乱语效果评估.md`：三组语料实测（Anty 侧 82% 文档被点名，硬锁 L9.1 命中率 100%；误报约 17%）

## v1.2.0 — 2026-10-06
**词库 → 表述策略（有条件许可）**
- 策略模型从"禁用词表"升级为"触发 → 补偿 → 判定"：允许说，但必须在邻近窗口给出补偿信息
- 新增 6 条窗口规则：**L9.8 绝对量词 / L9.9 因果声明 / L9.10 程度无量化 / L9.11 断言强度 / L9.12 时间绝对 / L9.13 自指权威**
- **L2 升级为"样本邻近锁"**：证据必须在断言 ±120 字内，而非"全文出现过即可"
- **严重度模型**：`hard` / `strict_hard` / `warn`，strict 模式下 8 类直接拒绝（L5 L6 L9.1 L9.11 L2 L9.8 L9.9 L9.12）
- 自检用例 19 → **30 条**（含每条窗口规则的"触发/放过"成对用例）
- 设计依据：当日聊天记录词频审计（验证类 12.5/万、绝对量词 9.0/万、因果连词 7.2/万）→ 证明"一刀切禁用会误杀正常表述"
- 修复：自检用例中「逸」误写为 `\u900d`（应为 `\u9038`）导致 L9.12 用例永不触发

## v1.2.1 — 2026-10-09
**部署时发现的三个真问题（均已修复）**
1. **工程锁会被档位切换顺手关掉**：`agy-tier.ps1` 每次切档都会重写 `plugins\dsh-permissions\hooks.json`，切到 `danger-full-access` 时把钩子置为 `enabled:false` → 寄生在那里的工程锁随之失效。
   **修法**：工程锁拆成**独立插件** `plugins\dsha-englock`（name=DSHA-EngLock），自带 `hooks.json`/启动器，并注册进 `config.json` 的 `plugins.<目录名>.enabled` 与 `plugins.json` 的 `entries`。实测：切到全权档后 `dsha-englock` 仍 `enabled=true`。
2. **钩子命令被双重转义**：`hooks.json` 里路径写成 `C:\\\\Users\\\\...`（JSON 解码后是双反斜杠）。**修法**：去掉生成时多余的 `.Replace('\','\\')`，并重写 `docs/hooks.full.json` / `hooks.permissions-only.json` / 插件内 `hooks.englock.example.json`，现为单层转义且解码后路径全部存在。
3. **安装器曾被正则修补截断**：分节只剩到「6. 自检」，独立插件与注销逻辑缺失。**修法**：按实际内容精确补回，并把"权限钩子是否开启"改为**随档位**（`read-only`/`auto` 开、`workspace-write`/`danger-full-access` 关），不再与 `agy-tier.ps1` 抢所有权。
