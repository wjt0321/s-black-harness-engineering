# 35 — Runtime Task Create Commit Smoke / Report Loop

## 阶段定位

本阶段在 `runtime task create --commit` 已实现的基础上，补一条端到端 smoke loop，验证在临时项目副本中可安全地完成：

1. `runtime task create --dry-run`
2. `runtime task create --commit`
3. `runtime event append --dry-run`
4. `runtime event append --commit`
5. `task validate` + `task check-ledger`
6. `runtime report`

本阶段不新增真实写入权限，不修改 task create / event append 的写入边界，只补文档与聚焦测试。

## Smoke Loop 步骤

在临时项目根内准备：

- `tasks/task.schema.json`、`tasks/event.schema.json`、`adapters/execution-envelope.schema.json`
- `policies/*.sample.policy.json`
- 空的 `tasks/tasks.jsonl` 与 `tasks/events.jsonl`
- 候选 task JSON、候选 created event JSON、adapter execution envelope JSON

然后依次执行：

```bash
# 1) task create dry-run
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run

# 2) task create commit
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit

# 3) event append dry-run
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run

# 4) event append commit
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit

# 5) ledger 校验
python -m agent_runtime.cli task validate \
  --record-file tasks/tasks.jsonl --schema task
python -m agent_runtime.cli task validate \
  --record-file tasks/events.jsonl --schema event
python -m agent_runtime.cli task check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl

# 6) runtime report
python -m agent_runtime.cli runtime report \
  --task-id task-20260707-001 \
  --request-id req-20260707-001 \
  --envelope envelope.json \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

## 安全边界

- 所有命令均在 `tmp_path` 构造的临时项目根中执行，不写仓库真实 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。
- 复用已有的 `runtime task create --commit` 与 `runtime event append --commit`，不新增写入目标或写入权限。
- `runtime report` 输出只包含安全摘要：`task_id`、`task_status`、`title_present`、事件数、envelope artifact 计数、gate 阶段、ledger 状态等；不回显完整 `title`、`summary`、`evidence description`、`artifact payload` 或 `secret match`。

## 输出示例

```text
PASS
Task: task-20260707-001 (planned): title_present=True
Events: 1 events, latest=created at 2026-07-07T10:00:00+08:00
Envelope: adapter_request=1
Gate: stage=response, can_proceed=False
Ledger: pass (tasks=1, events=1, requests=1, execution_events=0)
Blockers:
- Gate cannot proceed (stage=response).
Next: Provide missing input.
```

## 实现文件

- `tests/test_runtime_task_create_smoke_loop.py`：端到端 smoke loop 自动化测试。
- `agent_runtime/runtime_report.py`：`_sanitize_task_snapshot` 移除 `title` 等自由文本字段，改为 `title_present`。
- `agent_runtime/cli.py`：`runtime report` 人类输出不再打印完整 title。

## 验证结果

```text
python -m pytest tests/test_runtime_task_create_smoke_loop.py tests/test_runtime_report.py -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

## 下一阶段建议

- 可继续补 `runtime task create --commit` 与 `runtime event append --commit` 在错误场景下的 smoke 组合（如 duplicate task id、schema invalid 后 ledger 未被破坏）。
- 可考虑把本 smoke loop 加入 CI，作为受控写入链路的回归保护。
