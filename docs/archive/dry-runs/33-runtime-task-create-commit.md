# 33 — Runtime Task Create Commit 预备设计

## 阶段定位

本文为下一阶段 `runtime task create --commit` 预留实现上下文。当前只写设计，不实现命令，不修改 Runtime 行为。

上一阶段 `runtime task create --dry-run` 已冻结为：

```text
v0.9.0-runtime-task-create-dry-run
```

它已经跑通 task snapshot 写入前门禁：候选 task 读取、schema 校验、task id 去重、secret/public scan、模拟 append 后 ledger consistency，以及脱敏摘要输出。

下一阶段若继续推进，目标是在严格边界内允许 Runtime 把一个候选 task snapshot 追加到 task ledger。

## 非目标

本阶段不应做：

- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不写 adapter envelope。
- 不写 event ledger。
- 不覆盖、删除、重排或重写历史 task。
- 不实现批量 import。
- 不实现自动修复 ledger。
- 不自动创建对应 event。
- 不读取 `.env`、credential、token 或 keyring。

## 允许的唯一写入

第一版 `runtime task create --commit` 只允许一个动作：

```text
append exactly one JSON object as the last line of a task ledger JSONL file
```

默认目标：

```text
tasks/tasks.jsonl
```

可选目标：

```bash
--tasks-file <project-local-safe-jsonl>
```

但即使支持显式 `--tasks-file`，也必须满足：

- 位于项目根目录内。
- 后缀为 `.jsonl`。
- 不是 `.env`、credential、secret、`.git` internals。
- 不通过 `..` 或符号链接逃逸项目根目录。
- 不写 `tasks/examples.jsonl`，除非后续单独设计样例更新流程。

`--events-file` 只作为 ledger consistency 的只读输入，不作为本命令写入目标。

## CLI 形态建议

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit
```

```bash
type candidate-task.json | python -m agent_runtime.cli runtime task create \
  --stdin \
  --commit
```

可选参数：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
```

模式规则：

- `--dry-run` 与 `--commit` 互斥。
- 必须显式提供其中一个。
- `--dry-run` 继续保持完全只读。
- `--commit` 写入前必须复用 dry-run 全部检查。

## 写入前检查

`--commit` 写入前必须完成：

1. 读取候选 task。
2. 候选 task 必须是单个 JSON object。
3. 通过 `tasks/task.schema.json`。
4. `task.id` 在目标 tasks ledger 中不得重复。
5. candidate task 内容通过 secret scan。
6. candidate task 内容通过 public scan。
7. 目标 tasks file 通过 path guard。
8. 在临时 task ledger 中模拟 append。
9. 模拟 append 后 `task check-ledger` 必须通过。
10. 写入前记录 tasks file 原始 byte size。
11. 写入前确认现有 tasks file 若非空必须以换行结尾。

所有失败都必须在真实写入前返回，不得创建或修改 ledger。

## 关于无对应 event

`runtime task create --dry-run` 当前允许新 task 暂时没有对应 event，只要求新增 task 不破坏现有 ledger consistency。

第一版 commit 建议延续该语义：

- `runtime task create --commit` 只写 task snapshot ledger。
- 不自动追加 `created` event。
- 如需补事件，应由后续显式执行 `runtime event append --commit`。

这样可以保持唯一写入目标清晰，避免一个命令同时写 task ledger 和 event ledger。

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

写入前应确保现有文件末尾有换行；如果没有，第一版应直接 blocked，不自动修复，避免隐式修改历史内容。

## 写入后检查

写入后必须立即运行等价检查：

```bash
python -m agent_runtime.cli task validate --record-file <tasks-file> --schema task
python -m agent_runtime.cli task check-ledger --tasks-file <tasks-file> --events-file <events-file>
```

只有写后检查通过，才返回 `PASS`。

## 回滚策略

写入前记录：

- 目标 tasks file 的 byte size。
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
Source: candidate-task.json
task_id=task-...
status=planned
title_present=True
assignee_present=True
tag_count=2
artifact_count=1
evidence_count=1
would_create=True
ledger_check=pass
committed=True
post_validate=pass
post_ledger_check=pass
Next: Task appended. Consider appending a created event before further runtime planning.
```

JSON 输出也只包含：

- `status`
- `source`
- `task_id`
- `task_status`
- `title_present`
- `assignee_present`
- `tag_count`
- `artifact_count`
- `evidence_count`
- `would_create`
- `ledger_check`
- `committed`
- `post_validate`
- `post_ledger_check`
- `rolled_back`
- `rollback_error`
- `findings`
- `next_action`

不得输出完整：

- `title`
- `summary`
- `current_step`
- `blocked_message`
- `failure_reason`
- evidence description
- artifacts payload values if considered sensitive
- secret match

## 建议实现文件

可在现有模块上扩展：

```text
agent_runtime/runtime_task_create.py
agent_runtime/cli.py
```

建议新增结果模型字段：

```text
committed: bool
post_validate: str | None
post_ledger_check: str | None
rolled_back: bool
rollback_error: str | None
```

建议测试文件：

```text
tests/test_runtime_task_create_commit.py
```

## 最小测试清单

必须覆盖：

- commit pass：追加一行，写后 validate/check-ledger 通过。
- `--dry-run` 仍不写文件。
- `--dry-run` 与 `--commit` 互斥。
- 二者都不提供时报错。
- schema invalid 不写文件。
- duplicate task id 不写文件。
- secret/public scan blocked 不写文件且不回显匹配值。
- tasks file 不在项目内 blocked。
- tasks file 后缀非 `.jsonl` blocked。
- sample ledger blocked。
- tasks file 无末尾换行 blocked。
- post-check 失败时回滚。
- rollback 失败时返回 error。
- JSON 输出脱敏。
- commit 不写 events ledger。

## 完成条件

下一阶段完成前必须满足：

- `runtime task create --commit` 只追加单行。
- `runtime task create --dry-run` 保持完全只读。
- 不写 event ledger。
- 不自动创建 event。
- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不读取 `.env` / credential。
- 失败不留下半写入 ledger。
- 输出保持脱敏。
- `python -m pytest` 通过。
- `python -m agent_runtime.cli doctor` 通过。
- `python tools/public_scan.py` 通过。
- `git diff --check` 通过。

建议 tag：

```text
v0.10.0-runtime-task-create-commit
```
