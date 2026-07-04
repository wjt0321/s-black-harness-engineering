# 15 — Runtime Ledger Audit：跨系统账本一致性检查

## 这份文档解决什么问题

`runtime gate check` 已经能判断单个 `task_id` + `request_id` 对当前能否继续推进。但一个 envelope 里往往包含多个 adapter request 和 execution event，而 task ledger 中也可能已经记录了若干相关事件。Runtime Ledger Audit 就是用来在**只读**前提下，批量检查 task ledger、event ledger 与 adapter execution envelope 三者之间是否一致：引用的 task 是否存在、event 引用的 request 是否已知、task 已结束时 envelope 是否还在要求继续，等等。

## 设计目标

- 保持只读：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger。
- 不回显完整 artifact/input payload/evidence/raw_ref/decision_ref/target 值。
- 复用现有 `task check-ledger` 和 `adapter validate` 的安全读取与基础校验逻辑。
- 输出 compact 摘要，支持 `--json` 结构化输出。

## 非目标

- 不真正执行 adapter。
- 不真正写入 `tasks/events.jsonl` 或 `tasks/tasks.jsonl`。
- 不做单请求 gate 决策（那是 `runtime gate check` 的职责）。
- 不替代 orchestrator 对任务完成语义做最终判断。

## 核心概念

| 概念 | 说明 |
|:---|:---|
| `task ledger` | `tasks/tasks.jsonl` 中 task snapshot 集合 |
| `event ledger` | `tasks/events.jsonl` 中 task event 集合 |
| `adapter envelope` | `adapters/*.json` 中的 execution envelope，包含 `adapter_request`、`approval_record`、`adapter_response`、`execution_event` |
| `runtime ledger audit` | 对 ledger 与 envelope 之间引用关系与状态语义的批量检查 |

## 数据流

```text
CLI: runtime check-ledger --tasks-file <file> --events-file <file> --envelope <file>
  -> 运行 task/event ledger 基础一致性检查（复用 task check-ledger）
  -> 安全加载 adapter execution envelope（复用 adapter validate 的加载逻辑）
  -> 解析 adapter_request 与 execution_event
  -> 检查 task_id 与 request_id 引用
  -> 检查 task ledger 中是否存在 request_id 相关线索
  -> 检查 task 已 terminal 时 envelope 是否仍要求继续
  -> 输出 status / counts / findings / next_action
```

## 检查规则

| rule_id | severity | 说明 |
|---|---|---|
| `ledger-consistency-failed` | error | tasks/events 基础一致性失败，或 ledger 文件无法读取 |
| `envelope-load-failed` / `invalid-json` / `unsafe-envelope-file` 等 | error | envelope 无法安全加载或 JSON 无效（来自 `_load_envelope`） |
| `request-task-id-unknown` | error | `adapter_request.task_id` 不在 task ledger 中 |
| `event-task-id-unknown` | error | `execution_event.task_id` 不在 task ledger 中 |
| `event-request-id-unknown` | error | `execution_event.request_id` 未引用已知 `adapter_request` |
| `request-id-no-event-metadata` | warn | task ledger 的 event metadata/artifacts 中未找到该 request_id 线索 |
| `task-terminal-but-request-pending` | warn | task 已处于 `finished` / `failed` 终态，但 envelope 中的 request 仍要求继续 |

## 输出格式

### 人类可读格式

```text
PASS
counts: tasks=2, events=8, requests=2, execution_events=2
Next: Runtime ledger audit passed.
```

当存在 warning 时：

```text
WARN
counts: tasks=2, events=8, requests=2, execution_events=2
- request-id-no-event-metadata: No task ledger event metadata/artifact references request_id req-20260703-001
- task-terminal-but-request-pending: task_id task-20260703-001 is terminal (finished) but adapter_request req-20260703-001 still expects progress
Next: Review warnings; ledger audit passed with warnings.
```

### JSON 格式（`--json`）

```json
{
  "status": "warn",
  "counts": {
    "tasks": 2,
    "events": 8,
    "requests": 2,
    "execution_events": 2
  },
  "findings": [
    {
      "rule_id": "request-id-no-event-metadata",
      "severity": "warn",
      "action": "warn",
      "message": "No task ledger event metadata/artifact references request_id req-20260703-001"
    },
    {
      "rule_id": "task-terminal-but-request-pending",
      "severity": "warn",
      "action": "warn",
      "message": "task_id task-20260703-001 is terminal (finished) but adapter_request req-20260703-001 still expects progress"
    }
  ],
  "next_action": "Review warnings; ledger audit passed with warnings."
}
```

JSON 输出经过脱敏：不包含 `input`、`evidence`、`raw_ref`、`decision_ref`、`target` 等完整值。

## CLI 用法

```bash
# 检查 task ledger、event ledger 与 envelope 的一致性
python -m agent_runtime.cli runtime check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json

# JSON 输出
python -m agent_runtime.cli runtime check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

## 与现有模块的关系

| 模块 | 关系 |
|:---|:---|
| `agent_runtime/ledger_consistency.py` | 复用 `check_ledger_consistency()` 做 tasks/events 基础一致性 |
| `agent_runtime/adapter_validation.py` | 复用 `_load_envelope()` 安全加载 envelope |
| `agent_runtime/tasks.py` | 复用 `load_tasks()` / `load_events()` 读取 ledger |
| `agent_runtime/result.py` | 复用 `Finding` 与状态码映射 |
| `agent_runtime/cli.py` | 新增 `runtime check-ledger` 子命令与输出渲染 |

## 安全边界

- 命令只读打开 ledger 和 envelope，不写入、不追加、不修改。
- 不执行外部命令、不访问网络、不发送消息、不删除文件。
- 不读取 `.env`、`.env.local`、`.envrc`、`.secret`、`.key`、`.pem`、`.p12`、`.pfx` 等密钥文件。
- 人类/JSON 输出中不包含完整 `input`、`evidence`、`raw_ref`、`decision_ref` 值。
- 只接受项目根目录内的安全 `.jsonl` 与 `.json` 文件。

## 下一阶段候选

- `runtime plan`：根据 task 当前状态生成下一步 adapter request draft。
- 真正的 event 写入接口（需要显式授权机制后才实现）。
