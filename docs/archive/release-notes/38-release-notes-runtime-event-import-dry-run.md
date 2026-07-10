# 38 — Runtime Event Import Dry-run 阶段收口说明

## 阶段定位

本阶段实现 `runtime event import --dry-run`，为批量 event 导入提供只读预检能力。

该命令只检查候选 JSONL 文件中的 event batch 是否满足所有写入前门禁，不写入 event ledger、不写入 task ledger、不执行 adapter、不访问网络、不发送消息。

## 新增能力

### `runtime event import --dry-run`

从文件批量预检：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

指定 ledger：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --json
```

## 批量语义

- 输入为 JSONL，每行一个 event object；空行会被忽略并统计。
- 采用 all-or-nothing preflight：任意一行不合法，整批返回失败。
- 输入顺序即模拟导入顺序；不自动按 timestamp 排序。
- 不允许部分成功，也不生成可被误解为部分成功的 commit plan。

## 检查内容

逐行检查：

- 是否为合法 JSON。
- 是否为 JSON object。
- 是否符合 `tasks/event.schema.json`。
- 是否通过 secret scan 与 public scan。

批量检查：

- candidate 内部是否重复 `event_id`。
- candidate `event_id` 是否已存在于现有 event ledger。
- candidate 引用的 `task_id` 是否存在于 task ledger。
- 在临时文件（`existing events + candidate events in input order`）中模拟追加后，运行 `task validate --schema event` 与 `task check-ledger` 等价检查。
- 检测非法状态迁移（如终态回退、状态不连续、首事件非 `created` 等）。

## 输出摘要

dry-run 通过时的人类输出示例：

```text
PASS
Source: candidate-events.jsonl
event_count=3
blank_line_count=0
task_count=2
event_type_counts=created:1,status_changed:2
would_import=True
ledger_check=pass
Next: Dry-run passed. Review the event batch before any future commit command.
```

失败时输出保持相同结构，并附加 `findings`，每条 finding 包含行号、规则 id 与简短说明，不回显完整 candidate JSON 行。

不会回显完整 `message`、metadata values、artifacts payload、evidence description、`target` / `input`、`raw_ref` / `decision_ref` 或 secret match。

## 实现文件

- `agent_runtime/runtime_event_import.py` - batch import dry-run 门禁逻辑。
- `agent_runtime/cli.py` - `runtime event import` 子命令调度与安全摘要渲染。
- `tests/test_runtime_event_import_dry_run.py` - dry-run 聚焦测试。

## 安全边界

- 不实现 `--commit`；不新增真实写权限。
- 不修改真实 `tasks/events.jsonl` 或 `tasks/tasks.jsonl`。
- 不访问网络，不读取 `.env`/credential，不删除文件。
- 临时文件创建于项目根目录内，检查完成后立即删除。
- 输入文件必须位于项目根目录内、后缀为 `.jsonl`、不能指向 `.git` / credential / secret 路径。

## 验证结果

本阶段收口前验证：

```text
python -m pytest tests/test_runtime_event_import_dry_run.py -q -> passed
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

## 后续建议

下一步如需 `runtime event import --commit`，必须另写设计文档，定义批量写入的事务边界、回滚策略、是否允许创建新 ledger、是否要求末尾换行、dry-run plan hash 校验等，不能直接从 dry-run 推导。
