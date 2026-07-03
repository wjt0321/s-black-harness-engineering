# 12 — Adapter Execution Envelope 二期设计

## 这份文档解决什么问题

前面已经有 Adapter 注册表，但它只说明“有哪些适配器”和“它们大概能做什么”。下一步需要定义 Runtime 在准备调用适配器时，应该如何描述一次动作、如何记录授权、如何接收结果，以及如何把这些信息转换为任务账本事件。

本阶段仍然不接入真实外部系统，不执行 shell、不访问网络、不发送消息、不写真实 ledger。目标是先把 request / response / approval / event 的边界稳定下来。

## 设计目标

Adapter execution envelope 要回答四个问题：

- Runtime 准备让哪个 adapter 做什么？
- 执行前是否已经通过 policy preflight？
- 如果需要用户授权，授权只覆盖哪一次动作？
- Adapter 返回后，哪些内容可以成为 task evidence？

## 非目标

本阶段不做：

- 不实现真实 adapter 调用。
- 不绕过现有 policy preflight。
- 不把 approval 当成长期授权。
- 不把 raw tool output 原样写入公开日志。
- 不在 CLI 中执行外部动作。
- 不写入真实 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。

## Artifact 类型

本设计包含四类结构化 artifact。

| Artifact | 用途 |
|:---|:---|
| `adapter_request` | 描述一次拟执行动作 |
| `adapter_response` | 描述 adapter 的结构化返回 |
| `approval_record` | 描述一次用户授权或拒绝 |
| `execution_event` | 描述 envelope 与 task ledger 的衔接事件 |

Schema 文件：`adapters/execution-envelope.schema.json`。

样例文件：`adapters/execution-envelope.examples.json`。

## Adapter Request

`adapter_request` 是执行前的只读动作描述。它不代表动作已经发生。

核心字段：

| 字段 | 说明 |
|:---|:---|
| `request_id` | 单次 adapter 请求 id |
| `task_id` | 关联任务 |
| `adapter_id` | 对应 `adapters/adapters.sample.json` 中的 adapter id |
| `operation` | 动作名称，例如 `git_push`、`read_file`、`send_card` |
| `actor` | 发起方，例如 `orchestrator` 或某个 agent id |
| `target` | 本次动作的目标，必须尽量具体 |
| `input` | 已脱敏、可检查的输入参数 |
| `context` | 风险、来源、policy profile、dry-run、approval 引用等上下文 |
| `preflight` | policy 检查摘要 |
| `created_at` | 创建时间 |

示例：

```json
{
  "request_id": "req-20260703-001",
  "task_id": "task-20260703-001",
  "adapter_id": "github-cli",
  "operation": "git_push",
  "actor": "orchestrator",
  "target": "origin/main",
  "input": {
    "remote": "origin",
    "branch": "main"
  },
  "context": {
    "source": "cli",
    "policy_profile": "s-black",
    "risk_level": "external",
    "dry_run": true,
    "requires_approval": true,
    "approval_id": "appr-20260703-001",
    "payload_refs": ["git_diff", "commit_message"]
  },
  "preflight": {
    "status": "needs_approval",
    "findings": [
      {
        "rule_id": "github-cli-approval",
        "severity": "block",
        "action": "require_user_approval",
        "message": "External publish operation requires explicit approval."
      }
    ]
  },
  "created_at": "2026-07-03T10:00:00+08:00"
}
```

## Adapter Response

`adapter_response` 是 adapter 返回后的结构化结果。即使未来接入真实 adapter，也不应该把完整 raw output 直接视为 evidence。

核心字段：

| 字段 | 说明 |
|:---|:---|
| `response_id` | 单次响应 id |
| `request_id` | 对应 request |
| `status` | `succeeded`、`blocked`、`failed`、`needs_approval`、`needs_input`、`skipped` |
| `message` | 人类可读摘要，不能包含 secret |
| `artifacts` | 产物引用，例如文件路径、URL、任务 id |
| `evidence` | 可进入 task ledger 的证据摘要 |
| `raw_ref` | 原始输出引用；默认应为 `null` 或内部受控引用 |
| `error` | 失败时的结构化错误 |
| `finished_at` | 响应完成时间 |

状态映射建议：

| Response status | Task 处理建议 |
|:---|:---|
| `succeeded` | 追加 evidence，进入 postflight / completion check |
| `blocked` | task 进入 `blocked` |
| `failed` | task 进入 `failed` 或交由 orchestrator 判断 |
| `needs_approval` | task 进入 `blocked`，reason=`need_user_approval` |
| `needs_input` | task 进入 `blocked`，reason=`need_user_input` |
| `skipped` | 记录事件，通常不改变任务状态 |

## Approval Record

`approval_record` 只描述一次授权，不代表永久许可。

核心原则：

- 授权必须绑定 `request_id`。
- 授权 scope 必须包含 `task_id`、`adapter_id`、`operation`、`target`。
- `granted` 只能覆盖同一 request，不可复用到其他 target 或 operation。
- `denied` / `expired` 必须阻断执行。

示例：

```json
{
  "approval_id": "appr-20260703-001",
  "request_id": "req-20260703-001",
  "status": "pending",
  "scope": {
    "task_id": "task-20260703-001",
    "adapter_id": "github-cli",
    "operation": "git_push",
    "target": "origin/main"
  },
  "requested_at": "2026-07-03T10:00:01+08:00",
  "decided_at": null,
  "decided_by": null,
  "decision_ref": null
}
```

## Execution Event

`execution_event` 用来把 adapter envelope 映射为 task ledger 可消费的事件。它不是现有 `tasks/event.schema.json` 的替代品，而是 adapter 层更细的中间记录。

常见事件类型：

| event_type | 含义 |
|:---|:---|
| `adapter_preflight` | 已生成 request 并完成 preflight |
| `approval_requested` | 已请求用户授权 |
| `approval_recorded` | 已记录授权结果 |
| `adapter_invocation_planned` | 已准备执行，但本阶段仍不真实执行 |
| `adapter_response_recorded` | 已记录 adapter response |
| `evidence_added` | 已抽取 evidence |
| `postflight_checked` | 已完成 postflight 判断 |

## 最小流程

```text
Task running
  -> build adapter_request
  -> run policy preflight
  -> if needs approval: create approval_record(status=pending)
  -> if approval granted: continue planned invocation
  -> adapter returns adapter_response
  -> extract evidence
  -> create execution_event records
  -> task layer decides blocked / failed / finished / continue
```

在当前阶段，流程停在“可描述、可校验、可审查”，不会真实执行 adapter。

## 与现有模块的关系

| 模块 | 关系 |
|:---|:---|
| Adapter Registry | `adapter_id` 必须来自注册表 |
| Policy Schema | `preflight.findings` 使用 policy finding 结构 |
| Task Ledger | `task_id` 关联任务；response evidence 可转换为 task evidence |
| Completion Rules | `succeeded` 不等于任务完成，仍需 evidence 和 postflight |
| Public Scan | 所有公开样例不得包含真实路径、密钥或内部运行协议 |

## 后续实现候选

下一步可以继续保持只读，做一个 `adapter plan` 命令：

```bash
python -m agent_runtime.cli adapter plan \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
```

该命令只生成 request / approval / event 草案，不执行真实动作，不写 ledger。它可以把当前 `check action` 的 preflight 结果进一步包装成 adapter execution envelope。
