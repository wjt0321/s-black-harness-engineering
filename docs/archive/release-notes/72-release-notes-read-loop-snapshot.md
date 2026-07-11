# 72 — Release Notes: Read-Loop Snapshot（Stage 12 第二拍）

<!-- parents: 50-control-plane-state-model.md -->
<!-- relates: 53-minimal-orchestration-loop-cli-draft.md, 58-orchestration-run-controlled-execution-design.md, 60-orchestration-run-lifecycle-events-design.md -->

## 阶段定位

本文是 Stage 12 控制面状态模型第二拍的阶段收口 release notes：

> 在 Routing Decision Snapshot 已被 Run Preview 安全引用之后，进一步把 `orchestration run --dry-run` 的真实结果投影为 bundling Run Preview + candidate Event summaries + Report Preview 的只读闭环 snapshot。

它明确当前已闭合的链路是：

```text
Registry → Routing → Constraints/Trace → Routing Snapshot → Run Preview → Event/Report Read Loop
```

全部仍是 **ephemeral read model / 非持久 / 非执行**。

## 已交付能力

### 1. `OrchestrationReadLoopSnapshot` 只读闭环 snapshot

- 模块：`agent_runtime/orchestration_read_loop_snapshot.py`
- Schema version：`control-plane/read-loop/v1`
- 字段：
  - `schema_version` / `snapshot_id` / `status`
  - `run`：Run Preview，含 `task_id`、`request_id`、`adapter_id`、`capability`、`operation`、`mode`、`risk_level`、`requires_approval`、`requires_dry_run`、`plan_hash`、可选 `routing_snapshot_id`、lineage；`pass` 时 `run.status=planned`、`run.gate_status=ready`；`needs_approval` 时 `run.status=planned` 但 `run.gate_status=pending_approval`；blocked/needs_input/error/validation_failed 时 `run.status` 与 `run.gate_status` 一致。
  - `events`：candidate Event summaries，仅 `event_type` / `status=planned` / `metadata_keys`；不伪造 `event_id` 或 `timestamp`。
  - `report`：Report Preview，`status=preview`，含 `gate_status`、`status_summary`、candidate event/artifact 计数与类型分布、`requires_approval`、`next_action`、仅 rule_ids 的 finding 摘要；无持久 `report_id`。
  - `source`：安全标识（task_id / request_id / requested_capability）。
- `snapshot_id` 由最终安全 payload（去掉 `snapshot_id`）的 canonical SHA-256 哈希确定性生成，无时间戳/随机数/进程状态。

### 2. CLI：`orchestration run --dry-run --snapshot`

- 默认 `orchestration run --dry-run` 输出与 `plan_hash` 严格兼容。
- 显式传入 `--snapshot` 时输出 read-loop snapshot JSON 或 compact 人类可读摘要。
- `--commit` 模式下传入 `--snapshot` 或 `--routing-snapshot-id` 均被明确拒绝（`blocked`），不写任何文件/ledger。

### 3. 安全边界

- 不写入 task/event/run ledger。
- 不生成持久 Run / Event / Report 对象。
- 不执行真实 adapter、不访问网络、不读取凭据。
- 不回显完整 input/output schema、原始 target、policy 原文、finding message 或 secret。

## 未实现 / 仍后续

- snapshot 与持久化 Run/Event/Report 集合的真实衔接。
- 独立 Run storage / Run collection API。
- 真实 adapter execution、UI、service、DB。

## 验收检查清单（阶段冻结候选）

| 检查项 | 状态 |
|:---|:---|
| `agent_runtime/orchestration_read_loop_snapshot.py` 实现完成 | ✅ |
| `agent_runtime/cli.py` `--snapshot` flag 与 commit 拒绝逻辑 | ✅ |
| `tests/test_orchestration_read_loop_snapshot.py` 覆盖结构/阻断/输入/needs_approval/gate_status/确定性/hash/source mutation/无敏感/CLI/无写入 | ✅ |
| `pytest tests -q` 全量通过 | ✅ |
| `python -m agent_runtime.cli doctor` PASS | ✅ |
| `python tools/public_scan.py` OK | ✅ |
| `git diff --check` 无空白错误 | ✅ |
| 文档更新：`000-stage-digest.md`、`02-roadmap.md`、`10-cli-poc-usage.md`、`50-control-plane-state-model.md`、`51-backend-first-api-boundary.md`、`52-minimal-orchestration-loop.md`、`53-minimal-orchestration-loop-cli-draft.md` | ✅ |
| 进度账本与 handoff 更新 | ✅ |

## 建议里程碑版本

- 建议 tag：`v0.12.1-orchestration-read-loop-snapshot`（或保留 `v0.12.0-orchestration-foundation` 基线，将本阶段作为 foundation 后的第一个补丁/小特性迭代）。
- 理由：本拍未引入新的受控写入协议或持久化存储，是在 `v0.12.0-orchestration-foundation` 之上对控制面 read model 的增强；semver  patch 级增量合适，同时保留 orchestration 命名以明确主线。
- 冻结前仍需确认：
  1. 是否有未归档的 release notes / dry-run / smoke 文档需要归档。
  2. `docs/00-index.md` 是否已索引新文档。
  3. 是否存在临时产物（`.superpowers/` 等）未迁移。
  4. 是否已得到主控对阶段沉淀素材的书面确认。

## 一句话总结

Stage 12 控制面状态模型已把“路由决策 → Run 预览 → Event/Report 预览”串成一条只读、确定性、可消费的 read-loop snapshot；下一步才考虑与持久化 Run/Event 集合的衔接，而不是跳到真实执行。

## 后续状态补充

- 实际冻结 commit：`0419a04`。
- 实际 tag：`v0.12.1-orchestration-read-loop-snapshot`（annotated tag，已 push）。
- 冻结后已完成 README、AGENTS.md、Stage Digest、Roadmap、Versioning Governance、handoff、progress 等文档口径同步。
- 当前工作树干净，下一拍为 post-freeze recovery lineage aggregation read model。
