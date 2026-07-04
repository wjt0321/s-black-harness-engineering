# 10 — CLI POC 使用说明

## 当前状态

`s-black harness engineering` 现在已经有第一版最小只读 CLI POC。

它不是完整 Runtime，也不会执行外部动作。当前 CLI 只用于读取本仓库内的 schema、sample、JSONL 和文档，做结构校验、规则检查和列表查询。

## 运行方式

在仓库根目录运行：

```bash
python -m agent_runtime.cli <command>
```

也可以使用：

```bash
python -m agent_runtime <command>
```

如果已经以可编辑模式安装，也可以使用 console script：

```bash
python -m pip install -e .[dev]
agent-runtime <command>
```

## 快速自检

```bash
python -m agent_runtime.cli doctor
```

期望输出：

```text
PASS
Next: All checks passed.
```

`doctor` 会检查：

- 必要目录是否存在。
- 必要文件是否存在。
- JSON schema 是否为合法 JSON。
- sample JSON 是否能通过对应 schema。
- JSONL 样例是否逐行合法。
- 仓库文本文件是否命中公开发布风险扫描。

## 文本密钥扫描

```bash
python -m agent_runtime.cli check text --text hello
```

期望输出：

```text
PASS
```

从文件读取：

```bash
python -m agent_runtime.cli check text --file README.md
```

从 stdin 读取：

```bash
echo hello | python -m agent_runtime.cli check text --stdin
```

JSON 输出：

```bash
python -m agent_runtime.cli check text --text hello --json
```

注意：如果命中密钥模式，CLI 只输出规则 id、行号、列号和提示，不回显完整匹配值。

## 路径检查

```bash
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
```

写入检查：

```bash
python -m agent_runtime.cli check path ./some-target.md --write
```

删除检查：

```bash
python -m agent_runtime.cli check path ./some-target.md --delete
```

当前路径检查只做 policy 规则判断，不会创建、修改或删除任何文件。

## Action 检查

`check action` 会聚合 adapter 风险、command rules、publish rules 和 completion rules 的只读判断。它只输出 preflight / postflight 要求，不执行真实动作。

检查 GitHub push 这类外部动作：

```bash
python -m agent_runtime.cli check action --adapter github-cli --operation git_push --target origin/main
```

期望输出类似：

```text
NEEDS_APPROVAL
- github-cli-approval: github-cli: this external operation requires explicit user approval.
Next: Ask for approval for this task, this target, this operation.
```

按单个 policy profile 降噪：

```bash
python -m agent_runtime.cli --policy-profile s-black check action --adapter github-cli --operation git_push --target origin/main
```

低风险只读动作示例：

```bash
python -m agent_runtime.cli check action --adapter shell-local --operation read_file --target docs/README.md
```

期望输出：

```text
PASS
```

## 任务账本查询

查看任务快照：

```bash
python -m agent_runtime.cli task status task-20260703-001
```

期望输出会包含任务标题、状态、负责人、产物、证据和下一步。

查看任务事件流：

```bash
python -m agent_runtime.cli task events task-20260703-001
```

当前命令优先读取 `tasks/tasks.jsonl` 与 `tasks/events.jsonl`；如果真实 ledger 不存在，才回退到仓库内 `.examples.jsonl`。CLI 仍然只读，不会写入真实任务账本。

JSON 输出：

```bash
python -m agent_runtime.cli task status task-20260703-001 --json
python -m agent_runtime.cli task events task-20260703-001 --json
```

## Ledger 写入前 Preflight Schema 校验

在真实写入 `tasks/tasks.jsonl` 或 `tasks/events.jsonl` 之前，可以先对候选 JSONL 文件做只读 schema 校验：

```bash
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task
python -m agent_runtime.cli task validate --record-file tasks/events.jsonl --schema event
```

该命令仅读取并校验项目根目录内的安全 JSONL 文件，不会写入、追加或修改任何 ledger。失败时会输出错的行号、schema 类型和简短错误摘要，不会回显整条 record。

