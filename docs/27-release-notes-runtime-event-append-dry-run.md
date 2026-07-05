# 27 — Runtime Event Append Dry-run 阶段收口说明

## 阶段定位

本阶段冻结最小 Controlled Write POC 的第三步：`runtime event append --dry-run`。

它用于在真正向 `tasks/events.jsonl` 追加 task event 之前，先跑通 event 写入门禁：读取候选 event、校验 schema、确认 task 存在、模拟 append 后检查 ledger consistency，并可选运行 runtime ledger audit。该阶段仍保持只读，不写真实 ledger。

## 新增能力

### `runtime event append --dry-run`

从文件读取候选 event：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run
```

从 stdin 读取候选 event：

```bash
type candidate-event.json | python -m agent_runtime.cli runtime event append \
  --stdin \
  --dry-run
```

带 ledger 与 envelope audit：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

## 检查内容

`runtime event append --dry-run` 会执行：

- 候选 event JSON 解析。
- `tasks/event.schema.json` schema validation。
- `task_id` 存在性检查。
- candidate event 内容 secret scan。
- candidate event 内容 public scan。
- 内存/临时文件模拟 append 后运行 ledger consistency。
- 如提供 `--envelope`，模拟 append 后运行 runtime ledger audit。

## 输出摘要

输出只包含安全摘要，例如：

```text
PASS
Source: candidate.json
event_id=evt-20260705-003
task_id=task-20260705-001
event_type=progress
from_status=running
to_status=running
would_append=False
ledger_check=pass
artifact_count=0
Next: Dry-run passed. Use runtime event append --commit (not yet implemented) to persist.
```

JSON 输出同样只暴露安全字段，例如 event/task id、event_type、from/to status、`would_append`、`ledger_check`、`runtime_audit`、`metadata_keys`、`artifact_count`。

不会回显完整 message、metadata values、artifact payload、evidence description、target、input、raw_ref、decision_ref 或 secret match。

## 实现文件

- `agent_runtime/runtime_event_append.py` — dry-run event append 门禁逻辑。
- `agent_runtime/cli.py` — 注册 `runtime event append` 子命令与安全摘要渲染。
- `tests/test_runtime_event_append_dry_run.py` — 测试覆盖。
- `docs/26-runtime-event-append-dry-run.md` — 命令设计与用法。
- `tasks/handoff-2026-07-05-event-append-dry-run.md` — 接续上下文。

## 验证结果

本阶段收口前验证：

```text
python -m pytest -> 243 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

推送前额外执行：

```text
key pattern scan -> OK key scan
```

## 当前限制

- 仅支持 `--dry-run`。
- 不支持 `--commit`。
- 不写 `tasks/events.jsonl`。
- 不写 task ledger。
- 不写 adapter envelope。
- 不执行 adapter。
- 不访问网络、不发送消息。

## 后续建议

下一阶段如果继续推进，建议实现 `runtime event append --commit`，但必须比 draft export commit 更谨慎：

- 只允许 append，不允许修改历史行。
- 写入前复用 dry-run 全部检查。
- 写入前检查 event_id 不重复。
- 写入后重新运行 `task validate`、`task check-ledger`，如有 envelope 则运行 `runtime check-ledger`。
- 失败时回滚本命令追加的最后一行。
- 仍不执行 adapter。

建议下一阶段文档：

```text
docs/28-runtime-event-append-commit.md
```
