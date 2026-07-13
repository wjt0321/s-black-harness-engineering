# 000 — Stage Digest

> **新会话先读这份，不要先翻整仓文档。**

## 文档池规模

- docs/ 活跃文档：~35 个
- 归档文档：`docs/archive/`（release-notes / dry-runs / smoke-regression）
- 全仓 .md 文件：~140 个
- **文档维护规则：`docs/MAINTENANCE.md`**

## 当前基线

- 稳定基线：`v0.12.1-orchestration-read-loop-snapshot`
- 冻结 commit：`0419a04`
- Stage 13 最终收口提交：本轮阶段冻结提交；精确 commit 在最新 handoff 中记录
- 上一 foundation 基线：`v0.12.0-orchestration-foundation`（commit `38b4b69`）
- 本轮按 release notes 收口，不创建新的 semver tag

## 当前阶段

- **Stage 14 — 中枢台最小编排闭环**
- Stage 13 已完成：资源/操作模型与真实 CLI/read models 的 stable、stable（受限）、preview、unavailable 矩阵已冻结。
- 当前任务：将已冻结契约应用到最小、可回放、可审计的本地编排闭环；仍不选择 HTTP/RPC，不启动 service/UI/DB，不执行真实 adapter。

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


### 新进落地：Recovery Lineage Aggregation Read Model

- 新增 `agent_runtime/orchestration_recovery.py`，以现有 `run_planned` / `run_draft_exported` / `run_blocked` event metadata 为索引，确定性聚合同一 recovery chain。
- `orchestration run inspect --aggregate-lineage` 与 `orchestration report generate --aggregate-lineage` 输出 root request、leaf/latest request、attempt count、effective plan hash 与安全 request summaries。
- 多 leaf 不静默猜测 latest，返回 `needs_input`；missing/cross-task parent、cycle、重复 metadata 冲突返回 `validation_failed`。
- 默认未传 flag 时现有 inspect 输出保持兼容；不扫描 drafts、不增加事件类型、不写 ledger、不执行 adapter。
- 设计入口：`docs/73-recovery-lineage-aggregation-read-model.md`。

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
2. 再读：`docs/52-minimal-orchestration-loop.md`
3. 再读：`tasks/handoff-2026-07-13.md`
4. 再跑：`python -m agent_runtime.cli docs context --json`
5. 需要 Stage 13 边界时再读：`docs/51-backend-first-api-boundary.md`
6. 需要 Stage 13 验收事实时再读：`docs/archive/release-notes/76-release-notes-stage13-backend-first-api-boundary.md`

## 下一步做什么

- **Stage 13 已完成**：真实 CLI/read models 的资源/操作契约已完成对账，命令 surface 与关键 flag 已有契约测试。
- **当前优先方向：Stage 14 — 中枢台最小编排闭环**
  - 入口文档：`docs/52-minimal-orchestration-loop.md`
  - 重点：把已冻结契约应用到 Task intent → routing → preflight → dry-run/controlled commit → lifecycle event → projection/replay 闭环。
- **正式延期**：持久化 Run/Event/Report collection、协议、鉴权、UI、service、DB 和真实 adapter execution。
- **边界不变**：不选择 HTTP/RPC，不进入 UI/service/DB，不执行真实 adapter。

## 重要约束

- 仍然**不做真实 adapter execution**
- 仍然**不做 UI / service / DB**
- 后续实现可由任意受控编码 Agent 承担，但必须先消费本 digest、51 设计文档与最新 handoff，并保持验证/提交边界

## 一句话理解当前项目

这项目现在的重点不是继续堆零散功能，而是：

> 在不服务化的前提下，把现有 CLI/read models 收敛为稳定、可由未来入口复用的后端资源与操作契约。
