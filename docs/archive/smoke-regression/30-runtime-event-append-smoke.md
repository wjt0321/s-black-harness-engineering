# 30 — Runtime Event Append Smoke / Report Loop

## 目标

本文说明如何在**临时项目副本或临时目录**中，对 `runtime event append` 执行一条端到端的 smoke loop：

```text
candidate event dry-run -> commit -> task validate/check-ledger -> runtime check-ledger/report
```

重点：**不要在仓库样例 ledger（`tasks/tasks.jsonl`、`tasks/events.jsonl`）上直接 commit**。所有写入操作应在可丢弃的临时目录中进行。

## 边界

- 不新增任何写权限。
- 不执行 adapter、不访问网络、不发送消息。
- 不读取 `.env`/credential。
- 不修改真实 `tasks/events.jsonl` 示例 ledger。
- 不修改 `AGENTS.md`。

## 最小临时项目结构

在 `/tmp/smoke-project`（或 Windows 临时目录）下创建。Windows PowerShell 5 的 `Set-Content -Encoding UTF8` 会写入 BOM，可能导致 JSON parser 报 `Unexpected UTF-8 BOM`；Windows 下建议用 Python 或 `.NET UTF8Encoding(false)` 写临时 JSON/JSONL。

```text
/tmp/smoke-project/
├── policies/                        # 复制仓库 policies/*.sample.policy.json
├── adapters/
│   └── execution-envelope.schema.json
├── tasks/
│   ├── task.schema.json
│   └── event.schema.json
├── tasks.jsonl                      # 一条 task 记录
├── events.jsonl                     # 若干条 event 记录
├── envelope.json                    # 可选，用于 runtime check-ledger/report
└── candidate.json                   # 待追加的单个 event 对象
```

复制命令示例：

```bash
SMOKE=/tmp/smoke-project
rm -rf "$SMOKE"
mkdir -p "$SMOKE"/policies "$SMOKE"/adapters "$SMOKE"/tasks

# schema / policy
cp policies/*.sample.policy.json "$SMOKE"/policies/
cp adapters/execution-envelope.schema.json "$SMOKE"/adapters/
cp tasks/task.schema.json "$SMOKE"/tasks/
cp tasks/event.schema.json "$SMOKE"/tasks/

# ledger
cat > "$SMOKE"/tasks.jsonl <<'JSONL'
{"id":"task-20260706-001","title":"smoke task","status":"running","created_at":"2026-07-06T10:00:00+08:00","updated_at":"2026-07-06T10:00:00+08:00","created_by":"test","source":"cli","assignee":"cli"}
JSONL

cat > "$SMOKE"/events.jsonl <<'JSONL'
{"event_id":"evt-20260706-001","task_id":"task-20260706-001","timestamp":"2026-07-06T10:00:00+08:00","actor":"cli","event_type":"created","from_status":null,"to_status":"planned","message":"created","artifacts":[],"metadata":{}}
{"event_id":"evt-20260706-002","task_id":"task-20260706-001","timestamp":"2026-07-06T10:01:00+08:00","actor":"cli","event_type":"status_changed","from_status":"planned","to_status":"running","message":"started","artifacts":[],"metadata":{}}
JSONL

# candidate event
cat > "$SMOKE"/candidate.json <<'JSON'
{"event_id":"evt-20260706-003","task_id":"task-20260706-001","timestamp":"2026-07-06T10:02:00+08:00","actor":"cli","event_type":"progress","from_status":"running","to_status":"running","message":"making progress","artifacts":[],"metadata":{}}
JSON

# envelope（可选，用于 runtime check-ledger/report）
cat > "$SMOKE"/envelope.json <<'JSON'
{
  "version": 1,
  "description": "smoke envelope",
  "artifacts": [
    {
      "artifact_type": "adapter_request",
      "request_id": "req-20260706-001",
      "task_id": "task-20260706-001",
      "adapter_id": "github-cli",
      "operation": "git_status",
      "actor": "cli",
      "target": "origin/main",
      "input": {},
      "context": {"source": "cli", "policy_profile": "all", "risk_level": "local", "dry_run": true, "requires_approval": false},
      "preflight": {"status": "pass", "findings": []},
      "created_at": "2026-07-06T10:00:00+08:00"
    },
    {
      "artifact_type": "execution_event",
      "event_id": "exe-20260706-001",
      "task_id": "task-20260706-001",
      "request_id": "req-20260706-001",
      "timestamp": "2026-07-06T10:01:00+08:00",
      "actor": "cli",
      "event_type": "evidence_added",
      "message": "evidence attached",
      "metadata": {"response_id": "resp-20260706-001", "evidence_count": 1}
    }
  ]
}
JSON
```