JSON 输出：

```bash
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task --json
```

## Ledger 跨记录一致性检查

在写入前，还可以对 task 与 event ledger 做跨记录一致性检查：

```bash
python -m agent_runtime.cli task check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

检查内容：

- 每个 `event.task_id` 必须存在于 task ledger。
- 每个 task 的事件按 `timestamp` 排序后，状态流转必须连续合法。
- `created` 事件的 `from_status` 必须为 `null`。
- `finished`/`failed` 为终态，之后不得再进入 `running`/`planned`。
- task snapshot 的 `status` 必须与该 task 最新带 `to_status` 的事件一致。

该命令只读取 JSONL 文件，不写入、不修复、不追加 ledger。

JSON 输出：

```bash
python -m agent_runtime.cli task check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --json
```

## Adapter Execution Envelope 计划

`adapter plan` 把 `check action` 的 preflight 结果包装成只读的 Adapter execution envelope 草案。它不会执行真实 adapter、不会访问网络、不会写入 task ledger。

生成 GitHub push 的 envelope（需要授权）：

```bash
python -m agent_runtime.cli adapter plan \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
```

期望输出包含：

- `adapter_request`：preflight 状态、findings、context（含 `dry_run: true`）。
- `approval_record`：当 preflight 状态为 `needs_approval` 时生成。
- `execution_event`（`event_type: approval_requested`）：当需要授权时生成。

生成低风险 shell read 的 envelope（不需要授权）：

```bash
python -m agent_runtime.cli adapter plan \
  --adapter shell-local \
  --operation read_file \
  --target README.md
```

默认人类输出只展示 artifact 摘要，不打印完整 envelope；需要完整 envelope 时使用 JSON 输出：

```bash
python -m agent_runtime.cli adapter plan \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --json
```

支持 `--agent` / `--assignee` 自动选择 policy profile，也支持 `--actor` 和 `--task-id` 自定义 envelope 字段：

```bash
python -m agent_runtime.cli --agent orchestrator adapter plan \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --actor cli \
  --task-id task-20260703-001
```

## Adapter Execution Envelope 校验

`adapter validate` 用于只读校验已有的 adapter execution envelope JSON 文件。校验分两步：

1. **Schema 校验**：检查 envelope 是否符合 `adapters/execution-envelope.schema.json`。
2. **跨 artifact 一致性校验**：检查 artifact 之间的引用和 scope 是否一致。

它不会执行 adapter、不会访问网络、不会写入 ledger。

```bash
python -m agent_runtime.cli adapter validate \
  --file adapters/execution-envelope.examples.json
```

JSON 输出：

```bash
python -m agent_runtime.cli adapter validate \
  --file adapters/execution-envelope.examples.json \
  --json
```

校验规则：

- 文件必须在项目根目录内。
- 文件必须是安全的 `.json` 文件；不允许 `.env`、credential、密钥类文件。
- Schema 失败时只输出相对路径、schema 错误路径/规则和简短摘要，不回显整条 artifact 或敏感值。
- 一致性失败时只输出相对路径、artifact id、规则 id 和简短摘要，例如：
  - `duplicate-request-id`：`adapter_request.request_id` 必须唯一。
  - `approval-references-unknown-request`、`response-references-unknown-request`、`event-references-unknown-request`：引用必须指向存在的 `adapter_request`。
  - `approval-scope-mismatch`：`approval_record.scope` 的 `task_id` / `adapter_id` / `operation` / `target` 必须与对应 `adapter_request` 一致。
  - `needs-approval-missing-record`：`requires_approval` 且 `preflight.status == "needs_approval"` 的请求必须有对应的 `approval_record`（状态可为 `pending`、`granted`、`denied` 或 `expired`）。
  - `approval-requested-event-unknown-approval`：`approval_requested` 事件的 `metadata.approval_id` 必须引用存在的 `approval_record`。

## Adapter Execution Envelope 摘要

`adapter inspect` 在 `adapter validate` 的基础上输出一个紧凑的 envelope 摘要，用于快速了解 envelope 内 artifact 的分布、请求状态、授权情况和证据数量。

```bash
python -m agent_runtime.cli adapter inspect \
  --file adapters/execution-envelope.examples.json
