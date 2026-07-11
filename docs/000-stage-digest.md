# 000 — Stage Digest

> **新会话先读这份，不要先翻整仓文档。**

## 文档池规模

- docs/ 活跃文档：~35 个
- 归档文档：`docs/archive/`（release-notes / dry-runs / smoke-regression）
- 全仓 .md 文件：~140 个
- **文档维护规则：`docs/MAINTENANCE.md`**

## 当前基线

- 稳定基线：`v0.12.0-orchestration-foundation`
- 冻结 commit：`38b4b69`
- 当前 HEAD：以 `git rev-parse --short HEAD` 为准

## 当前阶段

- **Stage 15.99 — Run Lineage / Recovery Read Model 第一版**
- 当前成果：retry / fallback lineage 已经形成 **可写 + 可读** 的最小闭环

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

- preflight 将 routing decision passthrough 到 guardrail，不越界替 guardrail 做阻断判断。
- cost / latency / availability / 在线状态仍未实现，保留给后续阶段。
- 文档已更新：`docs/49-capability-routing-model.md`、`docs/02-roadmap.md`、`docs/10-cli-poc-usage.md`。

## 现在已经能做什么

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

- **优先方向：Stage 11 — Capability Routing Model（约束路由第一版已落地，继续巩固）**
- 入口文档：`docs/49-capability-routing-model.md`
- 目标：在 source-backed registry 投影与 constraint filter + preference rank 已对齐的基础上，继续巩固 Stage 11；不急着跳真实执行

## 重要约束

- 仍然**不做真实 adapter execution**
- 仍然**不做 UI / service / DB**
- 编码默认继续交给 Kimi；主控负责审核、文档、提交、push

## 一句话理解当前项目

这项目现在的重点不是继续堆零散功能，而是：

> 在保持受控写入边界的前提下，把 orchestration control-plane 的恢复链路、read model 和后端主线继续做扎实。
