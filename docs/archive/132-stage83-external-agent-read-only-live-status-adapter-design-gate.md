<!-- parents: archive/131-stage82-external-agent-adapter-contract-and-mvp-boundary.md, 130-gui-first-external-agent-control-plane-target.md -->
<!-- relates: archive/121-acp-readiness-collection-design-gate.md, archive/122-acp-readiness-collector-and-dispatch-binding.md, 48-adapter-runtime-interface.md -->

# 132 — Stage 83 外部 Agent 只读 Live Status Adapter Design Gate

> 状态：**design-only 完成；reader、producer 和真实 observation 均未授权**
> 日期：2026-07-27
> 目标：`omp-acp`（OMP/Pi via QwenPaw ACP）
> 契约：`../adapters/external-agent-status-snapshot.schema.json`、`../adapters/external-agent-live-status-adapter.schema.json`

## 1. 结论

Stage 83 选择 **adapter-owned atomic snapshot（adapter 拥有的原子状态快照）** 作为首个外部 Agent 只读 live status observation surface。未来 Harness reader 只能读取固定机器本地路径：

```text
.runtime/external-agent-status/omp-acp.v1.json
```

Stage 83 不实现 reader，不创建该文件，也不启动 producer。schema 和 fixture 只冻结未来 Stage 84 的输入、文件安全边界、TTL、identity/producer binding、normalized evidence、GUI 映射和失败语义。

首个目标使用现有 `omp-acp` socket，但 snapshot/evidence schema 保持 transport-neutral。未来其他 Agent 必须复用同一 contract，不能复制 OMP 专用主流程。

## 2. 方案比较

### A. Adapter-owned 原子状态快照（采用）

优点：Harness 只做固定文件读取；不启动进程、不连接 ACP、不启动 session、不发送 prompt、不调用模型、不读取凭据，也不访问网络。输入可通过 strict schema、固定路径、64 KiB 限制、TTL 和 producer binding 做 fail-closed 验证。

代价：快照 producer 属于外部 host/adapter，Stage 83 无法证明它已存在或真实安全。producer 与其 reviewed binding 必须在后续独立 gate 中实现和验收；没有快照时只返回 stable blocked/unknown，不降级到主动 probe。

### B. 固定 CLI status（deferred）

即使参数固定，它仍会新增第三个真实进程 operation，并需要 executable trust、固定参数、环境 allowlist、timeout、bounded I/O、Job Object、started/terminal audit 和真实副作用验证。当前不授权。

### C. ACP handshake（deferred）

handshake 会连接 transport，可能启动或改变连接/session 生命周期，也可能触发凭据或网络行为。它不符合本阶段零连接停止线。

## 3. 数据流与事实权威

```text
外部 reviewed producer
  -> temp file + fsync/close + atomic replace
  -> 固定 .runtime snapshot
  -> future bounded Harness reader
  -> normalized live-status evidence
  -> Stage 82 GUI read model mapping
```

producer 拥有外部 runner list 的原始观察。Harness 只拥有：

- 固定路径是否可安全读取；
- snapshot/schema/producer/target binding 是否有效；
- freshness、replay 和 stable-read 判断；
- normalized evidence 与 GUI 投影；
- blocked/stale/unavailable 原因。

Harness 不拥有外部 Agent 的真实 session、模型、工具或原始 transport 状态，也不得把 runner listed 解释为 ready。

## 4. Snapshot contract

`external-agent-status-snapshot/v1` 只包含：

- content-addressed `snapshot_id`；
- 单调 `generation` 和 `complete=true`；
- timezone-aware `observed_at`；
- producer id/version/reviewed binding；
- target agent/adapter/implementation/transport/capability manifest binding；
- `transport_presence=listed|missing|unknown`；
- 安全 runner alias、`session_state=closed|open|unknown`；
- 本 observation surface 固定不提供 event cursor；
- producer 的无副作用 attestation。

schema 不接受 endpoint、PID、process path、原始 session identity、stdout/stderr、工具输出、凭据、token 或自由原文错误。

## 5. 固定文件读取边界

Stage 84 reader 如获授权，必须同时满足：

- production path 固定为 `.runtime/external-agent-status/omp-acp.v1.json`；
- 不提供 production path override；测试只能使用显式 fixture-only helper；
- project containment，目标必须是单一 regular file；
- symlink、Windows reparse point、hardlink 和目录均 fail closed；
- 最大 64 KiB，严格 UTF-8、单一 JSON object、`additionalProperties=false`；
- 打开前后 stat/identity/size 保持一致，否则视为并发替换并重试一次或 blocked；
- reader 不写文件，不修复、不删除、不覆盖 snapshot；
- producer 必须 temp-write 后 atomic replace，partial snapshot 不接受；
- snapshot generation 不得回退或在内容变化时复用。

`.runtime/` 保持 gitignored，不提交真实 observation、session 或本机路径。

## 6. Freshness、binding 与状态机