```

期望输出包含：

- envelope 的 `version` 与 `description`。
- 各 `artifact_type` 的数量。
- 每个 `adapter_request` 的 `request_id`、`adapter_id`、`operation`、`target`、`preflight.status`、`requires_approval`。
- 每个 `approval_record` 的 `approval_id`、`request_id`、`status`。
- 每个 `adapter_response` 的 `response_id`、`request_id`、`status`、`evidence` 数量。
- `execution_event` 按 `event_type` 聚合的计数。
- 总体指标：`requires_approval_count`、`pending_approval_count`、`response_count`、`evidence_count`。

人类输出保持紧凑，不打印完整 envelope，也不打印 `input` payload。

JSON 输出：

```bash
python -m agent_runtime.cli adapter inspect \
  --file adapters/execution-envelope.examples.json \
  --json
```

JSON 结构为：

```json
{
  "status": "pass",
  "summary": {
    "version": 1,
    "description": "...",
    "artifact_counts": {...},
    "requests": [...],
    "approvals": [...],
    "responses": [...],
    "events": {...},
    "overall": {...}
  }
}
```

行为约束：

- 命令会先执行 schema + consistency 校验；若校验失败，返回与 `adapter validate` 相同的状态/返回码，不会继续输出 `summary`。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 失败输出不回显完整 artifact 或 input payload。

## Adapter Approval 检查

`adapter approval check` 用于检查某个 `adapter_request` 是否存在可继续执行的 `approval_record`。它只读访问 envelope JSON 文件，不执行 adapter、不写 ledger、不访问网络。

检查示例 envelope 中 `req-20260703-001` 的授权状态（当前为 `pending`）：

```bash
python -m agent_runtime.cli adapter approval check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-001
```

期望输出：

```text
NEEDS_APPROVAL
request_id=req-20260703-001 adapter_id=github-cli operation=git_push target=origin/main requires_approval=True approval_id=appr-20260703-001 approval_status=pending
- approval-pending: Approval appr-20260703-001 is pending.
Next: Wait for the approval to be granted before proceeding.
```

JSON 输出：

```bash
python -m agent_runtime.cli adapter approval check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json
```

JSON 结构：

```json
{
  "status": "needs_approval",
  "approval": {
    "request_id": "req-20260703-001",
    "adapter_id": "github-cli",
    "operation": "git_push",
    "target": "origin/main",
    "requires_approval": true,
    "approval_id": "appr-20260703-001",
    "approval_status": "pending",
    "decision_ref": null
  },
  "findings": [
    {
      "rule_id": "approval-pending",
      "severity": "warn",
      "action": "needs_approval",
      "message": "Approval appr-20260703-001 is pending."
    }
  ],
  "next_action": "Wait for the approval to be granted before proceeding."
}
```

状态映射：

| `approval_status` | CLI 返回状态 | 返回码 | 说明 |
|:---|:---:|:---:|:---|
| 请求不存在 | `needs_input` | `4` | `approval-request-not-found` |
| `requires_approval: false` | `pass` | `0` | 不需要授权 |
| `granted` | `pass` | `0` | 授权已批准，可继续 |
| `pending` | `needs_approval` | `3` | 等待授权 |
| `denied` | `blocked` | `2` | 授权被拒绝，不可继续 |
| `expired` | `blocked` | `2` | 授权已过期，不可继续 |

行为约束：

- 先执行与 `adapter validate` 相同的 schema + consistency 校验；校验失败时返回同样的状态/返回码，且不输出 `approval` 摘要。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 输出摘要包含 `request_id`、`adapter_id`、`operation`、`target`、`requires_approval`、`approval_id`、`approval_status`、`decision_ref`（如有），不输出 `input` payload。
- 文件必须在项目根目录内，且为安全的 `.json` 文件；`.env`、credential、密钥类文件会被拒绝。

## Adapter Response 检查

`adapter response check` 用于检查某个 `adapter_request` 是否已有 `adapter_response` 以及 response/evidence 状态。它只读访问 envelope JSON 文件，不执行 adapter、不写 ledger、不访问网络。

检查示例 envelope 中 `req-20260703-002` 的响应状态（当前为 `succeeded` 且含 evidence）：

```bash
python -m agent_runtime.cli adapter response check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002
```

期望输出：

```text
PASS
request_id=req-20260703-002 adapter_id=shell-local operation=read_file target=docs/06-adapter-layer.md response_id=resp-20260703-001 response_status=succeeded artifact_count=1 evidence_count=1 raw_ref_present=False
```

JSON 输出：

```bash
python -m agent_runtime.cli adapter response check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002 \
  --json
