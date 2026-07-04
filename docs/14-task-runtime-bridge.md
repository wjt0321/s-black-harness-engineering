# 14 — Task Runtime Bridge：把 Adapter Gate 衔接到 Task Ledger

## 这份文档解决什么问题

Adapter execution envelope 已经能描述一次 adapter 请求、授权和响应的完整边界。下一步需要回答：当 Runtime 把 envelope 与某个 task 关联起来时，应当如何判断“这个 task 现在能不能继续推进”，以及如果继续推进，应当向 task ledger 写入什么样的 event draft。

Task Runtime Bridge 就是这一层只读聚合器：它同时读取 task snapshot、task event stream 和 adapter execution envelope，按 `task_id` + `request_id` 做一致性检查，给出 `can_proceed` 判断，并输出建议的 task event draft（只打印摘要，不落盘）。

## 设计目标

- 把 task 状态、adapter gate 状态、approval/response 状态聚合成一个单一判断。
- 在需要推进时，给出符合 `tasks/event.schema.json` 的事件草案（包括 `event_type`、`from_status`、`to_status`、`message`、`metadata`）。
- 保持只读：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger。
- 不回显完整 artifact/input payload/evidence/raw_ref 值。

## 非目标

- 不真正执行 adapter。
- 不真正写入 `tasks/events.jsonl` 或 `tasks/tasks.jsonl`。
- 不把 raw adapter output 直接写进 task ledger。
- 不替代 orchestrator 对任务完成语义做最终判断。

## 核心概念

| 概念 | 说明 |
|:---|:---|
| `task snapshot` | `tasks/tasks.jsonl` 中某一行，包含 `id`、`status`、`assignee` 等 |
| `task event stream` | `tasks/events.jsonl` 中同一 `task_id` 的事件序列 |
| `adapter envelope` | `adapters/*.json` 中的 execution envelope，包含 `adapter_request`、`approval_record`、`adapter_response`、`execution_event` |
| `runtime gate` | 对“task + request”这一对实体做的聚合检查 |
| `event draft` | 根据 gate 结果生成的建议 task event，只输出摘要 |

## 数据流

```text
CLI: runtime gate check --task-id <id> --request-id <rid> --envelope <file>
  -> 读取 task snapshot（tasks/tasks.jsonl）
  -> 读取 task event stream（tasks/events.jsonl）
  -> 读取 adapter envelope（adapters/*.json）
  -> 定位 adapter_request by request_id
  -> 运行 adapter gate check（approval + response）
  -> 聚合 task 状态与 gate 状态
  -> 输出 can_proceed / next_action / suggested event draft
```

## 聚合规则

Runtime gate 的状态由以下因素共同决定：

1. **Task 必须存在**。如果 `task_id` 在 task ledger 中找不到，返回 `error`。
2. **Request 必须存在**。如果 `request_id` 在 envelope 中找不到，返回 `needs_input`。
3. **Envelope 必须合法**。如果 envelope schema/consistency 校验失败，返回 `validation_failed`。
4. **Task 状态必须允许继续**。如果 task 已经是 `finished` 或 `failed`，通常不应再推进；返回 `blocked`。
5. **Adapter gate 结果**：复用 `adapter_gate.check_adapter_gate` 的 `can_proceed`。

`can_proceed` 为 `true` 的充要条件：

- task 状态为 `planned`、`running` 或 `blocked`（允许从阻塞恢复）。
- adapter gate 最终状态为 `pass`。

## Task Event Draft 生成规则

Runtime gate 只输出 event draft 摘要，不会写盘。草案字段如下：

