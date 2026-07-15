# 55 — Release Notes：Orchestration Read-Model CLI 第一版

## 阶段定位

本阶段是 Stage 15「UI / 看板前的后端准备」的第一版收口。

之前 Stage 9-12 把中枢台后端文档立了起来（vision / adapter runtime interface / capability routing / control plane state），Stage 13-14 定义了 API 边界与最小编排闭环，Stage 15 则进一步回答：在真正进入 UI / 服务化 / 数据库之前，后端能不能先给每一类页面提供一个**最小只读 CLI read model**？

本阶段的答案是：可以。我们用一组只读 `orchestration *` 命令，覆盖了 54 中定义的六类页面视角，作为后续 UI read model 的最小雏形。

## 已实现的命令

所有命令都属于 `orchestration` 命名空间，**只读**，默认人类可读输出，支持 `--json`。

| 命令 | 页面视角 | 数据来源 / 说明 |
|:---|:---|:---|
| `orchestration overview` | 总览页 | task / event ledger 聚合 |
| `orchestration task list` | 任务列表 | task ledger，支持 `--status` 过滤 |
| `orchestration task get` | 任务详情 | task ledger + event timeline |
| `orchestration run list` | 执行列表 | envelope-scoped，从单个 adapter execution envelope 提取 request/response 摘要 |
| `orchestration run inspect` | 执行详情 | `runtime report` 薄包装，按 `(task_id, request_id, envelope)` 聚合 |
| `orchestration approval list` | 审批列表 | envelope-scoped，从 `approval_record` 提取摘要，支持 `--status` 过滤 |
| `orchestration approval get` | 审批详情 | envelope-scoped，返回 approval 详情 + 关联 request 安全摘要 |
| `orchestration artifact list` | 产物列表 | envelope-scoped，遍历所有 artifact 类型，支持 `--type` / `--request-id` 过滤 |
| `orchestration artifact get` | 产物详情 | envelope-scoped，返回 artifact 详情 + 关联 request 安全摘要 |
| `orchestration report generate` | 报告页 | `runtime report` 薄包装，按 `(task_id, request_id, envelope)` 实时聚合 |

## 资源边界

- **Task**：直接来自现有 task ledger 读取逻辑（`tasks.py`），与 `task status` / `task events` 共享 fallback。
- **Run / Approval / Artifact**：当前都是 **envelope-scoped read model**，没有引入独立的 Run / Approval / Artifact 持久集合。它们从单个 adapter execution envelope 提取，只反映该 envelope 内的状态。
- **Report**：当前是 **runtime-report-backed**，每次 `report generate` 都是实时聚合，不缓存、不沉淀为独立 Report 集合。`report list` / `report get <report_id>` 仍未实现。

这意味着：本阶段补的是「页面能看到什么」的雏形，而不是「页面背后的服务/数据库」。

## 安全边界

本阶段保持与之前一致的安全边界：

- 不写 ledger、draft、envelope 或任何项目内文件。
- 不执行真实 adapter。
- 不访问网络。
- 不引入服务、API、数据库、UI。
- 不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- `artifact get` / `approval get` 中的关联 request 摘要仅保留 id、adapter/operation/target、risk_level、capability、dry_run、requires_approval 等安全字段。

## 测试与验证

- `python -m pytest tests -q`：全量通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。
- `git diff --check`：无空白错误。
- GitHub Actions CI：在 Python 3.11 / 3.12 上 pytest + doctor + ledger smoke checks + public_scan 全部通过。

## 文档更新

- 新增本文档 `docs/archive/release-notes/55-release-notes-orchestration-read-models.md`。
- 更新 `docs/00-index.md`：在中枢台后端主线与发布/阶段收口列表中加入 55。
- 更新 `docs/02-roadmap.md`：Stage 15 状态从「设计文档已落地」调整为「read-model CLI 第一版已落地」。
- 更新 `docs/10-cli-poc-usage.md`：新增 Orchestration Read-Model CLI 章节。
- 更新 `README.md` / `README.en.md`：同步 Stage 13-15 状态与已落地能力列表。
- 更新 `tasks/progress.md`：追加 2026-07-09 阶段收口记录。

## 已知限制与后续建议

1. **Run / Approval / Artifact 仍 envelope-scoped**：真正的跨 envelope / 跨 task 历史查询，需要后续引入独立集合资源或索引。
2. **Report 未持久化**：`orchestration report generate` 是实时聚合；`report list` / `report get` 需等 Report storage 设计后再实现。
3. **尚未进入受控写入 orchestration 命令**：如 `orchestration run`、`orchestration approval resolve`、`orchestration task submit` 等仍只是 53 中的草案。
4. **进入受控写入前建议**：先明确 dry-run / commit 边界，以及 capability routing 结果如何与 guardrail preflight handoff（即 routing 输出如何成为 `runtime plan` / `adapter plan` 的输入）。

## 阶段结论

Stage 15 第一版目标已达成：六类页面视角都有了一个最小只读 CLI read model。下一阶段可以继续把 Stage 10-12 的后端抽象打细，或在条件成熟时进入 Stage 14 的受控编排闭环实现。