```

JSON 结构：

```json
{
  "status": "pass",
  "response": {
    "request_id": "req-20260703-002",
    "adapter_id": "shell-local",
    "operation": "read_file",
    "target": "docs/06-adapter-layer.md",
    "response_id": "resp-20260703-001",
    "response_status": "succeeded",
    "artifact_count": 1,
    "evidence_count": 1,
    "raw_ref_present": false
  },
  "next_action": "Response succeeded and evidence is present."
}
```

状态映射：

| response 状态 | CLI 返回状态 | 返回码 | rule_id | 说明 |
|:---|:---:|:---:|:---|:---|
| 请求不存在 | `needs_input` | `4` | `response-request-not-found` | 指定的 `request_id` 不在 envelope 中 |
| 无 `adapter_response` | `needs_input` | `4` | `response-missing` | 请求存在但尚未记录 response |
| `succeeded` 且 `evidence_count > 0` | `pass` | `0` | — | response 成功且包含 evidence |
| `succeeded` 但 `evidence_count == 0` | `blocked` | `2` | `response-evidence-missing` | response 成功但缺少 evidence |
| `blocked` | `blocked` | `2` | `response-blocked` | response 被阻断 |
| `failed` | `blocked` | `2` | `response-failed` | response 失败 |
| `needs_approval` | `needs_approval` | `3` | `response-needs-approval` | response 等待授权 |
| `needs_input` | `needs_input` | `4` | `response-needs-input` | response 需要补充输入 |
| `skipped` | `blocked` | `2` | `response-skipped` | response 被跳过，不能作为完成证据 |

行为约束：

- 先执行与 `adapter validate` 相同的 schema + consistency 校验；校验失败时返回同样的状态/返回码，且不输出 `response` 摘要。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 输出摘要包含 `request_id`、`adapter_id`、`operation`、`target`、`response_id`、`response_status`、`artifact_count`、`evidence_count`、`raw_ref_present`；不输出 `input` payload、evidence description 或 `raw_ref` 值。
- 文件必须在项目根目录内，且为安全的 `.json` 文件；`.env`、credential、密钥类文件会被拒绝。

## Adapter Gate 检查

`adapter gate check` 聚合 `adapter approval check` 与 `adapter response check`，对某个 `adapter_request` 给出当前是否可继续的单一判断。它只读访问 envelope JSON 文件，不执行 adapter、不写 ledger、不访问网络。

检查示例 envelope 中 `req-20260703-002`（不需要授权且已有 succeeded + evidence 的 response）：

```bash
python -m agent_runtime.cli adapter gate check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002
```

期望输出：

```text
PASS
stage=response request_id=req-20260703-002 approval_status=pass response_status=pass can_proceed=True
```

检查 `req-20260703-001`（当前 approval 为 pending）会停在 approval 阶段：

```bash
python -m agent_runtime.cli adapter gate check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-001
```

期望输出：

```text
NEEDS_APPROVAL
stage=approval request_id=req-20260703-001 approval_status=needs_approval response_status=None can_proceed=False
- approval-pending: Approval appr-20260703-001 is pending.
Next: Wait for the approval to be granted before proceeding.
```

JSON 输出：

```bash
python -m agent_runtime.cli adapter gate check \
  --file adapters/execution-envelope.examples.json \
  --request-id req-20260703-002 \
  --json