| 场景 | event_type | from_status | to_status | message 摘要 | metadata 摘要 |
|:---|:---|:---|:---|:---|:---|
| task 不存在 | — | — | — | 提示 task 未找到 | — |
| request 不存在 | — | — | — | 提示 request 未找到 | — |
| envelope 非法 | — | — | — | 提示 envelope 校验失败 | — |
| gate pass | `status_changed` / `evidence_added` | 当前 task 状态 | 维持或恢复为 `running` | Adapter request 可通过 gate，可继续执行 | `request_id`、`adapter_id`、`operation` |
| approval pending | `blocked` | 当前 task 状态 | `blocked` | 因等待用户授权而阻塞 | `request_id`、`approval_id`、`blocked_reason: need_user_approval` |
| approval denied/expired | `blocked` | 当前 task 状态 | `blocked` | 授权被拒绝或已过期 | `request_id`、`approval_id`、`blocked_reason: policy_blocked` |
| response missing / needs_input | `blocked` | 当前 task 状态 | `blocked` | 缺少 adapter response 或输入 | `request_id`、`blocked_reason: need_user_input` |
| response blocked/failed/skipped | `blocked` / `failed` | 当前 task 状态 | `blocked` / `failed` | adapter response 被阻断或失败 | `request_id`、`response_id`、`blocked_reason: tool_failed` |
| task 已是终态 | `blocked` | — | — | task 已结束，不应继续推进 | `task_status` |

metadata 中只保留 id、adapter/operation 名称、阻塞原因等安全字段，不包含 `input`、`evidence`、`raw_ref` 完整值。

## 输出格式

### 人类可读格式

```text
BLOCKED
task_id=task-20260703-001 task_status=finished request_id=req-20260703-002
gate: stage=response approval_status=pass response_status=pass can_proceed=true
Suggested event draft:
- event_type: status_changed
  from_status: finished
  to_status: finished
  message: Task is already in a terminal state (finished); do not proceed.
  metadata: {request_id=req-20260703-002, adapter_id=shell-local, operation=read_file}
Next: Task is already in a terminal state (finished); do not proceed.
```

### JSON 格式（`--json`）

```json
{
  "status": "pass",
  "task_id": "task-20260703-001",
  "task_status": "finished",
  "request_id": "req-20260703-001",
  "gate": {
    "stage": "response",
    "approval_status": "pass",
    "response_status": "succeeded",
    "can_proceed": false
  },
  "suggested_event_draft": {
    "event_type": "blocked",
    "from_status": "finished",
    "to_status": "finished",
    "message": "Task is already in a terminal state; do not proceed.",
    "metadata": {
      "task_status": "finished",
      "request_id": "req-20260703-001"
    }
  },
  "next_action": "Task is already in a terminal state; do not proceed."
}
```

## CLI 用法

```bash
# 默认读取项目根目录下的 tasks/tasks.jsonl、tasks/events.jsonl 和指定 envelope
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --envelope adapters/execution-envelope.examples.json

# 显式指定 ledger 文件（仍只读）
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --envelope adapters/execution-envelope.examples.json \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl

# JSON 输出（仍脱敏）
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

## 与现有模块的关系

| 模块 | 关系 |
|:---|:---|
| `agent_runtime/tasks.py` | 读取 task snapshot 与 event stream |
| `agent_runtime/adapter_gate.py` | 复用 adapter gate 检查 |
| `agent_runtime/adapter_validation.py` | 复用 envelope schema + consistency 校验 |
| `tasks/event.schema.json` | event draft 字段需符合该 schema |
| `adapters/execution-envelope.schema.json` | envelope 结构约束 |

## 安全边界

- 命令只读打开 ledger 和 envelope，不写入、不追加、不修改。
- 不执行外部命令、不访问网络、不发送消息、不删除文件。
- 不读取 `.env`、`.env.local`、`.envrc`、`.secret`、`.key`、`.pem`、`.p12`、`.pfx` 等密钥文件。
- 人类/JSON 输出中不包含完整 `input`、`evidence`、`raw_ref`、`decision_ref` 值。
- 公开仓库样例中不出现本机真实路径、内部称谓、真实 agent id、运行协议文本或密钥样例。

## 下一阶段候选

下一步可以在保持只读的前提下扩展：

- `runtime plan`：根据 task 当前状态生成下一步 adapter request draft。
- `runtime check-ledger`：检查 task ledger 中 event draft 与实际 envelope 状态是否一致。
- 真正的 event 写入接口（需要显式授权机制后才实现）。
