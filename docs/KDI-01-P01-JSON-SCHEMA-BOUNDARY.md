# KDI-01 / P01 — JSON Schema 语义边界审计（隔离实验）

- **状态**：差异审计 + 回归锁定；不是完整 JSON Schema 实现，也不是生产 Gate。
- **事实基线**：`fatfish@ee484d3b47e51ea259d73eb71719dfb915e0cf2c`；DSHA 私有协议 `v1.2.0-std` 不变。
- **范围**：仅 `scripts/kdi_protocol_preflight.py` 的 `CompiledContract.compile()` / `prepare_tool_call()` 与隔离测试。未修改执行链。
- **外部依据**：OpenAI 官方 [Function calling — Strict mode](https://developers.openai.com/api/docs/guides/function-calling)；[JSON Schema 对象与 required](https://json-schema.org/understanding-json-schema/reference/object)。

## 已证实的语义差异

| 语义 | OpenAI / JSON Schema | P01 目前实现 | 结论 |
|---|---|---|---|
| `required` | 通用 JSON Schema 可要求任意字段子集 | `named_required_counts` 只能要求字段顺序的前 N 项；允许省略连续尾部 | **不等价**。缺少中间字段不能安全地转为位置 argv，当前拒绝是正确的 fail-closed 行为 |
| `additionalProperties` | 通用 JSON Schema 默认允许额外字段；显式 `false` 才拒绝 | 具名模式强制字段集合等于声明字段的前缀集合 | 近似于受限 `additionalProperties=false`，但**并非 JSON Schema 解析器** |
| OpenAI `strict: true` | 每个对象要求 `additionalProperties:false`，且所有 `properties` 字段均列入 `required`；可用包含 `null` 的类型表达可选值 | P01 允许省略尾部字段，却不接受 `null` 值 | **不能宣称严格模式 Schema 兼容**，应在独立适配层决定映射/拒绝策略 |
| 旧位置参数 `{"args":[...]}` | 不属于具名 Schema 的属性约束 | 继续兼容，但不经过具名整数边界/字符串枚举校验 | **重要安全边界**：具名约束不能当作所有调用入口的统一授权保证 |
| 权限 `context/tier` | 不应从模型参数提升 DSHA 权限 | 具名模式拒绝未知/受保留字段；位置参数不改变 `context={}` | 继续由原有执行边界 Gate 判定权限，P01 不能替代 Gate |

## 最小复现矩阵

可信字段顺序 `("location", "query", "lang")`、`named_required_counts=1`：

1. `{"location":"Tokyo"}` → 允许（尾部均省略）。
2. `{"lang":"ja","query":"weather","location":"Tokyo"}` → 允许，argv 按可信声明顺序归一化。
3. `{"location":"Tokyo","lang":"ja"}` → 拒绝；这是 JSON Schema 可表达但 P01 位置 argv 无法无损映射的非连续字段。
4. `{"location":"Tokyo","extra":"x"}` → 拒绝；即使通用 JSON Schema 默认可允许 extra。
5. 配置具名 `limit` 整数 0–10、`lang` 枚举 en/ja 时，`{"limit":999,"lang":"fr"}` 拒绝，但旧 `{"args":["999","fr"]}` 仍按兼容规则接受。**不得将此行为描述为 Schema 全入口验证。**

回归测试：`test_schema_boundary_required_prefix_not_arbitrary_subset`、`test_schema_boundary_extra_properties_fail_closed_both_protocols`、`test_schema_boundary_legacy_args_not_subject_to_named_constraints`，均覆盖 Responses / Chat。测试仅观察现有行为，不调用真实工具。

## 后续独立决策（本轮不实施）

若未来需要严格 Schema 接线，先明确两种可逆路径：A）仅支持无可选洞、全字段必填的安全子集；B）设计可信参数对象到 argv 的显式映射（含 null/缺省处理），并按工具单独审计。对仍允许旧 `args` 的入口，必须清楚区分其约束策略，不能因为具名校验存在就推断旧路径受同样约束。

**未覆盖**：真实 OpenAI API / SSE、完整 JSON Schema、Router/BaseTool/Gate 集成、Windows 真机。Windows Stage 5→6 TOCTOU 仍未解决。文档与回归不构成安全认证。
