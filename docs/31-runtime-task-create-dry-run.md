# 31 — Runtime Task Create Dry-run

## 目标

`runtime task create --dry-run` 在把单个候选 task snapshot 真正写入 task ledger 之前，跑通所有入门禁：

- 读取候选 task（`--file` 项目内安全 `.json` 文件或 `--stdin`）。
- 用 `tasks/task.schema.json` 做 schema 校验。
- 确认 `task.id` 在目标 task ledger 中不重复。
- 对候选 task 内容做 secret / public scan，命中则 blocked 且不回显完整匹配。
- 在内存中模拟把 task 追加到 task ledger，配合现有 events ledger 跑 ledger consistency 检查。
- 输出脱敏摘要。

## 边界

- **只读**：不写 `tasks/tasks.jsonl`、不写 `tasks/events.jsonl`、不写 envelope。
- 不执行 adapter、不访问网络、不发送消息、不删除文件、不读取 `.env`/credential。
- `--dry-run` 必须显式提供；未提供时报错。
- `--commit` 未实现；显式传入会返回 `commit-not-implemented` 错误。
- 输出不回显完整 title / summary / evidence description / secret match / 自由文本 payload。

## CLI

```bash
python -m agent_runtime.cli runtime task create --file candidate-task.json --dry-run
python -m agent_runtime.cli runtime task create --stdin --dry-run
python -m agent_runtime.cli runtime task create --file candidate-task.json --dry-run \
    --tasks-file tasks/tasks.jsonl \
    --events-file tasks/events.jsonl \
    --json
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--file` | 候选 task JSON 文件路径（与 `--stdin` 互斥） |
| `--stdin` | 从 stdin 读取候选 task JSON（与 `--file` 互斥） |
| `--dry-run` | 必须显式提供，只读模拟 |
| `--tasks-file` | task ledger 路径，默认 `tasks/tasks.jsonl` |
| `--events-file` | event ledger 路径，默认 `tasks/events.jsonl` |
| `--json` | 输出结构化但脱敏的 JSON |

## 输出示例

Human-readable：

```text
PASS
Source: candidate.json
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

JSON：

```json
{
  "status": "pass",
  "next_action": "Dry-run passed. Task create --commit is not yet implemented.",
  "source": "candidate.json",
  "task_id": "task-20260706-001",
  "task_status": "planned",
  "title_present": true,
  "assignee_present": true,
  "tag_count": 2,
  "artifact_count": 1,
  "evidence_count": 1,
  "would_create": false,
  "ledger_check": "pass"
}
```

输出只包含安全摘要，不回显完整 title、summary、evidence description 或 secret match。

## 关于无对应 event 的说明

新创建的 task 在 event ledger 中通常还没有对应事件。`runtime task create --dry-run` 模拟追加后的 ledger consistency 检查时：

- 如果 events ledger 已存在，就使用现有 events ledger 检查新增 task 不会破坏一致性。
- 如果 events ledger 不存在，使用空临时 events 文件进行检查。
- 只要现有 ledger 未被破坏， dry-run 即可通过；并不要求新 task 必须已有事件。

## 退出码

| 码 | 含义 |
|:---:|:---|
| 0 | dry-run 通过 |
| 1 | 错误（路径错误、IO、未提供 `--dry-run`、未实现 `--commit` 等） |
| 2 | blocked（secret/public scan 命中） |
| 5 | validation_failed（schema、重复 task id 或 ledger consistency 失败） |

## 实现要点

- 新增模块 `agent_runtime/runtime_task_create.py`。
- 目标 task ledger 路径必须位于项目根目录内、以 `.jsonl` 结尾、不能指向 credential/git internals。
- 用系统临时文件模拟追加：把现有 tasks 复制到位于项目根目录内的临时 JSONL，追加候选 task，然后调用现有 `check_ledger_consistency`。
- secret scan 复用 `policy.check_text`；public scan 复用 `tools/public_scan.py` 的规则。
- 临时文件在检查完成后立即删除，不留在项目目录中。

## 测试

聚焦测试位于 `tests/test_runtime_task_create_dry_run.py`，覆盖：

- dry-run pass（含无现有 events ledger 的情况）。
- stdin 输入。
- schema invalid / candidate 非 object。
- 重复 task id。
- secret scan / public scan blocked 且不回显。
- task ledger 路径在项目根目录外 / 后缀不安全。
- dry-run 不写真实 task ledger。
- JSON 输出脱敏。
- 未提供 `--dry-run` / 传入 `--commit` 报错。

## 下一步

- 如项目进入持久化写入阶段，可实现 `runtime task create --commit`，但需保持相同的门禁顺序与脱敏输出。
