# 19. Runtime Report 聚合报告

## 目标

在只读 CLI 中新增 `runtime report` 子命令，为指定 task + adapter request 生成一份聚合报告。报告把 task 快照、事件流摘要、adapter execution envelope 摘要、runtime gate 状态、runtime ledger audit 状态汇总到一处，并给出 blockers 与 next_action 建议。

## 边界

- 只读：不执行网络请求、不写真实 ledger/envelope、不读取 `.env` / credential 文件。
- 脱敏：输出不得回显完整 `target`、`input` payload、`evidence` description、`raw_ref`、`decision_ref`。
- 不修改 `AGENTS.md`。

## CLI 用法

```bash
python -m agent_runtime.cli runtime report \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json
```

可选参数：

- `--tasks-file <path>`：覆盖默认 `tasks/tasks.jsonl`。
- `--events-file <path>`：覆盖默认 `tasks/events.jsonl`。
- `--json`：输出 JSON 聚合报告。

## 实现

### 新增模块

`agent_runtime/runtime_report.py` 提供：

- `RuntimeReportResult` dataclass
  - `status: str`
  - `task_id: str`
  - `task_status: str | None`
  - `task_snapshot: dict[str, Any]`（脱敏后的 task 快照）
  - `event_summary: dict[str, Any]`（事件数量与最近事件列表）
  - `envelope_summary: dict[str, Any] | None`（envelope inspect 摘要）
  - `gate: dict[str, Any] | None`（脱敏后的 gate 状态）
  - `ledger: dict[str, Any] | None`（ledger audit 结果）
  - `blockers: list[str]`（人类可读的 blocker 列表）
  - `next_action: str | None`

- `check_runtime_report(...)`
  1. 调用 `find_task` 与 `find_task_events` 读取 task 与事件。
  2. 调用 `inspect_runtime_draft` 校验 envelope 并生成摘要（复用已有的 envelope 校验与脱敏逻辑）。
  3. 调用 `check_runtime_gate` 获取 gate 状态与建议 event draft。
  4. 调用 `check_runtime_ledger` 获取跨系统审计结果。
  5. 汇总 `blockers` 与 `next_action`。

### 状态汇总规则

`runtime report` 的整体 `status` 取所有子检查中最严重的状态：

```text
error > blocked > needs_approval > needs_input > warn > pass
```

常见 blocker：

- task 不存在。
- task 处于 `finished` / `failed` 终态。
- envelope 校验失败。
- ledger audit 出现 error。
- gate `can_proceed` 为 false。

`next_action` 按优先级给出：

- 若存在 error → "Fix errors before proceeding."
- 若 task 终态 → "Task is terminal; no new actions."
- 若 gate 需要审批 → "Wait for user approval."
- 若 gate 需要输入 → "Provide missing input."
- 若 gate 通过 → "Proceed with adapter execution."

### CLI 输出

文本输出分块：

```text
REPORT
Task: task-20260703-001 (running)
Events: 4 events, latest: finished
Envelope: 4 artifacts, 2 requests, 1 approvals, 1 responses
Gate: can_proceed=true
Ledger: pass (tasks=1, events=4, requests=2, execution_events=2)
Blockers: none
Next: Proceed with adapter execution.
```

JSON 输出结构与 `RuntimeReportResult.to_dict()` 一致，所有字符串值均经过脱敏处理。

## 测试

新增 `tests/test_runtime_report.py`，覆盖：

1. 正常文本输出包含 task、gate、ledger、next action 等摘要。
2. JSON 输出脱敏，不含完整 target / input / raw_ref / decision_ref / evidence 描述。
3. terminal task 时报告 BLOCKED/不能推进。
4. 只读：运行前后 `tasks.jsonl`、`events.jsonl`、`envelope.json` 字节不变。

## 相关文档

- `docs/14-task-runtime-bridge.md`
- `docs/15-runtime-ledger-audit.md`
- `docs/16-runtime-plan.md`
- `docs/17-runtime-planning-bridge.md`
