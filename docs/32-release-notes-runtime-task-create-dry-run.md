# 32 — Runtime Task Create Dry-run 阶段收口说明

## 阶段定位

本阶段冻结 `runtime task create --dry-run`。

它用于在未来真正向 task snapshot ledger 写入新 task 之前，先跑通 task 创建门禁：读取候选 task、校验 schema、确认 task id 不重复、扫描敏感/公开风险内容、模拟追加后检查 ledger consistency，并输出脱敏摘要。

本阶段仍保持只读，不写真实 task ledger，不写 event ledger，不实现 commit。

## 新增能力

### `runtime task create --dry-run`

从文件读取候选 task：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run
```

从 stdin 读取候选 task：

```bash
type candidate-task.json | python -m agent_runtime.cli runtime task create \
  --stdin \
  --dry-run
```

指定 ledger 并输出 JSON：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --json
```

## 检查内容

`runtime task create --dry-run` 会执行：

- 候选 task JSON 解析。
- 候选 task 必须是单个 JSON object。
- `tasks/task.schema.json` schema validation。
- `task.id` 在目标 task ledger 中不得重复。
- 目标 task ledger 必须是项目内安全 `.jsonl` 文件。
- candidate task 内容 secret scan。
- candidate task 内容 public scan。
- 临时 task ledger 中模拟 append 后运行 ledger consistency。

如果 events ledger 不存在，本阶段使用空临时 events 文件进行一致性检查；新 task 暂时无对应 event 不会单独阻断 dry-run。

## 输出摘要

输出只包含安全摘要，例如：

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
would_create=False
ledger_check=pass
Next: Dry-run passed. Task create --commit is not yet implemented.
```

JSON 输出同样只暴露安全字段。不会回显完整 title、summary、evidence description、secret match 或其他自由文本 payload。

## 实现文件

- `agent_runtime/runtime_task_create.py` - task create dry-run 门禁逻辑。
- `agent_runtime/cli.py` - 注册 `runtime task create` 子命令与安全摘要渲染。
- `tests/test_runtime_task_create_dry_run.py` - 测试覆盖。
- `docs/31-runtime-task-create-dry-run.md` - 命令设计与用法。

## 验证结果

本阶段收口前验证：

```text
python -m pytest tests/test_runtime_task_create_dry_run.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

## 当前限制

- 仅支持 `--dry-run`。
- `--commit` 未实现；显式传入会返回 `commit-not-implemented`。
- 不写 `tasks/tasks.jsonl`。
- 不写 `tasks/events.jsonl`。
- 不执行 adapter。
- 不访问网络、不发送消息。
- 不读取 `.env` / credential。
- 不要求新 task 已有对应 event。

## 后续建议

下一阶段如继续推进，建议仍先做只读/低风险能力：

- `runtime event import --dry-run`：批量 event 导入预检。
- `ledger compaction --dry-run`：只读分析 ledger 压缩候选。
- 或为 `runtime task create --commit` 写预备设计文档，但不要直接实现 commit。
