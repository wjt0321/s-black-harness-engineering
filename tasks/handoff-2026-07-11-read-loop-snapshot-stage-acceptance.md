# Handoff — 2026-07-11 — Read-Loop Snapshot Stage Acceptance

## 当前基线

- 冻结基线：`v0.12.1-orchestration-read-loop-snapshot`（commit `0419a04`，annotated tag 已创建并 push）。
- 上游 foundation 基线：`v0.12.0-orchestration-foundation`（commit `38b4b69`，已 push）。
- 冻结代码基线为 `0419a04`；当前 HEAD 与工作树状态以 Git 实际输出为准，后续允许仅包含文档同步的收口提交位于该基线之后。

## 本阶段已闭合链路

```text
Registry → Routing → Constraints/Trace → Routing Snapshot → Run Preview → Event/Report Read Loop
```

全部是 **只读 / ephemeral / 非执行**。

## 关键改动

- `agent_runtime/orchestration_read_loop_snapshot.py`：新增 `OrchestrationReadLoopSnapshot`、`build_read_loop_snapshot`、gate_status 分层。
- `agent_runtime/cli.py`：`orchestration run --dry-run --snapshot` flag；commit 分支拒绝 `--snapshot` / `--routing-snapshot-id`；人类输出显示 `gate_status`。
- `tests/test_orchestration_read_loop_snapshot.py`：覆盖 pass/needs_approval/blocked/needs_input、gate_status 分层、无 event_id/timestamp、确定性、hash、source mutation、CLI、无写入。
- 文档：Stage Digest、Roadmap、CLI usage、Control Plane State Model、API Boundary、最小闭环、CLI draft、00-index、progress、本 handoff。
- 阶段收口 release notes：`docs/archive/release-notes/72-release-notes-read-loop-snapshot.md`（按 MAINTENANCE 规则，release notes 归档存放）。

## 审查返工点

1. `run.gate_status` / `report.gate_status` 稳定分层：
   - `pass` → `ready`
   - `needs_approval` → `pending_approval`
   - `blocked` / `needs_input` / `error` / `validation_failed` → 原样传播
2. `tasks/progress.md` 中原“commit 路径透传 `routing_snapshot_id`”条目已标记 `[已撤回]`。

## 未实现 / 不要误读

- 未持久化 snapshot、Run、Event、Report。
- 未执行真实 adapter、未访问网络、未读写凭据。
- 未进入 Stage 16 UI / service / DB。

## 验证状态

- `pytest tests -q` ✅
- `python -m agent_runtime.cli doctor` ✅ PASS
- `python tools/public_scan.py` ✅ OK
- `git diff --check` ✅ 仅 LF/CRLF 警告

## 下一步建议

- **post-freeze 唯一方向**：把 read-loop snapshot / lineage 与 **recovery lineage aggregation read model** 衔接。
  - 目标：为同一 task 的 retry/fallback 链提供聚合只读视图（root request、latest attempt、fallback chain、effective plan_hash）。
  - 入口：`docs/50-control-plane-state-model.md`、`docs/52-minimal-orchestration-loop.md`、本 handoff。
  - 边界：只读、无网络、无凭据、无 UI/service/DB；若涉及新事件类型或索引，先走 design doc。
  - 首个切片：在 `orchestration run inspect` 新增 `--aggregate-lineage` 模式，按 task_id 聚合同一线路链上的 request_ids 与状态。
- 当前里程碑 `v0.12.1-orchestration-read-loop-snapshot`（`0419a04`）已冻结，不再重复冻结。

## 临时产物

- `.superpowers/` 目录不存在，无需迁移。