```

JSON 结构：

```json
{
  "status": "pass",
  "gate": {
    "request_id": "req-20260703-002",
    "stage": "response",
    "approval_status": "pass",
    "response_status": "pass",
    "can_proceed": true,
    "next_action": "Response succeeded and evidence is present.",
    "approval": {
      "request_id": "req-20260703-002",
      "adapter_id": "shell-local",
      "operation": "read_file",
      "target": "docs/06-adapter-layer.md",
      "requires_approval": false,
      "approval_id": null,
      "approval_status": null,
      "decision_ref": null
    },
    "response": {
      "request_id": "req-20260703-002",
      "adapter_id": "shell-local",
      "operation": "read_file",
      "target": "docs/06-adapter-layer.md",
      "response_id": "resp-20260703-001",
      "response_status": "succeeded",
      "artifact_count": 1,
      "evidence_count": 1,
      "raw_ref_present": false
    }
  },
  "next_action": "Response succeeded and evidence is present."
}
```

聚合规则：

* 先执行 approval check。
* 若 approval check 返回非 `pass` 状态（`validation_failed` / `error` / `needs_input` / `needs_approval` / `blocked`），gate 直接返回同等状态，`stage` 标记为 `approval`，不再执行 response check。
* 若 approval check 返回 `pass`，再执行 response check；response check 的状态成为 gate 最终状态，`stage` 标记为 `response`。
* 最终 `status == "pass"` 当且仅当 approval 已满足且 response 为 succeeded 并包含 evidence；此时 `can_proceed` 为 `true`，否则为 `false`。

状态映射：

| 场景 | CLI 返回状态 | 返回码 | stage | can_proceed | 说明 |
|:---|:---:|:---:|:---:|:---:|:---|
| 不需要授权 + succeeded + evidence | `pass` | `0` | `response` | `true` | 可继续 |
| approval pending | `needs_approval` | `3` | `approval` | `false` | 等待授权 |
| approval denied / expired | `blocked` | `2` | `approval` | `false` | 授权被拒绝/过期 |
| approval granted 但无 response | `needs_input` | `4` | `response` | `false` | 等待 response |
| response succeeded 但无 evidence | `blocked` | `2` | `response` | `false` | 缺少证据 |
| response blocked/failed/skipped | `blocked` | `2` | `response` | `false` | response 未成功 |
| response needs_approval/needs_input | 对应状态 | `3`/`4` | `response` | `false` | response 本身未就绪 |
| 请求不存在 | `needs_input` | `4` | `approval` | `false` | 指定 request_id 不在 envelope 中 |
| envelope 非法 | `validation_failed`/`error` | `5`/`1` | `approval` | `false` | 校验失败或路径/文件不安全 |

行为约束：

- 复用现有的 `check_adapter_approval` 与 `check_adapter_response`，保持与二者相同的 schema + consistency 前置校验。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 输出摘要包含 `request_id`、`stage`、`approval_status`、`response_status`、`can_proceed`、`next_action`，可附带 approval/response 子摘要；不输出 `input` payload、evidence description 或 `raw_ref` 值。
- 文件必须在项目根目录内，且为安全的 `.json` 文件；`.env`、credential、密钥类文件会被拒绝。

## Runtime Gate 检查

`runtime gate check` 把 task ledger、task event stream 与 adapter execution envelope 聚合成一个单一判断：给定 task + request 对当前能否继续推进。它只读访问 ledger 和 envelope，不执行 adapter、不写 ledger、不访问网络。

检查示例 task 与 request（task 已 finished，因此即使 adapter gate 通过也不会继续推进）：

```bash
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json
```

显式指定 ledger 文件：

```bash
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