默认 TTL 为 15 秒，允许 1-60 秒。评估时间显式注入，便于 deterministic 测试：

- observation 晚于 evaluation：blocked；
- evaluation 超过 expiry：stale；
- generation 回退或 snapshot id 重放：stale/blocked，不猜测新鲜；
- target 或 producer binding 漂移：blocked；
- runner missing：unavailable；
- runner listed：`observation_status=observed`，但 `readiness_status=unknown`；
- open session 且没有 Harness `run_id + attempt_id` mapping：blocked，不能把外部会话认领为当前 run。

normalized evidence 永远固定：

```text
sufficient_for_dispatch = false
execution_authorized = false
session_binding = null
```

## 7. GUI 映射

| Observation | Agent status | Readiness | GUI 中文语义 |
|:---|:---|:---|:---|
| `observed` / runner listed | `unknown` | `unknown` | Runner 已列出，未证明就绪 |
| `unavailable` / runner missing | `disconnected` | `unknown` | 目标 Runner 未观察到 |
| `stale` | `stale` | `stale` | 状态观察已过期 |
| `blocked` | `blocked` | `blocked` | 状态证据绑定或文件边界无效 |

即使 snapshot 报告 `session_state=open`，GUI 也不创建 Harness session projection；只有独立 session mapping contract 才能绑定 run/attempt。

## 8. Failure matrix

| Failure code | 处置 |
|:---|:---|
| `status_source_missing` | blocked；等待 producer 发布固定 snapshot |
| `status_source_not_regular` | blocked；拒绝目录、设备或其他文件类型 |
| `status_source_indirection_blocked` | blocked；拒绝 symlink/reparse/hardlink |
| `status_source_too_large` | blocked；不读取超过 64 KiB 的内容 |
| `status_source_unreadable` | blocked；不容错猜测编码或部分 JSON |
| `status_source_schema_invalid` | blocked；strict schema 失败 |
| `status_snapshot_incomplete` | blocked；未完成 atomic publication |
| `status_snapshot_replayed` | stale；generation/snapshot identity 未前进 |
| `status_observation_from_future` | blocked；时间关系无效 |
| `status_observation_expired` | stale；重新等待 producer observation |
| `status_identity_binding_mismatch` | blocked；target identity/version 漂移 |
| `status_producer_binding_missing` | blocked；没有 reviewed producer binding |
| `status_producer_binding_drift` | blocked；producer version/binding 漂移 |
| `status_target_not_observed` | unavailable；不回退到主动 probe |
| `status_unbound_session_observed` | blocked；外部 open session 未绑定 Harness attempt |
| `status_projection_invalid` | blocked；不得释放不符合 GUI contract 的投影 |

公开 finding 只释放 stable code 和安全中文提示，不释放文件原文、外部错误、session identity 或 producer 内部信息。

## 9. 测试计划

### 9.1 Stage 83 当前测试

- 两个 schema 通过 draft 2020-12 自校验，fixture 通过；
- 固定目标、固定路径、64 KiB、TTL 和无 path override；
- regular-file/containment/indirection/stable-read/atomic-replace policy；
- 零进程、零 ACP 连接、零 session/prompt/model/credential/network/write；
- normalized evidence exact binding、readiness unknown、无 session/event cursor、无 dispatch authority；
- GUI mapping 与 Stage 82 enum 兼容，observed 永不映射为 ready；
- failure matrix、替代方案与停止线一致。

### 9.2 Stage 84 reader 测试门槛

实现前必须新增失败测试覆盖：fixed path missing、目录、symlink、reparse point、hardlink、oversize、UTF-8/JSON/schema 错误、partial snapshot、stable-stat drift、future timestamp、expiry、generation replay、producer/target drift、runner missing、unbound open session 和 projection failure。

reader 测试只读 fixture 或临时 `.runtime`，不得启动 producer 或连接 Agent。

### 9.3 Producer/probe 独立 gate

任何真实 producer 必须单独证明它如何取得 runner list、是否启动进程/连接 ACP/访问网络/读取凭据、如何原子写入、如何受信绑定及如何回收。Stage 83 和未来 reader implementation 都不自动授权 producer。

## 10. Stage 83 停止线

- 不实现 reader；
- 不启动进程；
- 不连接 ACP；
- 不启动 session；
- 不发送 prompt；
- 不调用模型；
- 不读取凭据；
- 不访问网络；
- 不创建真实 snapshot；
- 不写 `.runtime`、ledger 或 audit；
- 不新增第三个真实 operation；
- 不授予 dispatch authority；
- 不把 runner listed、session state 或 fixture evidence 解释为 readiness。

## 11. 下一阶段入口

下一候选是 **Stage 84：bounded atomic snapshot reader implementation**。它只能实现固定文件的安全读取和 normalized evidence/GUI projection，不得实现 producer、CLI probe、ACP handshake、session mapping 或 dispatch。Stage 84 开始前仍需再次明确授权。
