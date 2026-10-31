# KDI-01 / P01 — Strict JSON null 与位置 argv 边界（隔离审计）

- **事实基线**：`fatfish@bccb5192a4e71dabf4bdb31a7860764ff53fc449`，DSHA 私有协议 `v1.2.0-std`。
- **唯一目标**：冻结 strict named tool 的 JSON `null`、字段缺失与字符串值之间的行为边界；不新增参数编码或执行权限。
- **范围**：隔离 P01 回归测试及本文档。未修改 `scripts/kdi_protocol_preflight.py`、Router、BaseTool、Gate、TraceReceipt 或七阶段生命周期。
- **参考**：[OpenAI Function calling — Strict mode](https://developers.openai.com/api/docs/guides/function-calling)；[JSON Schema null](https://json-schema.org/understanding-json-schema/reference/null)。

## 现有行为与必要区分

OpenAI 严格模式中，对象的所有声明属性列入 `required`，可用 `type: ["string", "null"]` 等表达语义上的可选值。但 P01 只提供可信字段顺序到 `Tuple[str, ...]` 的映射，`null` 不是可直接执行的字符串 argv。

| 输入（声明 `location, lang`） | 当前严格模式 | 说明 |
|---|---|---|
| `{"location":"Tokyo","lang":"ja"}` | PASS | 完整字符串字段 |
| `{"location":"Tokyo"}` | REJECT | 严格模式不允许字段缺失 |
| `{"location":"Tokyo","lang":null}` | REJECT | 没有可信的 null→argv 编码 |
| `{"location":"Tokyo","lang":""}` | PASS | 空字符串是实际字符串参数，不等于 null |
| `{"location":"Tokyo","lang":"null"}` | PASS | 字面字符串 `null`，不是 JSON null |
| `{"args":["Tokyo",""]}` | REJECT | 严格模式禁止旧位置参数入口 |

非严格工具仍允许声明的尾部字段**缺失**，但不因此接受显式 `null`；旧 `args` 兼容行为不变。

## 设计判定

**本轮不自动把 null 转为空字符串、字面 "null" 或省略中间位置参数。** 这些转换可能导致语义碰撞或位置错位。仅在严格模式已列出所有字段的情况下，若将来采用“可信可空尾部字段”方案，必须额外证明：

1. 可空字段只能组成声明字段的连续尾部；输入中一旦出现 null，后续字段必须全部为 null，禁止位置洞。
2. 由可信契约声明字段顺序及 null→缺省的具体业务语义，不能由模型自行指定。
3. 保留足够信息以区分 JSON null、空字符串与字面字符串 "null"；验证反向重建或明确记录不可逆损失。
4. 原有权限 Gate、工具参数边界和严格模式的旧 `args` 拒绝规则均保持不变。
5. 独立完成正反向测试、异常值测试和双平台回归后，才能考虑启用；默认继续拒绝 null。

若业务工具需要中间可空参数，应另行研究显式对象到 argv 的可信映射，而不是复用前缀位置映射。

## 回归矩阵

新增 `test_strict_named_null_values_fail_closed_both_protocols`、`test_strict_named_missing_null_and_empty_are_distinct`、`test_non_strict_optional_omission_does_not_accept_null`。每项覆盖 Responses 与 Chat，测试不执行真实工具。

**边界**：这不是通用 JSON Schema 验证、OpenAI API 端到端、SSE、生产 Router 集成或 OS 沙箱安全证明。Windows Stage 5→6 TOCTOU 仍是独立已知风险。

## 回滚

只在重新核验 `fatfish` HEAD 后反向提交本轮文档和测试；不 force push、不触碰其他分支、不自动合并 Draft PR #6。

## 下游承载性判定 — 2026-10-31 / KDI-01 下一独立验收项

**基线**：`fatfish@a3603f538f018da7a75b356651f3d5b5b168140b`；DSHA 私有协议仍为 `v1.2.0-std`。

**结论：目前不能证明现有 DSHARequest / Call_Tools 链路可无损承载 JSON null。保持 fail-closed，不把隔离投影接入执行链。** 现有 `PreparedToolCall.to_dsha_request()` 仅生成 `{"tool": ..., "args": [string, ...], "context": {}}`，没有可信的 nullable 元数据通道；`Call_Tools(tool_name, args, context)` 接收的是字符串位置参数，不会消费 `NullableSuffixProjection`。不能将 `null_suffix_count` 塞入 `context` 或伪装为环境/权限字段以绕过协议和 Gate。

**可重复的语义碰撞**：严格工具的 `{"location":"Tokyo","lang":null}` 在隔离投影中得到 `argv_prefix=("Tokyo",)`、`null_suffix_count=1`；非严格工具的 `{"location":"Tokyo"}` 合法地得到相同 `args=["Tokyo"]`，但其语义是字段缺失，而非显式 JSON null。只传 argv 会丢失两者差异；前者仍由 P01 拒绝。空字符串和字面 `"null"` 不作为哨兵。

**本轮回归**：`test_nullable_suffix_metadata_not_preserved_by_legacy_dsha_envelope` 在 Responses/Chat 两种输入中同时验证严格与非严格模式拒绝显式 null、非严格尾部缺失仍兼容、argv 碰撞以及无 sidecar 的现有 DSHA 请求形状。测试是纯协议隔离测试，不执行真实工具。

**后续决策**：暂不新增下游 sidecar 或修改私有协议。下一独立任务研究“可信对象→argv 的显式映射”及业务工具的可空参数语义，须先给出可逆性与 Gate 不变的证据；若无证明，继续拒绝 null。Windows TOCTOU、真实 SSE/API、生产 Router 接线仍属未解决范围。

**回滚**：仅在重新校验 `fatfish` HEAD 后，反向提交本节文档及对应测试；不 force push、不改动其他分支或 PR 状态。