JSON 输出（仍脱敏）：

```bash
python -m agent_runtime.cli runtime gate check \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

输出结构：

```json
{
  "status": "blocked",
  "task_id": "task-20260703-001",
  "task_status": "finished",
  "request_id": "req-20260703-002",
  "gate": {
    "stage": "response",
    "approval_status": "pass",
    "response_status": "pass",
    "can_proceed": true
  },
  "suggested_event_draft": {
    "event_type": "blocked",
    "from_status": "finished",
    "to_status": "finished",
    "message": "Task is already in a terminal state (finished); do not proceed.",
    "metadata": {
      "request_id": "req-20260703-002",
      "adapter_id": "shell-local",
      "operation": "read_file"
    },
    "artifacts": []
  },
  "next_action": "Task is already in a terminal state (finished); do not proceed."
}
```

聚合规则：

* task 必须存在于 task ledger；否则返回 `error`。
* request 必须存在于 envelope；否则返回 `needs_input`。
* envelope 必须能通过 schema + consistency 校验；否则返回 `validation_failed` / `error`。
* task 处于 `finished` / `failed` 终态时，即使 adapter gate 通过也会返回 `blocked`。
* `can_proceed == true` 当且仅当 task 非终态且 adapter gate `can_proceed == true`。

建议的 event draft：

* gate 通过 -> `status_changed`，`to_status: running`。
* approval pending -> `blocked`，`blocked_reason: need_user_approval`。
* approval denied / expired -> `blocked`，`blocked_reason: policy_blocked`。
* response 缺失 / needs_input -> `blocked`，`blocked_reason: need_user_input`。
* response blocked / failed / skipped -> `blocked`，`blocked_reason: tool_failed`。
* task 已是终态 -> `blocked`，`to_status` 保持终态。

行为约束：

- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 人类/JSON 输出中不包含完整 `input`、`evidence`、`raw_ref`、`decision_ref` 值。
- 建议的 event draft 只打印摘要，不落盘；metadata 仅保留 id、adapter/operation 名称、阻塞原因等安全字段。

## Runtime Ledger Audit

`runtime check-ledger` 检查 task ledger、event ledger 与 adapter execution envelope 之间的跨系统一致性。它保持只读，不执行 adapter、不写 ledger、不访问网络。

```bash
python -m agent_runtime.cli runtime check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime check-ledger \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

检查内容：

- tasks/events 基础一致性（复用 `task check-ledger`）。
- envelope 中 `adapter_request.task_id` 是否存在于 task ledger。
- envelope 中 `execution_event.task_id` 是否存在于 task ledger。
- envelope 中 `execution_event.request_id` 是否引用已知 `adapter_request`。
- task ledger 中是否存在与 request_id 相关的 event metadata/artifacts 线索（仅 warn）。
- task 已 `finished` / `failed` 但 envelope request 仍要求继续时 warn。

输出不回显完整 `input`、`evidence`、`raw_ref`、`decision_ref`、`target` 值。

## Runtime Plan

`runtime plan` 为指定 task 生成 adapter action 的只读草案摘要。它会先检查 task 是否存在且未进入终态，然后复用 `adapter plan` 的 preflight 逻辑生成 `request_draft`；当动作需要授权时，还会生成 `approval_draft` 与 `event_draft` 摘要。所有草案不落盘。

