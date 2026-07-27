<!-- parents: ../130-gui-first-external-agent-control-plane-target.md, 129-stage81-current-operator-inbox-and-approval-collection.md -->
<!-- relates: ../48-adapter-runtime-interface.md, ../49-capability-routing-model.md, ../64-versioning-governance.md -->

# 131 — Stage 82 External Agent Adapter Contract 与 MVP Boundary

> 状态：**Stage 82 design-only 完成；未授权真实 adapter、session、readiness probe 或 dispatch**
> 日期：2026-07-27
> 事实源：`../../adapters/external-agent-adapter-contract.schema.json`、`../../adapters/external-agent-live-read-model.schema.json`

## 1. 里程碑结论

Stage 82 冻结了 Claude、Kimi、OMP/Pi、QwenPaw 和未来外部 Agent 共用的 transport-neutral contract。ACP、CLI、local process 只负责承载消息和生命周期信号，不得改变 Harness 的 plan、run、attempt、approval、lease、audit、handoff、review 和 recovery 语义。

本阶段只有 schema、fixture、failure matrix、测试计划和 GUI 最小 live read model。示例中的 Agent、readiness、session、dispatch、event、approval 与 artifact 全部是 fixture，不是本机探测或真实执行证据。

## 2. 权威边界

Harness 唯一拥有 plan、work item、run、attempt、expected state、current projection、dispatch authority、approval binding、lease、idempotency、audit、retry/cancel/recovery 决策和 GUI 安全投影。

外部 Agent 唯一拥有模型与 Provider、原生 session、内部上下文、工具实现、原始工具输出和自身 transport 特性。Harness 只能消费 adapter 可验证后上报的 readiness、event、artifact 与 review evidence。

readiness、可见按钮、fixture approval 或业务资格都不是 dispatch authority。真实 transport 调用前必须由 Harness 同时确认 identity、capability、readiness、approval、expected state、lease、idempotency，并先写 started audit。

## 3. 契约包

### 3.1 稳定身份与 capability

每个接入绑定 `agent_id`、`adapter_id`、`implementation_id`、`agent_version`、`adapter_version`、`transport_id`、transport kind、`protocol_version` 和内容寻址的 capability manifest。任何版本或 manifest 漂移都使旧 readiness、approval 和 session mapping 失效。

capability 以 Planner、Executor、Reviewer role、work-item 类型、输入/输出 artifact 类型和 streaming/cancel/session-resume 特征声明。Agent 产品名不能成为主流程分支条件。

### 3.2 Readiness evidence

readiness evidence 必须有明确来源、观察时间、过期时间和完整身份/capability binding。状态固定为 `ready|blocked|unknown|stale`：

- evidence 缺失或来源不可验证：`unknown`，fail closed；
- TTL 过期：`stale`，不可派发；
- binding drift：`blocked`，必须重新采集并重新审批；
- `ready` 只表示外部实现可用性，不表示已获得执行授权。

### 3.3 Session mapping

外部 session identity 只以 opaque digest/reference 保存和展示。映射粒度固定为 Harness `run_id + attempt_id`，不得跨 attempt 复用。断连后 session 状态先变为 `unknown`，不得猜测已关闭、已完成或可安全重试。

### 3.4 Dispatch envelope

派发只接受 `external-agent-dispatch/v1` 结构化 work-item envelope。它绑定 plan/version、run projection、attempt、work item、adapter/version、transport/protocol、capability manifest、instruction/input artifact digest、readiness、approval、lease、deadline 和 idempotency key。

契约不提供任意进程参数、宿主路径、环境覆盖或通用 shell 旁路。transport adapter 只能把同一 envelope 映射到自己的协议，不能自行扩大权限或修改 control-plane 事实。

### 3.5 Event、artifact、review 与 terminal

每个 dispatch 的 event 使用从 1 开始的单调 sequence、previous event 和 deduplication key。重复且内容相同的 event 可幂等忽略；相同 dedup key 但内容冲突必须进入 recovery。序列缺口、断连或无法确认 cancel 结果时，Harness 不能推断成功，必须产生唯一 `outcome_unknown` terminal audit，并 withholding 历史结果直到 reconciliation。

artifact 只通过 reference、digest、media type、size 和安全摘要进入控制面；digest 不匹配时内容 withheld。review 必须是结构化 decision，不能以原始聊天或文本猜测替代。

## 4. Approval evidence 与 dispatch authority

approval evidence 必须包含 issuer 类型与 id、decision 状态、签发/过期/撤销时间、binding digest 和 idempotency key，并精确绑定 plan id/version、run/current projection、attempt/work item、expected state、adapter/capability。

仅 `granted`、未过期、未撤销且 binding 完全匹配的 evidence 才能成为 dispatch authority 的一个必要条件。它仍不是充分条件；identity、readiness、lease、expected state、idempotency 和 started audit 任一失败都必须阻止调用。

## 5. Transport 共同语义

| Transport | 可变部分 | 不可变上层语义 |
|:---|:---|:---|
| ACP | handshake、session API、事件承载方式 | 同一 identity/capability/readiness/dispatch/event/approval/audit contract |
| CLI | 固定受信入口、一次性或可恢复调用映射 | 不接受任意参数；同一 started/terminal、bounded output、recovery 语义 |
| local process | 本机进程或 IPC 生命周期 | 同一 lease、进程树 containment、event ordering 和 outcome unknown 语义 |

WebSocket 或未来协议若加入，也只能成为后续 transport kind；不得建立 Agent-specific 主流程或 GUI 分支。

