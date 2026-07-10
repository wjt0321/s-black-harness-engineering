# runtime event append --dry-run

## 目标

`runtime event append --dry-run` 在把单个候选 event 真正追加到 `tasks/events.jsonl` 之前，跑通所有入门禁：

- 读取候选 event（`--file` 项目内安全 `.json` 文件或 `--stdin`）。
- 用 `tasks/event.schema.json` 做 schema 校验。
- 确认 `task_id` 已存在于 task ledger。
- 在内存中模拟把 event 追加到 event ledger，跑 ledger consistency 检查。
- 如提供 `--envelope`，模拟追加后跑 runtime ledger audit 预期检查。
- 对候选 event 内容做 secret / public scan，命中则 blocked 且不回显完整匹配。
- 输出脱敏摘要。

## 边界

- **只读**：不写 `tasks/events.jsonl`、不写 task ledger、不写 envelope。
- 不执行 adapter、不访问网络、不发送消息、不删除文件、不读取 `.env`/credential。
- `--dry-run` 必须显式提供；未提供时报错。
- 输出不回显完整 target / input payload / evidence description / raw_ref / decision_ref / secret match。

## CLI

```bash
python -m agent_runtime.cli runtime event append --file candidate-event.json --dry-run
python -m agent_runtime.cli runtime event append --stdin --dry-run
python -m agent_runtime.cli runtime event append --file candidate-event.json --dry-run \
    --tasks-file tasks/tasks.jsonl \
    --events-file tasks/events.jsonl \
    --envelope adapters/execution-envelope.examples.json \
    --json
```

参数说明：

| 参数 | 说明 |
|---|---|
| `--file` | 候选 event JSON 文件路径（与 `--stdin` 互斥） |
| `--stdin` | 从 stdin 读取候选 event JSON（与 `--file` 互斥） |
| `--dry-run` | 必须显式提供，只读模拟 |
| `--tasks-file` | task ledger 路径，默认 `tasks/tasks.jsonl` |
| `--events-file` | event ledger 路径，默认 `tasks/events.jsonl` |
| `--envelope` | 可选 adapter execution envelope，用于 runtime ledger audit |
| `--json` | 输出结构化但脱敏的 JSON |

## 输出示例

Human-readable：

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

JSON：

```json
{
  "status": "pass",
  "next_action": "Dry-run passed. Use runtime event append --commit (not yet implemented) to persist.",
  "source": "candidate.json",
  "event_id": "evt-20260705-003",
  "task_id": "task-20260705-001",
  "event_type": "progress",
  "from_status": "running",
  "to_status": "running",
  "would_append": false,
  "ledger_check": "pass",
  "artifact_count": 0
}
```

输出只包含安全摘要，不回显完整 message、metadata values、artifact payload、evidence description 或 secret match。

## 退出码

| 码 | 含义 |
|:---:|:---|
| 0 | dry-run 通过 |
| 1 | 错误（缺少 task、路径错误、IO 等） |
| 2 | blocked（secret/public scan 命中） |
| 5 | validation_failed（schema 或 ledger consistency 失败） |

## 实现要点

- 新增模块 `agent_runtime/runtime_event_append.py`。
- 用系统临时文件模拟追加：把现有 events 复制到位于项目根目录内的临时 JSONL，追加候选 event，然后调用现有 `check_ledger_consistency` 与 `check_runtime_ledger`。
- secret scan 复用 `policy.check_text`；public scan 复用 `tools/public_scan.py` 的规则。
- 临时文件在检查完成后立即删除，不留在项目目录中。

## 下一步

- 如项目进入持久化写入阶段，可实现 `runtime event append --commit`，但需保持相同的门禁顺序与脱敏输出。
