# 34 — Runtime Task Create Commit 阶段收口说明

## 阶段定位

本阶段实现 `runtime task create --commit`，把上一阶段的 task create dry-run 门禁扩展为受控写入。

该命令只允许把一个候选 task snapshot 追加到 task ledger JSONL 末尾，不自动写 event ledger，不执行 adapter，不访问网络，不发送消息。

## 新增能力

### `runtime task create --commit`

从文件提交创建：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit
```

从 stdin 提交创建：

```bash
type candidate-task.json | python -m agent_runtime.cli runtime task create \
  --stdin \
  --commit
```

指定 ledger：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --json
```

## 写入边界

`--commit` 的唯一写入动作是：

```text
append exactly one JSON object as the last line of a task ledger JSONL file
```

它不会：

- 写 event ledger。
- 创建对应 event。
- 执行 adapter。
- 访问网络。
- 发送消息。
- 读取 `.env`、credential 或 keyring。
- 覆盖、删除、重排或重写历史 task。

## 门禁与回滚

写入前检查：

- 候选 task JSON 解析。
- 候选 task 必须是单个 JSON object。
- `tasks/task.schema.json` schema validation。
- `task.id` 在目标 task ledger 中不得重复。
- candidate task 内容 secret scan。
- candidate task 内容 public scan。
- 目标 task ledger 必须是项目内安全 `.jsonl` 文件，且不能是 sample / git / credential 路径。
- 在临时 task ledger 中模拟 append 后运行 ledger consistency。
- 现有非空 task ledger 必须以换行结尾。
- 目标父目录必须已存在。

写入后检查：

- `task validate --schema task` 等价检查。
- `task check-ledger` 等价检查。

如果写后检查失败，命令会按写入前 byte size 截断回滚；如果本命令创建了新文件，则删除该新文件。

## 输出摘要

输出只包含安全摘要：

```text
PASS
Source: candidate-task.json
task_id=task-20260706-001
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

不会回显完整 title、summary、current_step、blocked_message、failure_reason、evidence description、artifact payload 或 secret match。

## 实现文件

- `agent_runtime/runtime_task_create.py` - task create dry-run 与 commit 门禁逻辑。
- `agent_runtime/cli.py` - `runtime task create` 模式调度与安全摘要渲染。
- `tests/test_runtime_task_create_commit.py` - commit 聚焦测试。
- `tests/test_runtime_task_create_dry_run.py` - dry-run 兼容性测试。

## 验证结果

本阶段收口前验证：

```text
python -m pytest tests/test_runtime_task_create_dry_run.py tests/test_runtime_task_create_commit.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

## 后续建议

下一步可补一条 smoke/report loop 文档与测试：在临时项目副本中执行 task create dry-run -> commit -> event append dry-run/commit -> runtime report，验证 task 与 event 的完整受控写入闭环。