## 6. Failure matrix

| Failure code | 阶段 | 稳定处置 |
|:---|:---|:---|
| `identity_binding_mismatch` | binding | blocked；重新解析身份，不调用 transport |
| `contract_version_unsupported` | binding | blocked；要求兼容版本 |
| `capability_not_declared` | binding | blocked；不得猜测 capability |
| `readiness_missing` | pre-dispatch | blocked；重新采集 evidence |
| `readiness_expired` | pre-dispatch | blocked；过期 evidence 不可复用 |
| `readiness_binding_drift` | pre-dispatch | blocked；重新采集并重新审批 |
| `session_mapping_conflict` | pre-dispatch | blocked；人工核对 run/attempt 映射 |
| `approval_missing` | pre-dispatch | blocked；进入 approval inbox |
| `approval_not_granted` | pre-dispatch | blocked；pending/denied 都不可派发 |
| `approval_expired` | pre-dispatch | blocked；重新审批 |
| `approval_revoked` | pre-dispatch | blocked；不得复用旧 decision |
| `approval_binding_drift` | pre-dispatch | blocked；目标、状态或版本漂移 |
| `expected_state_stale` | pre-dispatch | blocked；刷新 current projection |
| `lease_unavailable` | pre-dispatch | blocked；不得并发旁路 |
| `idempotency_replay` | pre-dispatch | 返回既有 terminal；outcome unknown 时先恢复，不重复派发 |
| `transport_unavailable` | pre-dispatch | blocked；尚未调用时不伪造 started |
| `dispatch_rejected` | dispatch | 写唯一 failed terminal；可按新 attempt 重试 |
| `event_duplicate_conflict` | event collection | recovery required；停止接受冲突流 |
| `event_sequence_gap` | event collection | recovery required；不得推断完成 |
| `transport_disconnected` | event collection | outcome unknown；等待 reconciliation |
| `cancel_unsupported` | cancellation | blocked；UI 不提供伪取消 |
| `cancel_outcome_unknown` | cancellation | outcome unknown；禁止立即 redispatch |
| `artifact_integrity_failed` | artifact collection | failed/withheld；不释放内容 |
| `review_contract_invalid` | review collection | failed；run 不得标记 completed |
| `terminal_audit_conflict` | audit | 保留首个 terminal，拒绝覆盖并进入恢复 |

## 7. GUI 最小 live read model

`external-agent-live-read-model/v1` 只提供 GUI 真正需要的安全投影：

- Agent 中文名称、transport、capability、readiness、session 和当前任务；
- work item 的 role/state/approval 状态；
- 最近的有序事件安全摘要；
- approval、artifact integrity 和 recovery item；
- 汇总计数、stable reason code 与中文标签。

所有集合都有 `maxItems`，所有可见摘要有长度上限。投影不包含原始工具输出、凭据、绝对路径、进程参数或外部 session 原文。Stage 82 fixture 固定 `execution_authorized=false`、`dispatch_enabled=false`。

## 8. 测试计划

### 8.1 当前 Stage 82 自动契约测试

- 两个 schema 通过 draft 2020-12 自校验，两个 fixture 通过 schema；
- 覆盖三类 transport 与 Planner/Executor/Reviewer；
- 验证 dispatch exact binding 与危险旁路字段不存在；
- 验证 event 顺序、dedup、唯一 terminal 和 outcome unknown；
- 验证 failure matrix 与文档一致；
- 验证 GUI 投影有界、中文默认、零执行授权。

### 8.2 后续 adapter conformance harness

真实实现前必须新增 transport-neutral conformance suite：相同 fixture 分别喂给 ACP、CLI、local process adapter fake，验证 identity/version drift、TTL、session mapping、approval revocation、idempotency replay、event gap、disconnect、cancel 和 artifact digest。fake suite 仍不得调用真实 Agent。

### 8.3 后续 live integration

独立授权后，先完成一个只读 live status adapter 的 probe design gate；再逐步验证单 work-item dispatch、stream event/artifact/review、cancel/recovery，最后验收 Planner -> Executor -> Reviewer。每一步都必须有 started/terminal audit、故障注入、进程树回收和公开输出 secret scan。

## 9. MVP 验收线

MVP 必须同时证明：

1. 至少三类外部 Agent implementation/transport 共用同一主流程；
2. GUI 展示真实状态、任务、事件、审批、artifact 和 recovery；
3. 用户确认 collaboration plan 并对 dispatch 显式审批；
4. Planner -> Executor -> Reviewer 闭环真实完成；
5. event、artifact、review、retry、cancel、outcome unknown 各有真实验收路径；
6. 任一 Agent 不可用时 fail closed，且公开投影 bounded、deterministic、无凭据。

## 10. Stage 82 停止线

- 不调用 Agent；
- 不启动 session；
- 不探测 live readiness；
- 不读取真实 approval ledger；
- 不写真实 ledger 或 audit；
- 不新增第三个真实 operation；
- 不实现网络 adapter、服务、数据库或后台任务；
- 不改变 fixed Git status 与 fixed Pi print 的执行边界；
- 不把 schema、fixture、readiness 或 approval 示例解释为执行授权。

## 11. 下一阶段入口

下一候选是 **Stage 83：一个外部 Agent 的只读 live status adapter design gate**。该阶段应先选择不启动 session、不发送 prompt、不读取凭据的 observation surface，并再次明确请求授权；若无法证明无副作用和有界 evidence，则保持 deferred。
