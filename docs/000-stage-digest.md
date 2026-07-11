# 000 — Stage Digest

> **新会话先读这份，不要先翻整仓文档。**

## 文档池规模

- docs/ 活跃文档：~35 个
- 归档文档：`docs/archive/`（release-notes / dry-runs / smoke-regression）
- 全仓 .md 文件：~140 个
- **文档维护规则：`docs/MAINTENANCE.md`**

## 当前基线

- 当前稳定基线：`v0.12.1-orchestration-read-loop-snapshot`
- 冻结 commit：`0419a04`
- 上一 foundation 基线：`v0.12.0-orchestration-foundation`（commit `38b4b69`）
- 当前 HEAD：以 `git rev-parse --short HEAD` 为准；`0419a04` 是本里程碑冻结代码基线，后续仅文档收口提交可位于其后

## 当前阶段

- **Stage 12 — Control Plane State Model（read-only loop 第一版已冻结）**
- 当前成果：Registry → Routing → Constraints/Trace → Routing Snapshot → Run Preview → Event/Report Read Loop 已闭合为 **只读 / ephemeral / 非执行** 的 read model 链路

### Stage 10 基线（保留）

- `adapters/adapters.sample.json` 是 adapter/capability/risk 的单一事实源。
- `agent_runtime.adapter_registry` 提供 source-backed 投影，供 `orchestration adapter list/inspect`、route preview、preflight 共同消费。
- 投影字段包括 adapter_id、display_name、kind、capabilities、risk_level、enabled、功能开关（background/artifacts/approval_roundtrip 等）、timeout_profile、指向该 entry 真实 input/output schema 的 JSON Pointer。
- route preview 与 preflight 基于此投影生成路由决策，避免查询 registry 与路由 registry 漂移。

### 新进落地：Stage 11 — Capability Routing Model 约束路由第一版

- `RouteConstraints` 已接入 `orchestration route preview` / `orchestration preflight`。
- 支持约束：`--preferred-adapter`、`--max-risk`、`--require-background`、`--require-artifacts`。
- 路由流程：capability match → constraint filter → preference rank。
- 默认未传约束参数时，route/preflight 保持原有输出字段不变；仅在显式使用约束 flag 时才输出 `routing_constraints` / `rejected_candidates` 等新增字段。
- 新增 `--explain` 决策解释 trace：暴露 capability-matched / constraint-rejected / eligible / selected / fallback 候选及 deterministic reason，trace 由 `preview_route` 内部中间结果直接构造，preflight 复用不复算，为 Stage 12 状态模型做准备。

### 新进落地：Stage 12 — Control Plane State Model 第一拍

- 新增 `RoutingDecisionSnapshot`：把 Stage 11 route/preflight 决策投影为稳定、compact、只读的控制面状态对象。
- `snapshot_id` 由 canonical safe payload 的 SHA-256 内容哈希确定性生成，无时间戳/随机数/进程状态。
- CLI：`orchestration route snapshot` 与 `orchestration preflight --snapshot`。
- snapshot 包含分层的 routing 状态与 guardrail 状态（preflight snapshot），不写 ledger、不生成持久 Run、不执行真实 adapter。

### 新进落地：Routing Snapshot → Run Preview 安全引用第一拍

- `orchestration run --dry-run` 新增可选 `--routing-snapshot-id sha256:<64hex>`。
- 引用只接受 `sha256:<64 lowercase hex>` 格式；非法值返回 `needs_input`，绝不读取任意路径或把 JSON 当参数。
- 引用进入 `RunDryRunResult`、candidate artifact refs、`run_planned` candidate event metadata keys 与 `plan_hash` canonical payload。
- 默认不传时旧输出与 `plan_hash` 完全兼容；传入时相同输入重复运行产生 byte-equivalent JSON，`plan_hash` 随 snapshot id 变化。
- retry / fallback dry-run 同样支持引用，lineage 与 routing snapshot 各自独立。
- 不校验 snapshot 是否存在于磁盘，明确其为 content-addressed reference contract，不是持久化产物假装已落地。
- 文档已更新：`docs/50-control-plane-state-model.md`、`docs/52-minimal-orchestration-loop.md`、`docs/02-roadmap.md`、`docs/10-cli-poc-usage.md`。

- preflight 将 routing decision passthrough 到 guardrail，不越界替 guardrail 做阻断判断。
- cost / latency / availability / 在线状态仍未实现，保留给后续阶段。

### 新进落地：Run Preview → Event / Report 只读投影闭环

