# 28 — Runtime Event Append Commit 预备设计

## 阶段定位

本文为下一阶段 `runtime event append --commit` 预留实现上下文。当前只写设计，不实现命令，不修改 Runtime 行为。

上一阶段 `runtime event append --dry-run` 已冻结为：

```text
v0.7.0-runtime-event-append-dry-run
```

它已经跑通 event 写入前门禁：候选 event 读取、schema 校验、task 存在性检查、secret/public scan、模拟 append 后 ledger consistency，以及可选 runtime ledger audit。

下一阶段若继续推进，目标是在严格边界内允许 Runtime 把一个候选 event 追加到 event ledger。

## 非目标

本阶段不应做：

- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不写 adapter envelope。
- 不修改 task snapshot ledger。
- 不覆盖、删除、重排或重写历史 event。
- 不实现批量 import。
- 不实现自动修复 ledger。
- 不读取 `.env`、credential、token 或 keyring。

## 允许的唯一写入

第一版 `runtime event append --commit` 只允许一个动作：

```text
append exactly one JSON object as the last line of an event ledger JSONL file
```

默认目标：

```text
tasks/events.jsonl
```

可选目标：

```bash
--events-file <project-local-safe-jsonl>
```

但即使支持显式 `--events-file`，也必须满足：

- 位于项目根目录内。
- 后缀为 `.jsonl`。
- 不是 `.env`、credential、secret、`.git` internals。
- 不通过 `..` 或符号链接逃逸项目根目录。
- 不写 `tasks/examples.jsonl` 或 `tasks/events.examples.jsonl`，除非后续单独设计样例更新流程。

## CLI 形态建议

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit
```

```bash
type candidate-event.json | python -m agent_runtime.cli runtime event append \
  --stdin \
  --commit
```

可选参数：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--envelope adapters/execution-envelope.examples.json
--json
```

模式规则：

- `--dry-run` 与 `--commit` 互斥。
- 必须显式提供其中一个。
- `--dry-run` 继续保持完全只读。
- `--commit` 写入前必须复用 dry-run 全部检查。

## 写入前检查

`--commit` 写入前必须完成：

1. 读取候选 event。
2. 候选 event 必须是单个 JSON object。
3. 通过 `tasks/event.schema.json`。
4. `task_id` 必须存在于 task ledger。
5. `event_id` 在目标 events ledger 中不得重复。
6. candidate event 内容通过 secret scan。
7. candidate event 内容通过 public scan。
8. 在临时 ledger 中模拟 append。
9. 模拟 append 后 `task check-ledger` 必须通过。
10. 如提供 `--envelope`，模拟 append 后 `runtime check-ledger` 不得产生 error。
11. 输出路径通过 path guard。
12. 写入前记录 events file 原始 byte size。

所有失败都必须在真实写入前返回，不得创建或修改 ledger。

## 写入规则

写入必须遵守 append-only：

- 只追加一行。
- 不修改已有行。
- 不删除已有行。
- 不重排已有行。
- 不格式化整个文件。
- 不压缩 ledger。

写入格式：

```text
json.dumps(candidate, ensure_ascii=False) + "\n"
```

写入前应确保现有文件末尾有换行；如果没有，第一版建议直接 blocked，不自动修复，避免隐式修改历史内容。

## 写入后检查

写入后必须立即运行：

```bash
python -m agent_runtime.cli task validate --record-file <events-file> --schema event
python -m agent_runtime.cli task check-ledger --tasks-file <tasks-file> --events-file <events-file>
```

如提供 envelope，还必须运行等价检查：

```bash
python -m agent_runtime.cli runtime check-ledger \
  --tasks-file <tasks-file> \
  --events-file <events-file> \
  --envelope <envelope>
```

只有写后检查通过，才返回 `PASS`。

## 回滚策略

写入前记录：

- 目标 events file 的 byte size。
- 是否由本命令创建了新文件。

如果写入后检查失败：

1. 尝试把文件截断回原 byte size。
2. 如果本命令创建了新文件且原本不存在，则删除该新文件。
3. 回滚成功后返回失败状态，并说明已回滚。
4. 回滚失败时返回 `error`，提示人工恢复。

禁止静默成功。

## 输出摘要

成功输出只给安全摘要：

```text
PASS
Source: candidate.json
event_id=evt-...
task_id=task-...
event_type=progress
from_status=running
to_status=running
committed=True
ledger_check=pass
runtime_audit=pass
Next: Event appended; review runtime report before further actions.
```

JSON 输出也只包含：

- `status`
- `source`
- `event_id`
- `task_id`
- `event_type`
- `from_status`
- `to_status`
- `committed`
- `ledger_check`
- `runtime_audit`
- `metadata_keys`
- `artifact_count`
- `findings`
- `next_action`

不得输出完整：

- `message`
- metadata values
- artifacts payload
- evidence description
- target
- input payload
- raw_ref
- decision_ref
- secret match

## 建议实现文件

可在现有模块上扩展：

```text
agent_runtime/runtime_event_append.py
```

建议新增结果模型字段：

```text
committed: bool
post_validate: str | None
post_ledger_check: str | None
post_runtime_audit: str | None
rolled_back: bool
rollback_error: str | None
```

建议测试文件：

```text
tests/test_runtime_event_append_commit.py
```

## 最小测试清单

必须覆盖：

- commit pass：追加一行，写后 validate/check-ledger 通过。
- commit pass with envelope：写后 runtime check-ledger 跑通。
- `--dry-run` 仍不写文件。
- `--dry-run` 与 `--commit` 互斥。
- 二者都不提供时报错。
- schema invalid 不写文件。
- missing task 不写文件。
- duplicate event_id 不写文件。
- illegal transition 不写文件。
- secret/public scan blocked 不写文件且不回显匹配值。
- events file 不在项目内 blocked。
- events file 后缀非 `.jsonl` blocked。
- events file 无末尾换行 blocked。
- post-check 失败时回滚。
- rollback 失败时返回 error。
- JSON 输出脱敏。

## 完成条件

下一阶段完成前必须满足：

- `runtime event append --commit` 只追加单行。
- 没有任何 adapter execution。
- 没有网络访问。
- 没有消息发送。
- 没有 credential 读取。
- `python -m pytest` 通过。
- `python -m agent_runtime.cli doctor` 通过。
- `python tools/public_scan.py` 通过。
- 推送前 key pattern scan 通过。
- 新增 release notes 与 handoff 后再打 tag。

建议 tag：

```text
v0.8.0-runtime-event-append-commit
```
