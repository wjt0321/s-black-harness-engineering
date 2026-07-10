# 29 - Runtime Event Append Commit 阶段收口说明

## 阶段定位

本阶段冻结最小 Controlled Write POC 的第四步：`runtime event append --commit`。

这是本项目第一次允许 Runtime 写入 task event ledger，但写入边界被严格收窄：只允许把一个已通过全部预检的 candidate event 作为最后一行追加到 event ledger JSONL。它仍然不执行 adapter、不访问网络、不发送消息、不写 adapter envelope、不修改 task snapshot ledger。

## 新增能力

### `runtime event append --commit`

从文件追加：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit
```

从 stdin 追加：

```bash
type candidate-event.json | python -m agent_runtime.cli runtime event append \
  --stdin \
  --commit
```

带 ledger 与 envelope audit：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

`--dry-run` 仍保留只读语义；`--dry-run` 与 `--commit` 互斥，且必须显式提供其中一个。

## 写入前检查

`--commit` 写入前复用 dry-run 全部检查：

- 候选 event JSON 解析，且必须是单个 JSON object。
- `tasks/event.schema.json` schema validation。
- `task_id` 必须存在于 task ledger。
- `event_id` 在目标 event ledger 中不得重复。
- candidate event 内容通过 secret scan。
- candidate event 内容通过 public scan。
- 模拟 append 后运行 ledger consistency。
- 如提供 `--envelope`，模拟 append 后运行 runtime ledger audit。

commit 额外目标路径限制：

- events file 必须位于项目根目录内。
- 后缀必须为 `.jsonl`。
- 不允许写 credential / `.git` internals。
- 不允许写 sample ledgers。
- 父目录必须已存在；本阶段不隐式创建目录。
- 非空 events file 必须已有末尾换行；本阶段不自动修复历史 ledger。

## 写入行为

成功写入时：

- 只追加一行。
- 不修改已有行。
- 不删除已有行。
- 不重排已有行。
- 不格式化整个 ledger。
- 写入格式为 `json.dumps(candidate, ensure_ascii=False) + "\n"`。

## 写入后检查与回滚

写入后立即重新检查：

- `task validate --schema event` 等价检查。
- `task check-ledger` 等价检查。
- 如提供 `--envelope`，再运行 `runtime check-ledger` 等价检查。

如果 post-check 失败：

- 尝试截断回写入前 byte size。
- 如果目标文件是本命令创建的新文件，则删除该新文件。
- 回滚成功后返回失败状态并说明已回滚。
- 回滚失败则返回 error，提示人工恢复。

## 输出摘要

输出只包含安全摘要，例如：

```text
PASS
Source: candidate-event.json
event_id=evt-20260705-003
task_id=task-20260705-001
event_type=progress
from_status=running
to_status=running
would_append=True
ledger_check=pass
committed=True
post_validate=pass
post_ledger_check=pass
artifact_count=0
Next: Event appended. Review runtime report before further actions.
```

JSON 输出同样只暴露安全字段。不会回显完整 message、metadata values、artifacts payload、evidence description、target、input、raw_ref、decision_ref 或 secret match。

## 实现文件

- `agent_runtime/runtime_event_append.py` - 扩展 `append_event(..., commit=False)` 与 commit 路径。
- `agent_runtime/cli.py` - `runtime event append` 模式校验与安全摘要渲染。
- `tests/test_runtime_event_append_commit.py` - commit 模式测试覆盖。
- `tests/test_runtime_event_append_dry_run.py` - 模式错误预期更新。
- `docs/28-runtime-event-append-commit.md` - commit 模式设计与用法。

## 验证结果

本阶段功能提交后验证：

```text
python -m pytest -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task -> PASS
python -m agent_runtime.cli task validate --record-file tasks/events.jsonl --schema event -> PASS
python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl -> PASS
```

推送前额外执行：

```text
key pattern scan -> OK key scan
```

## 当前限制

- 不支持批量 import。
- 不支持修改历史 event。
- 不支持自动修复 ledger。
- 不支持写 sample ledger。
- 不隐式创建 event ledger 父目录。
- 不执行 adapter。
- 不访问网络、不发送消息。
- 不写 adapter envelope。
- 不写 task snapshot ledger。

## 后续建议

下一阶段建议先保持低风险，不进入 adapter execution。可考虑：

- `runtime report` 对 append 后状态的专门 smoke 文档。
- task 创建 dry-run。
- 批量 event import dry-run。
- ledger compaction dry-run。