## Smoke Loop 步骤

### 1. Dry-run：确认候选 event 可通过全部预检

```bash
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate.json \
  --dry-run \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl \
  --envelope envelope.json
```

期望输出包含 `PASS`、`would_append=False`、`committed=False`。此步骤**不写** `events.jsonl`。

### 2. Commit：追加一行到 events.jsonl

```bash
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate.json \
  --commit \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl \
  --envelope envelope.json
```

期望输出包含 `PASS`、`committed=True`、`post_validate=pass`、`post_ledger_check=pass`。

确认只追加一行：

```bash
wc -l "$SMOKE"/events.jsonl
# 应从 2 行变为 3 行
```

### 3. 写后校验

```bash
python -m agent_runtime.cli --root "$SMOKE" task validate \
  --record-file events.jsonl \
  --schema event

python -m agent_runtime.cli --root "$SMOKE" task check-ledger \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl

python -m agent_runtime.cli --root "$SMOKE" runtime check-ledger \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl \
  --envelope envelope.json
```

以上均应返回 `PASS` 或 `WARN`（envelope audit 的 warn 不影响通过）。

### 4. Runtime report：读取追加后状态

```bash
python -m agent_runtime.cli --root "$SMOKE" runtime report \
  --task-id task-20260706-001 \
  --request-id req-20260706-001 \
  --envelope envelope.json \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl
```

期望输出包含：

- `Task: task-20260706-001 (running)`
- `Events: 3 events, latest: progress`
- `Envelope:`、`Gate:`、`Ledger:`、`Blockers:` 等摘要
- `Next:` 建议

## 脱敏检查

在整个 loop 的输出中，不应出现：

- 完整 `message` 内容（如 `"making progress"`）。
- 完整 `target`（如 `origin/main`）。
- 完整 `input` payload。
- `evidence` description。
- `raw_ref`、`decision_ref` 值。
- secret match。

如果使用了 `--json`，可重定向到文件后搜索上述字符串：

```bash
python -m agent_runtime.cli --root "$SMOKE" runtime report \
  --task-id task-20260706-001 \
  --request-id req-20260706-001 \
  --envelope envelope.json \
  --tasks-file tasks.jsonl \
  --events-file events.jsonl \
  --json > report.json
grep -E "making progress|origin/main|decision_ref|raw_ref" report.json && echo "LEAK" || echo "OK"
```

## 清理

Smoke 结束后直接删除临时目录：

```bash
rm -rf "$SMOKE"
```

## 与仓库真实 ledger 的关系

仓库中的 `tasks/tasks.jsonl` 和 `tasks/events.jsonl` 是只读样例，用于：

- `doctor` 校验。
- `task validate`、`task check-ledger` 等只读命令的 smoke。
- `runtime report` 等只读报告的示例输入。

**任何 `runtime event append --commit` 命令都不应直接指向这两个文件。** 如需在仓库内保留 smoke 产生的 ledger，可显式指定 `--events-file smoke/events.jsonl` 等独立路径，并在 `.gitignore` 中排除。

## 相关文档

- `docs/26-runtime-event-append-dry-run.md`
- `docs/28-runtime-event-append-commit.md`
- `docs/19-runtime-report.md`
- `docs/15-runtime-ledger-audit.md`