- `orchestration run --dry-run --snapshot` 基于真实 `RunDryRunResult` 一次性构造 `OrchestrationReadLoopSnapshot` 只读闭环 snapshot。
- snapshot 包含 Run Preview（`status=planned/preview`）、candidate Event summaries（`status=planned`，不伪造 event_id/timestamp）、Report Preview（`status=preview`，无持久 report_id）。
- `snapshot_id` 由最终安全 payload（去掉 `snapshot_id`）的 canonical SHA-256 哈希确定性生成，无时间戳/随机数/进程状态。
- 默认不传 `--snapshot` 时，`orchestration run --dry-run` 旧输出与 `plan_hash` 严格兼容；传入时仅新增 snapshot 字段。
- `--commit` 模式下传入 `--snapshot` 会被明确拒绝（`blocked`），本拍仅 `--dry-run` preview 支持。
- 不写入 ledger、不生成持久 Run/Event/Report、不执行真实 adapter；明确为 ephemeral read model。
- Routing Snapshot → Run Preview → Event/Report read-only loop 已闭合，但仍明确非持久/非执行。

## 现在已经能做什么

- 已冻结里程碑 `v0.12.1-orchestration-read-loop-snapshot`（commit `0419a04`），包含 Stage 10–12 的 registry/routing/state read model 闭环。
- `orchestration run --dry-run` 可安全引用 `orchestration route snapshot` / `orchestration preflight --snapshot` 的内容寻址 snapshot id
- retry / fallback commit 第一版已落地
- `orchestration run inspect` 可见 lineage
- `orchestration run list` 可见紧凑 lineage 标识
- `orchestration report generate` 可见 lineage 安全摘要
- `python -m agent_runtime.cli docs context` 可输出恢复入口
- `orchestration adapter list` / `inspect` 可查询 source-backed adapter capability registry；`orchestration route preview` / `orchestration preflight` 已基于同一投影生成路由与 preflight 决策

## 下次恢复顺序

1. 先读：`docs/000-stage-digest.md`（本文件）
2. 再跑：`python -m agent_runtime.cli docs context`
3. 再读：`docs/02-roadmap.md`
4. 如需接续上轮会话：读最新 `tasks/handoff-*.md`

## 下一步做什么

- **已冻结**：`v0.12.1-orchestration-read-loop-snapshot`（commit `0419a04`，annotated tag 已创建并 push）。工作树干净，post-freeze 文档口径已同步。
- **下一拍（post-freeze）**：优先把 read-loop snapshot / lineage 与 **recovery lineage aggregation read model** 做扎实。
  - 目标：在现有 `orchestration run inspect` / `orchestration run list` / `orchestration report generate` 的 lineage 字段基础上，为同一 task 的 retry/fallback 链提供聚合只读视图（例如 root request、latest attempt、fallback chain、当前有效 plan_hash）。
  - 输入：`tasks/events.jsonl` 中的 `run_planned` / `run_draft_exported` 事件与 envelope draft 的 lineage metadata。
  - 输出：新的只读 CLI read model（如 `orchestration run lineage --task-id <id>`）或扩展现有 `run inspect` 的聚合摘要；明确不持久化、不执行 adapter。
  - 边界：只读、无网络、无凭据、无 UI/service/DB；若需新事件类型或索引，先走 design doc。
  - 首个建议实现切片：在 `orchestration run inspect` 中新增可选 `--aggregate-lineage` 模式，按 task_id 聚合同一 lineage 链上的全部 request_ids 与状态。
- **入口文档**：`docs/50-control-plane-state-model.md`、`docs/52-minimal-orchestration-loop.md`、最新 `tasks/handoff-2026-07-11-read-loop-snapshot-stage-acceptance.md`。
- **优先方向：Stage 12 — Recovery Lineage Aggregation Read Model**
  - 入口文档：`docs/50-control-plane-state-model.md`
  - 重点：在 read-loop snapshot 冻结基线之上，把 retry/fallback lineage 聚合为 recovery 只读视图，不持久化、不执行 adapter。
- **边界不变**：不进入真实 adapter execution、UI、service、DB。

## 重要约束

- 仍然**不做真实 adapter execution**
- 仍然**不做 UI / service / DB**
- 编码默认继续交给 Kimi；主控负责审核、文档、提交、push

## 一句话理解当前项目

这项目现在的重点不是继续堆零散功能，而是：

> 在保持受控写入边界的前提下，把 orchestration control-plane 的恢复链路、read model 和后端主线继续做扎实。