低风险只读动作示例：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md
```

需要授权的外部动作示例：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter github-cli \
  --operation git_push \
  --target origin/main
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

支持 `--actor`、`--tasks-file`，以及 `--policy-profile` / `--agent` / `--assignee` 选择 policy profile。详细输出格式与状态映射见 `docs/16-runtime-plan.md`。

行为约束：

- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- task 不存在时返回 `error`；task 已 `finished` / `failed` 时返回 `blocked`。
- 输出不回显完整 `input` payload、`evidence`、`raw_ref`、`decision_ref` 或 secret match。

## Registry 查询

列出 Agent：

```bash
python -m agent_runtime.cli agents list
```

按 capability 过滤：

```bash
python -m agent_runtime.cli agents list --capability light_coding
```

列出 Adapter：

```bash
python -m agent_runtime.cli adapters list
```

按 kind 过滤：

```bash
python -m agent_runtime.cli adapters list --kind github
```

按 risk 过滤：

```bash
python -m agent_runtime.cli adapters list --risk external
```

列出 Policy：

```bash
python -m agent_runtime.cli policies list
```

列出 Policy（自动按 agent 选择 profile）：

```bash
python -m agent_runtime.cli --agent orchestrator policies list
python -m agent_runtime.cli --assignee media-agent policies list
```

## 全局参数

| 参数 | 说明 |
|:---|:---|
| `--root <path>` | 指定项目根目录，默认当前目录 |
| `--policy <file>` | 指定单个 policy 文件，最高优先级 |
| `--policy-profile <name>` | 指定样例 policy profile：`s-black`、`wangcai`、`dabai` 或 `all` |
| `--agent <agent-id>` | 按 agent id 自动推断 policy profile |
| `--assignee <agent-id>` | 按 assignee id 自动推断 policy profile（`--agent` 的别名） |
| `--json` | 输出 JSON |
| `--no-color` | 禁用彩色输出 |
| `--quiet` | 保留给后续精简输出使用 |
| `--verbose` | 保留给后续诊断输出使用 |

## Policy Profile 解析优先级

`check text`、`check path`、`check action`、`policies list`、`adapter plan` 等命令需要加载 policy 时，按以下优先级解析：

1. `--policy <file>`：直接使用指定 policy 文件，最高优先级。
2. `--policy-profile <name>`：手动指定 profile。
3. `--agent <agent-id>` 或 `--assignee <agent-id>`：自动推断 profile。
4. 默认 `all`。

当前自动映射从 `agents/agents.sample.json` 的 `policy_profile` 字段读取：

| agent / assignee | profile |
|:---|:---|
| `orchestrator` | `s-black` |
| `media-agent` | `wangcai` |
| `memory-agent` | `dabai` |
| `kimi-code`、`claude-code`、`omp` | `s-black` |
| 未知 | `all` |

## 返回码

| 返回码 | 含义 |
|:---|:---|
| `0` | 通过或查询成功 |
| `1` | CLI 使用错误或内部错误 |
| `2` | policy 阻断 |
| `3` | 需要用户授权 |
| `4` | 需要更多输入 |
| `5` | 校验失败 |

## 当前安全边界

第一版 CLI 保持只读：

- 不执行外部命令。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写真实 task ledger。
- 不读取 `.env`、`.env.local` 或密钥文件。
- 不回显完整 secret match。

## 公开发布前扫描

仓库内已提供只读 public scan 脚本，用于在发布前检查文本文件中是否残留 token 模式或本机路径痕迹：

```bash
python tools/public_scan.py
```

扫描规则包括常见 token 模式、Windows 绝对路径（如 `DRIVE:/...`）、Unix home 路径（如 `/home/<user>/`）等。命中时只输出相对路径、行号和规则 id，不输出完整命中值。

返回码：

- `0`：通过
- `1`：发现风险项

该脚本已加入 CI，在 `pytest` 和 `doctor` 之后运行。

## 当前限制

- `check action` 仍然只做 preflight 判断，不执行真实外部动作。
- `tasks/tasks.jsonl` 和 `tasks/events.jsonl` 目前只支持 CLI 查询，不支持 CLI 写入。
- 还没有后台服务。
- 还没有插件系统或真实 adapter 执行。

## 阶段性结论

到这一版为止，项目已经从纯文档推进到一个可运行、可测试、可审查的只读 POC。

这可以作为后续 Runtime 实现的第一块稳定地基：先验证规则、schema、registry 和 CLI 边界，再逐步扩展真实执行能力。
