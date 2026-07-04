# 16 — Runtime Plan（任务级动作计划）

`runtime plan` 是 runtime gate 的前置一步：给定一个 task 和一组 adapter + operation + target，先确认 task 存在且未进入终态，再生成只读的 adapter_request 草案摘要，以及（当需要授权时）approval_record 与 execution_event 草案摘要。它**不执行** adapter、**不访问**网络、**不写** ledger、**不读取** credential。

## 目标

- 在真正推进 task 之前，先把待执行动作变成可审计的草案。
- 与 `adapter plan` 不同：`runtime plan` 把草案绑定到具体 task，并受 task 状态约束。
- 为后续 `runtime gate check` 提供输入：runtime plan 生成的 request_id、approval_id 等可以写入 envelope 后再被 gate 检查。

## 非目标

- 不执行真实 adapter 调用。
- 不写入 task ledger、event ledger 或 adapter envelope 文件。
- 不做长期后台调度或模型路由决策。

## 数据流

1. CLI 读取 `--task-id`，通过 `agent_runtime/tasks.py` 加载 task snapshot。
2. 若 task 不存在，返回 `error`。
3. 若 task 状态为 `finished` / `failed` 终态，直接返回 `blocked`，不生成任何草案。
4. 否则复用 `agent_runtime/adapter_plan.plan_adapter_action()` 做 preflight：
   - 加载 adapter registry，确认 adapter 存在。
   - 运行 `check_action`，聚合 risk_level、`requires_approval`、command_rules、publish_rules、completion_rules。
   - 生成 envelope 草案，schema 校验通过后才继续。
5. 从 envelope 提取摘要，构造 `request_draft`；当 preflight 状态为 `needs_approval` 时，额外提取 `approval_draft` 与 `event_draft`。
6. 返回 compact 人类摘要或结构化 JSON；均不回显完整 input payload / evidence / raw_ref / decision_ref。

## CLI 用法

为一个 running 状态的 task 规划一次低风险只读动作：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md
```

期望人类输出：

```text
PASS
task_id=task-20260703-001 task_status=running
request_draft: request_id=req-20260704-... adapter=shell-local operation=read_file target=docs/06-adapter-layer.md profile=all risk=local requires_approval=False preflight=pass
```

为一个 running 状态的 task 规划需要授权的外部动作：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
```

期望人类输出包含 `approval_draft` 与 `event_draft`：

```text
NEEDS_APPROVAL
task_id=task-20260703-001 task_status=running
request_draft: request_id=req-20260704-... adapter=github-cli operation=git_push target=origin/main profile=all risk=external requires_approval=True preflight=needs_approval
approval_draft: approval_id=appr-20260704-... request_id=req-20260704-... status=pending
event_draft: event_id=exe-20260704-... event_type=approval_requested approval_id=appr-20260704-... adapter=github-cli operation=git_push
- github-cli-approval: github-cli: this external operation requires explicit user approval.
- github-publish-preflight: GitHub 发布前必须完成密钥扫描、Markdown 格式检查、目标确认和用户授权。
Next: ask for approval for this task, target, and operation; run secret scan for the payload or diff.
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --json
```

输出结构：

```json
{
  "status": "pass",
  "task_id": "task-20260703-001",
  "task_status": "running",
  "request_draft": {
    "request_id": "req-20260704-...",
    "adapter_id": "shell-local",
    "operation": "read_file",
    "target": "docs/06-adapter-layer.md",
    "actor": "cli",
    "policy_profile": "all",
    "risk_level": "local",
    "requires_approval": false,
    "preflight_status": "pass"
  },
  "approval_draft": null,
  "event_draft": null,
  "findings": [],
  "next_action": null
}
```

当需要授权时：

```json
{
  "status": "needs_approval",
  "task_id": "task-20260703-001",
  "task_status": "running",
  "request_draft": {
    "request_id": "req-20260704-...",
    "adapter_id": "github-cli",
    "operation": "git_push",
    "target": "origin/main",
    "actor": "cli",
    "policy_profile": "all",
    "risk_level": "external",
    "requires_approval": true,
    "preflight_status": "needs_approval"
  },
  "approval_draft": {
    "approval_id": "appr-20260704-...",
    "request_id": "req-20260704-...",
    "status": "pending"
  },
  "event_draft": {
    "event_id": "exe-20260704-...",
    "event_type": "approval_requested",
    "approval_id": "appr-20260704-...",
    "adapter_id": "github-cli",
    "operation": "git_push"
  },
  "findings": [
    {"rule_id": "github-cli-approval", ...},
    {"rule_id": "github-publish-preflight", ...}
  ],
  "next_action": "..."
}
```

支持 `--actor` 自定义执行者，以及 `--tasks-file` 显式指定 task ledger：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --actor runtime-orchestrator \
  --tasks-file tasks/tasks.jsonl
```

同样支持 `--policy-profile` / `--agent` / `--assignee` 自动选择 policy profile：

```bash
python -m agent_runtime.cli --agent orchestrator runtime plan \
  --task-id task-20260703-001 \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
```

## 状态与返回码

| 场景 | CLI 状态 | 返回码 | 说明 |
|:---|:---:|:---:|:---|
| task 不存在 | `error` | `1` | `task-not-found` |
| task 处于 `finished` / `failed` | `blocked` | `2` | `task-terminal`；不生成草案 |
| adapter 不存在 | `error` | `1` | `adapter-not-found` |
| 生成 envelope 失败或 schema 不通过 | `error` | `1` | `envelope-schema-error` / `missing-envelope` |
| policy 阻断 | `blocked` | `2` | 如命中 command rule |
| 需要授权 | `needs_approval` | `3` | 生成 request/approval/event 草案 |
| 需要更多输入 | `needs_input` | `4` | 如 publish rule 要求 secret scan |
| 低风险动作通过 | `pass` | `0` | 只生成 request 草案 |

## 模块关系

- `agent_runtime/cli.py`：新增 `runtime plan` 子命令，解析参数并调用 `plan_runtime_action()`。
- `agent_runtime/runtime_plan.py`：实现 `plan_runtime_action()` 与 `RuntimePlanResult`。
- `agent_runtime/tasks.py`：通过 `find_task()` 读取 task snapshot。
- `agent_runtime/adapter_plan.py`：生成 envelope 草案并做 schema 校验。
- `agent_runtime/policy.py` / `agent_runtime/policy_profile.py`：preflight 规则与 profile 解析。

## 安全边界

- 只读：不执行外部命令、不访问网络、不发送消息、不删除文件、不写真实 task ledger、不读取 `.env`/credential。
- 输出不回显完整 `input` payload、evidence description、`raw_ref`、`decision_ref` 或 secret match。
- `request_draft` 只保留 request_id、adapter_id、operation、target、actor、policy_profile、risk_level、requires_approval、preflight_status。
- `approval_draft` 只保留 approval_id、request_id、status。
- `event_draft` 只保留 event_id、event_type、approval_id、adapter_id、operation。
- 所有草案不落盘；调用者需要显式保存到 envelope 或 ledger 才能进入后续 gate 检查。
