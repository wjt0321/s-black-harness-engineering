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

## 恢复上下文

当文档越来越多、需要快速恢复项目状态时，先读这个命令的输出，而不是从头翻所有 docs：

```bash
python -m agent_runtime.cli docs context
python -m agent_runtime.cli docs context --json
```

输出包含：

- 当前里程碑基线（tag / commit）
- 当前阶段与状态（优先来自 `docs/000-stage-digest.md`，缺失时回退到 README 阶段进度）
- 推荐恢复阅读列表（top 5~10，优先使用 digest 的恢复顺序，再补充 index、roadmap、最新 release notes、progress、最新 handoff）
- 下一步设计入口（优先来自 digest，缺失时来自 roadmap 中下一个高优先级阶段）
- 文档总量安全摘要（总数、编号范围、最近 3 份编号文档、最新 handoff、`digest_available` 标志）

说明：

- 只读本地 markdown，不联网、不用 LLM、不读 credential。
- 输出紧凑，不回显完整 roadmap/progress/digest 长文本。
- 如果存在 `docs/000-stage-digest.md`，会优先消费其中的紧凑字段；digest 缺失或字段不全时自动回退到 `README.md` / `docs/00-index.md` / `docs/02-roadmap.md` / `tasks/progress.md` 的解析。
- 如果关键来源缺失，会返回 `warn` 并提示缺少哪些文件。

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

### Runtime Plan Envelope Draft（--draft-json）

`runtime plan` 默认输出 compact 摘要。若需要拿到可直接送入 `adapter validate` 或后续 gate 的完整 envelope 机器草案，使用 `--draft-json`：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --draft-json
```

输出结构：

```json
{
  "status": "needs_approval",
  "task_id": "task-20260703-001",
  "task_status": "running",
  "envelope_draft": {
    "version": 1,
    "description": "Adapter execution plan for github-cli git_push",
    "artifacts": [
      {
        "artifact_type": "adapter_request",
        "request_id": "req-20260704-...",
        "task_id": "task-20260703-001",
        "adapter_id": "github-cli",
        "operation": "git_push",
        "actor": "cli",
        "target": "origin/main",
        "input": {
          "operation": "git_push",
          "target": "origin/main"
        },
        "context": {
          "source": "cli",
          "policy_profile": "all",
          "risk_level": "external",
          "dry_run": true,
          "requires_approval": true,
          "approval_id": "appr-20260704-...",
          "payload_refs": []
        },
        "preflight": {
          "status": "needs_approval",
          "findings": []
        },
        "created_at": "2026-07-04T..."
      },
      {
        "artifact_type": "approval_record",
        "approval_id": "appr-20260704-...",
        "request_id": "req-20260704-...",
        "status": "pending",
        "scope": {
          "task_id": "task-20260703-001",
          "adapter_id": "github-cli",
          "operation": "git_push",
          "target": "origin/main"
        },
        "requested_at": "2026-07-04T...",
        "decided_at": null,
        "decided_by": null
      },
      {
        "artifact_type": "execution_event",
        "event_id": "exe-20260704-...",
        "task_id": "task-20260703-001",
        "request_id": "req-20260704-...",
        "timestamp": "2026-07-04T...",
        "actor": "cli",
        "event_type": "approval_requested",
        "message": "Approval requested before adapter execution.",
        "metadata": {
          "approval_id": "appr-20260704-...",
          "adapter_id": "github-cli",
          "operation": "git_push",
          "target": "origin/main",
          "preflight_status": "needs_approval"
        }
      }
    ]
  },
  "findings": [],
  "next_action": "..."
}
```

行为约束：

- `envelope_draft` 已经过 `adapters/execution-envelope.schema.json` schema 校验。
- `input` payload 保持最小，仅包含 `operation` 与 `target`。
- 不输出 `raw_ref`；pending `approval_record` 不包含 `decision_ref` 字段。
- task 不存在或已处于 `finished` / `failed` 终态时，`envelope_draft` 为 `null`。
- 普通 `--json` 仍保持 compact 摘要输出，不包含 `envelope_draft`。
- task 不存在时返回 `error`；task 已 `finished` / `failed` 时返回 `blocked`。
- 输出不回显完整 `input` payload、`evidence`、`raw_ref`、`decision_ref` 或 secret match。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。

## Runtime Draft 校验

`runtime draft validate` 用于只读校验 `runtime plan --draft-json` 产生的 envelope draft。它接受两种输入格式：

- 直接 envelope：`{"version": 1, "artifacts": [...]}`
- `runtime plan --draft-json` 外层包装：`{"status": "...", "envelope_draft": {...}}`

从文件校验：

```bash
python -m agent_runtime.cli runtime draft validate --file draft.json
```

从 stdin 校验：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --draft-json | python -m agent_runtime.cli runtime draft validate --stdin
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime draft validate --file draft.json --json
```

校验内容：

1. **文件/输入安全检查**：`--file` 必须在项目根目录内、为安全 `.json` 文件；拒绝 `.env`/credential 类文件；`--stdin` 不落盘。
2. **Envelope 提取**：自动识别直接 envelope 或外层 `envelope_draft`；识别失败返回 `validation_failed`。
3. **Schema 校验**：按 `adapters/execution-envelope.schema.json` 校验内层 envelope。
4. **一致性校验**：复用 `adapter validate` 的跨 artifact 一致性规则（`duplicate-request-id`、引用存在性、`approval-scope-mismatch`、`needs-approval-missing-record`、`approval-requested-event-unknown-approval` 等）。

输出只包含状态、规则 id、简短摘要和 `next_action`；不回显完整 input payload、`evidence`、`raw_ref`、`decision_ref` 或 secret match。

## Runtime Draft 摘要

`runtime draft inspect` 先对 runtime draft 做与 `runtime draft validate` 相同的校验，通过后输出一个紧凑的 draft 摘要，用于快速了解 draft 中 artifact 的分布与状态。

```bash
python -m agent_runtime.cli runtime draft inspect --file draft.json
```

从 stdin：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --draft-json | python -m agent_runtime.cli runtime draft inspect --stdin
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime draft inspect --file draft.json --json
```

JSON 结构：

```json
{
  "status": "pass",
  "summary": {
    "source": "draft.json",
    "task_id": "task-20260703-001",
    "status": "needs_approval",
    "version": 1,
    "description": "...",
    "artifact_counts": {
      "adapter_request": 1,
      "approval_record": 1,
      "execution_event": 1
    },
    "requests": [
      {
        "request_id": "req-...",
        "adapter_id": "github-cli",
        "operation": "git_push",
        "preflight_status": "needs_approval",
        "requires_approval": true,
        "risk_level": "external"
      }
    ],
    "approvals": [
      {
        "approval_id": "appr-...",
        "request_id": "req-...",
        "status": "pending"
      }
    ],
    "responses": [],
    "events": {
      "approval_requested": 1
    },
    "overall": {
      "requires_approval_count": 1,
      "pending_approval_count": 1,
      "response_count": 0,
      "evidence_count": 0
    }
  }
}
```

与 `adapter inspect` 的区别：

- 更强调 "draft"：摘要不包含 `target`，不输出 `input` payload。
- 支持从外层 `envelope_draft` 提取 `task_id` 与 `status`。
- 失败时返回与 `runtime draft validate` 相同的状态/返回码，不输出 `summary`。

行为约束：

- 先执行 schema + consistency 校验；失败不输出 summary。
- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 人类/JSON 输出不回显完整 `input`、`evidence`、`raw_ref`、`decision_ref` 或 secret match。

## Runtime Draft Export Dry-run

`runtime draft export --dry-run` 把已经通过校验的 runtime plan envelope draft 模拟导出到项目内受控路径，**不落盘**。它是 Controlled Write POC 的第一步。

配合 `runtime plan --draft-json` 使用：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --draft-json | \
  python -m agent_runtime.cli runtime draft export \
    --stdin \
    --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
    --dry-run
```

从文件导出：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --dry-run
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --dry-run \
  --json
```

dry-run 通过时的人类输出示例：

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-20260703-001/req-xxx.envelope.json
Would write: false
Validation: pass
Artifact counts: adapter_request=1, approval_record=0, execution_event=0, adapter_response=0
Next: Use --commit to persist the draft (not yet implemented).
```

行为约束：

- 只读：`--dry-run` 不写文件、不覆盖文件；需要持久化时请使用 `--commit`。
- 输出路径必须在项目根目录内、以 `.json` 结尾、不能指向 credential/git internals，且默认禁止覆盖已存在文件。
- 输入 envelope 必须通过 schema + consistency 校验。
- 导出内容会通过 policy secret scan 与 public scan，命中则 block 且不回显完整匹配值。
- JSON/人类输出不回显完整 `target` / `input` / `raw_ref` / `decision_ref` / evidence description。

详细设计见 `docs/22-runtime-draft-export-dry-run.md`。

## Runtime Draft Export Commit

`runtime draft export --commit` 将已通过 dry-run 全部检查的 envelope draft 持久化到 `drafts/runtime/.../*.json`。

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --draft-json | \
  python -m agent_runtime.cli runtime draft export \
    --stdin \
    --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
    --commit
```

约束：

- `--dry-run` 与 `--commit` 互斥，必须显式提供其中一个。
- `--output` 在 `--commit` 模式下必须位于 `drafts/runtime/` 下，后缀 `.json`。
- 不支持 overwrite；目标文件已存在即 blocked。
- 写入后会重新 `runtime draft validate` 与 `runtime draft inspect`；失败时删除半写入文件。
- 不回显完整 `target` / `input` / `raw_ref` / `decision_ref` / evidence description / secret match。

详细设计见 `docs/24-runtime-draft-export-commit.md`。

## Runtime Event Append Dry-run

`runtime event append --dry-run` 在把单个候选 event 真正追加到 `tasks/events.jsonl` 之前，跑通所有入门禁：schema 校验、task 存在性检查、模拟追加后的 ledger consistency、可选的 runtime ledger audit、secret/public scan。

从文件模拟追加：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run
```

从 stdin 模拟追加：

```bash
echo '{"event_id":"evt-20260705-001",...}' | \
  python -m agent_runtime.cli runtime event append --stdin --dry-run
```

指定 ledger 文件与 envelope 做 audit：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

约束：

- `--dry-run` 必须显式提供。
- 不写 `tasks/events.jsonl`、不写 task ledger、不写 envelope。
- 不回显完整 `target` / `input` / `evidence` / `raw_ref` / `decision_ref` / secret match。

详细设计见 `docs/26-runtime-event-append-dry-run.md`。

## Runtime Event Append Commit

`runtime event append --commit` 在复用 dry-run 全部检查后，把单个候选 event 追加到 event ledger JSONL 文件（默认 `tasks/events.jsonl`）。写入后自动运行 `task validate --schema event`、`task check-ledger`，如有 `--envelope` 还会运行 `runtime check-ledger`；若任一写后检查失败，则按原始 byte size 回滚本次追加。

从文件提交：

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit
```

从 stdin 提交：

```bash
echo '{"event_id":"evt-20260705-001",...}' | \
  python -m agent_runtime.cli runtime event append --stdin --commit
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

约束：

- `--dry-run` 与 `--commit` 互斥，必须显式提供其中一个。
- 只追加 exactly one JSON object as last line，不覆盖、不删除、不重排、不格式化历史 ledger。
- 默认目标 `tasks/events.jsonl`；显式 `--events-file` 必须位于项目根目录内、后缀 `.jsonl`、且不是 sample/credential/git internals。
- 现有 events file 非空且没有末尾换行时直接 blocked，不自动修复。
- 写入前检查：候选 JSON object、event schema、`task_id` 存在、event_id 不重复、secret/public scan、模拟 append 后 ledger consistency、可选 runtime ledger audit。
- 写入后检查失败时回滚；回滚成功后返回失败状态并说明已回滚，回滚失败时返回 `error`。
- 不回显完整 `message` / metadata values / artifacts payload / evidence description / `target` / `input` / `raw_ref` / `decision_ref` / secret match。

详细设计见 `docs/28-runtime-event-append-commit.md`。

## Runtime Task Create Dry-run / Commit

`runtime task create --dry-run` 在把单个候选 task snapshot 真正写入 task ledger 之前，跑通所有入门禁：schema 校验、`task.id` 去重、secret/public scan、模拟追加后的 ledger consistency。

`runtime task create --commit` 复用 dry-run 写前门禁，只向 task ledger JSONL 末尾追加一行，写后运行 task schema validation 与 ledger consistency；失败会按写入前 byte size 回滚。它不会自动写 event ledger。

从文件模拟创建：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run
```

从 stdin 模拟创建：

```bash
echo '{"id":"task-20260706-001",...}' | \
  python -m agent_runtime.cli runtime task create --stdin --dry-run
```

指定 ledger 文件：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --dry-run \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl \
  --json
```

提交创建 task snapshot：

```bash
python -m agent_runtime.cli runtime task create \
  --file candidate-task.json \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

通过 orchestration 命名空间提交 task（A+B controlled write）：

```bash
python -m agent_runtime.cli orchestration task submit \
  --file candidate-task.json \
  --dry-run

python -m agent_runtime.cli orchestration task submit \
  --file candidate-task.json \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

`--dry-run` 会完全只读地预览 commit 将执行的两步写入（A=task ledger，B=created event），输出中包含 `would_create=True` 和 `would_append_created_event=True`。

`--commit` 边界：

- A：向 task ledger 追加 exactly one JSON object as the last line。
- B：向 events ledger 追加 exactly one `event_type=created` event，其 `task_id` 指向刚提交的 task，`from_status=null`，`to_status` 等于 task snapshot 的 `status`。
- `--events-file` 在 `--commit` 下必填；缺失时返回 `needs_input`，不写 A/B。
- A 或 B 任一环节失败，或 post-check 失败，task ledger 与 events ledger 都回滚到原始 byte size。
- post-check 针对实际落盘后的 task + events ledger，包括 schema 校验与 `task check-ledger` 跨记录一致性。
- 不自动执行 route / preflight / run / adapter。
- 目标 ledger 必须位于项目根内、后缀为 `.jsonl`、不是样本 ledger、不是 git/credential 路径。
- 父目录必须已存在；现有非空文件必须以换行结尾。
- 输出只包含 task id、event id、状态、计数和检查状态，不回显 title / summary / evidence description / secret match；created event 的 metadata 只放安全摘要。

约束：

- `--dry-run` 与 `--commit` 必须显式二选一。
- `--dry-run` 不写 `tasks/tasks.jsonl`、不写 `tasks/events.jsonl`、不写 envelope。
- `--commit` 原子写 task ledger + created event，不写 envelope、不执行外部动作。
- 不回显完整 title / summary / evidence description / secret match。

详细设计见 `docs/31-runtime-task-create-dry-run.md` 与 `docs/34-release-notes-runtime-task-create-commit.md`。

## Runtime Task Create Smoke / Report Loop

`runtime task create --commit` 只写 task ledger，不自动写 event ledger。完整的端到端 smoke loop 应在**临时项目副本**中先创建 task，再追加 `created` event，最后跑只读校验与聚合报告：

```text
task create dry-run -> task create commit -> event append dry-run -> event append commit -> task validate/check-ledger -> runtime report
```

示例（假设已在临时目录 `$SMOKE` 中准备好 schema、policy、空 ledger、envelope、candidate-task.json、candidate-event.json）：

```bash
# 1. task create dry-run
python -m agent_runtime.cli --root "$SMOKE" runtime task create \
  --file candidate-task.json --dry-run \
  --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl

# 2. task create commit
python -m agent_runtime.cli --root "$SMOKE" runtime task create \
  --file candidate-task.json --commit \
  --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl

# 3. event append dry-run
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate-event.json --dry-run \
  --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl

# 4. event append commit
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate-event.json --commit \
  --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl

# 5. post-commit read-only checks
python -m agent_runtime.cli --root "$SMOKE" task validate \
  --record-file tasks/tasks.jsonl --schema task
python -m agent_runtime.cli --root "$SMOKE" task validate \
  --record-file tasks/events.jsonl --schema event
python -m agent_runtime.cli --root "$SMOKE" task check-ledger \
  --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl

# 6. runtime report
python -m agent_runtime.cli --root "$SMOKE" runtime report \
  --task-id task-20260707-001 --request-id req-20260707-001 \
  --envelope envelope.json --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl
```

约束：

- 不要在仓库真实 `tasks/tasks.jsonl` / `tasks/events.jsonl` 样例 ledger 上直接 `commit`。
- 所有写入应限制在可丢弃的临时目录或显式隔离的 `--tasks-file` / `--events-file` 路径。
- loop 中各命令输出不回显完整 `title` / `summary` / `message` / `target` / `input` / `evidence` / `raw_ref` / `decision_ref` / secret match。

详细步骤与临时目录构造见 `docs/35-runtime-task-create-smoke.md`。

## Controlled Write Regression

受控写入命令（`runtime draft export --commit`、`runtime event append --commit`、`runtime task create --commit`）的完整链路已纳入回归测试。运行聚焦测试：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

该测试在临时项目根中执行：

```text
task create dry-run -> task create commit -> event append dry-run -> event append commit -> task validate -> task check-ledger -> runtime report
```

并断言：

- 受控写入只追加预期单行。
- `runtime report` 不泄露 task title 与 event message。
- 仓库真实 `tasks/tasks.jsonl` 与 `tasks/events.jsonl` 不被修改。

建议 CI 在完整 `pytest` 之外显式跑一次受控写入 smoke test，作为回归保护：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

详细边界与写入点梳理见 `docs/36-controlled-write-regression.md`。


## Runtime Event Import

`runtime event import` 对批量候选 event 做只读预检或受控追加。它分两种模式：`--dry-run` 只读模拟；`--commit` 把整批 event 作为一个连续 JSONL block 追加到现有 event ledger 尾部。

### Dry-run

`--dry-run` 在真正追加前跑通所有入门禁：JSON 语法、object 形状、event schema、secret/public scan、candidate 内部 event_id 去重、与现有 ledger 的 event_id 去重、task_id 存在性、模拟追加后的 ledger consistency。

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

### Commit

`--commit` 会把候选 JSONL 中的 event 追加到 `--events-file` 指定的 ledger。第一版要求目标 ledger 必须已存在；非空 ledger 末尾必须已有换行符；否则 blocked。

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

commit 成功时的人类输出示例：

```text
PASS
Source: candidate-events.jsonl
event_count=3
blank_line_count=0
task_count=2
event_type_counts=created:1,status_changed:2
target_events_file=tasks/events.jsonl
committed=True
appended_line_count=3
post_validate=pass
post_ledger_check=pass
rolled_back=False
Next: Event batch committed successfully.
```

### Consistency Freeze

dry-run 默认输出一致性冻结元数据，用于在 dry-run 与 commit 之间建立“审阅上下文一致性”锚点：

- `candidate_fingerprint`：candidate 文件非空原始行的 sha256。
- `events_ledger_fingerprint`：目标 events ledger 完整原始字节的 sha256。
- `events_ledger_size_bytes`、`events_ledger_line_count`：ledger 大小与行数。
- `plan_hash`：一次 dry-run 完整上下文的 canonical sha256。
- `freeze_mode=advisory`：当前为建议冻结模式，不强制 commit 必须传 hash。

带 `--json` 的 dry-run 示例：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run \
  --json
```

commit 时可通过 `--expected-plan-hash` 绑定某次 dry-run 的 plan hash：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --expected-plan-hash sha256:... \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

如果 dry-run 后 candidate 文件或 events ledger 被改动，commit 会立即返回 `blocked`（`plan-hash-mismatch`），不会进入 preflight 与写入阶段。不提供 `--expected-plan-hash` 时，commit 保持原有行为不变。

### Strict Freeze Mode

如果调用方希望显式声明“本次 commit 必须绑定某次 dry-run 审阅结果”，可使用 `--require-dry-run`：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --require-dry-run \
  --expected-plan-hash sha256:... \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

约束：

- `--require-dry-run` 只能与 `--commit` 一起使用；与 `--dry-run` 同传或单独使用都会报错。
- 使用 `--require-dry-run` 时必须同时提供 `--expected-plan-hash`，否则返回 `error`（`rule_id=missing-expected-plan-hash`）。
- hash 一致时仍继续完整 preflight + append + post-check + rollback；hash 不一致直接 `blocked`。
- 不提供 `--require-dry-run` 时，现有 `--expected-plan-hash` 与 commit 行为保持不变。

### 通用约束

- `--dry-run` 与 `--commit` 互斥；两者都不提供时报错。
- `--expected-plan-hash` / `--require-dry-run` 仅在 `--commit` 时生效。
- 输入文件必须是项目根目录内的安全 `.jsonl` 文件，不能指向 `.git` / credential / secret 路径。
- 批量语义为 all-or-nothing：任意一行失败、post-check 失败或 freeze mismatch，整批不保留。
- 输入顺序即模拟/写入顺序；不自动按 timestamp 排序。
- `--commit` 只追加 event ledger，不写入 task ledger、不写 envelope。
- 不回显完整 `message` / metadata values / artifacts payload / evidence description / `target` / `input` / `raw_ref` / `decision_ref` / secret match；freeze 字段只暴露 hash、size、line count 等安全元数据。

详细设计见 `docs/37-runtime-event-import-dry-run.md`、`docs/39-runtime-event-import-commit-design.md`、`docs/41-runtime-event-import-consistency-freeze.md` 与 `docs/45-runtime-event-import-strict-freeze-mode.md`，阶段收口说明见 `docs/38-release-notes-runtime-event-import-dry-run.md`、`docs/40-release-notes-runtime-event-import-commit.md`、`docs/42-release-notes-runtime-event-import-consistency-freeze.md` 与 `docs/46-release-notes-runtime-event-import-strict-freeze.md`。

## Runtime Event Append Smoke / Report Loop

`runtime event append` 写入 event ledger 后，通常需要再跑一遍只读检查与聚合报告来确认状态。完整的 smoke loop 应在**临时项目副本**中进行：

```text
dry-run -> commit -> task validate/check-ledger -> runtime check-ledger/report
```

示例（假设已在临时目录 `$SMOKE` 中准备好 schema、policy、ledger、envelope、candidate）：

```bash
# 1. dry-run
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate.json --dry-run \
  --tasks-file tasks.jsonl --events-file events.jsonl --envelope envelope.json

# 2. commit
python -m agent_runtime.cli --root "$SMOKE" runtime event append \
  --file candidate.json --commit \
  --tasks-file tasks.jsonl --events-file events.jsonl --envelope envelope.json

# 3. post-commit read-only checks
python -m agent_runtime.cli --root "$SMOKE" task validate \
  --record-file events.jsonl --schema event
python -m agent_runtime.cli --root "$SMOKE" task check-ledger \
  --tasks-file tasks.jsonl --events-file events.jsonl
python -m agent_runtime.cli --root "$SMOKE" runtime check-ledger \
  --tasks-file tasks.jsonl --events-file events.jsonl --envelope envelope.json

# 4. runtime report
python -m agent_runtime.cli --root "$SMOKE" runtime report \
  --task-id task-20260706-001 --request-id req-20260706-001 \
  --envelope envelope.json --tasks-file tasks.jsonl --events-file events.jsonl
```

约束：

- 不要在仓库真实 `tasks/events.jsonl` 样例 ledger 上直接 `commit`。
- 所有写入应限制在可丢弃的临时目录或显式隔离的 `--events-file` 路径。
- loop 中各命令输出不回显完整 `message` / `target` / `input` / `evidence` / `raw_ref` / `decision_ref` / secret match。

详细步骤与临时目录构造见 `docs/30-runtime-event-append-smoke.md`。

## `runtime report`

`runtime report` 把 task snapshot、task event stream 摘要、adapter execution envelope 摘要、runtime gate 状态、runtime ledger audit 状态汇总到一份只读报告中，并给出 blockers 与 next_action 建议。

```bash
python -m agent_runtime.cli runtime report \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json
```

可选参数：

- `--tasks-file <path>`：指定 tasks JSONL 文件（默认 `tasks/tasks.jsonl`）。
- `--events-file <path>`：指定 events JSONL 文件（默认 `tasks/events.jsonl`）。
- `--json`：输出 JSON 聚合报告。

文本输出示例：

```text
PASS
Task: task-20260703-001 (running): title_present=True
Events: 2 events, latest=status_changed at 2026-07-03T10:05:00+08:00
Envelope: adapter_request=1, adapter_response=1, execution_event=1
Gate: stage=response, can_proceed=true
Ledger: pass (tasks=1, events=2, requests=1, execution_events=1)
Blockers: none
Next: Proceed with adapter execution.
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime report \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

行为约束：

- 只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 人类/JSON 输出不回显完整 `target`、`input` payload、`evidence` 描述、`raw_ref` 或 `decision_ref`。
- 终态 task（`finished` / `failed`）会被标记为 BLOCKED，且不能继续推进。

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

## Orchestration Read-Model CLI

Stage 15 第一版新增了一组 `orchestration` 命名空间的只读命令，作为未来看板各页面的最小 read model 雏形。这些命令都不写 ledger、不执行 adapter、不访问网络。

CLI 自动化契约发现（post-Stage 14，只读）：

```bash
python -m agent_runtime.cli orchestration contract inspect
python -m agent_runtime.cli orchestration contract inspect --json
```

JSON 输出使用 `control-plane/orchestration-contract/v1`，确定性列出 `stable`、`stable_limited`、`preview`、`unavailable` 条目、真实 command argv、关键边界 flag 与安全说明。该命令只读取代码内冻结的契约元数据，不读取 ledger 或 adapter registry，不写文件，不访问网络，也不执行 manifest 中的命令。

Requirement Gate（只读，不执行 requirement 对应命令）：

```bash
# stable/stable_limited requirement
python -m agent_runtime.cli orchestration contract check \
  --require task_read \
  --require routing_preflight \
  --json

# preview 默认返回 needs_input；必须显式 opt-in
python -m agent_runtime.cli orchestration contract check \
  --require run_plan \
  --allow-preview \
  --max-access read_only \
  --json
```

- `--require` 可重复；结果按 contract id 去重和排序。
- `--allow-preview` 默认关闭。
- `--max-access` 可选 `read_only` 或 `controlled_write`，默认 `controlled_write`。
- unknown / preview 未授权返回 `needs_input`（退出码 4）；unavailable / access 超限返回 `blocked`（退出码 2）。
- 输出 schema 为 `control-plane/orchestration-contract-check/v1`。

Automation Profile（source-backed，只读）：

```bash
python -m agent_runtime.cli orchestration profile list --json
python -m agent_runtime.cli orchestration profile inspect \
  --profile-id ci-read-only \
  --json
python -m agent_runtime.cli orchestration profile check \
  --profile-id local-dry-run \
  --json
```

- 固定读取 `automation/automation-profiles.sample.json`，不接受任意 profile 文件路径。
- `profile list` 输出紧凑摘要；`inspect` 输出规范化 requirement 集合；`check` 复用 Requirement Gate。
- 内置样例：`ci-read-only`、`local-dry-run`、`local-controlled-write`。
- registry 缺失、非法 JSON/schema 或重复 profile id 返回 `validation_failed`（退出码 5）。
- profile check 只做能力协商，不执行 requirement 对应 command。

Read-only Workflow Plan projection：

```bash
python -m agent_runtime.cli orchestration workflow plan \
  --profile-id local-dry-run \
  --json
```

- 输出 schema 为 `control-plane/automation-workflow-plan/v1`。
- 先复用 profile check；只有 gate 为 `pass` 才生成步骤，否则保持原状态且 `steps=[]`。
- command argv、关键 flag、availability、access 与 boundary 都来自同一 contract manifest。
- 步骤按 discovery / inspect / decide / prepare / controlled_write / observe / capability 排序，并固定标记 `status=planned`、`execution=not_executed`。
- `plan_id` 是规范化安全 projection 的 SHA-256 内容哈希；同一 source/profile 产生相同输出。
- 即使 profile 允许 controlled-write，planner 也只展示带 `--commit` 等显式 flag 的候选，不执行命令、不写文件或 ledger。

Workflow Plan re-check / drift validation：

```bash
python -m agent_runtime.cli orchestration workflow check \
  --profile-id local-dry-run \
  --expected-plan-id sha256:<64-lowercase-hex> \
  --json
```

- expected id 来自之前 `workflow plan --json` 的 `plan_id`。
- id 必须严格匹配 `sha256:[a-f0-9]{64}`；非法格式返回 `needs_input`，并且不会读取 profile registry。
- 当前投影匹配时返回 `pass` / `matches_current=true`；不匹配时返回 `blocked` / `automation-workflow-plan-drift`。
- hash mismatch 只能证明 canonical projection 已变化，不提供伪造的字段级原因；结果内嵌当前完整 plan 供重新审查。
- 输出 schema 为 `control-plane/automation-workflow-check/v1`，仍然不执行 command、不写文件或 ledger。

Stage 16–18 Read-only Control Panel（本地静态、只读、stdio-first）：

```bash
python -m agent_runtime.cli orchestration control-panel snapshot --json
python -m agent_runtime.cli orchestration control-panel snapshot \
  --envelope adapters/execution-envelope.examples.json \
  --json
python -m agent_runtime.cli orchestration control-panel render \
  --envelope adapters/execution-envelope.examples.json \
  > control-panel.html
python -m agent_runtime.cli orchestration control-panel handoff --json
python -m agent_runtime.cli orchestration control-panel handoff \
  --envelope adapters/execution-envelope.examples.json \
  --json
```

- `snapshot` 输出 `control-plane/control-panel-snapshot/v1` 与确定性 `snapshot_id`。
- `render` 只向 stdout 输出自包含 HTML；CLI 自身不创建文件、不启动 service。
- `handoff` 输出 `control-plane/control-panel-handoff/v1`，声明 JSON/HTML representation、media type、encoding、renderer version、`snapshot_id`、`render_id`、`working_directory=project_root` 与 argv 数组。
- `render_id` 只由 `{snapshot_id, renderer_version}` 的 canonical JSON 决定；`handoff_id` 对不含自身的 descriptor 做 canonical SHA-256。
- `handoff` 不内嵌 HTML、不执行 argv、不打开浏览器；项目内绝对 envelope 路径会归一化为 root-relative 表示。
- 不传 `--envelope` 时，runs/approvals/artifacts 显示 `envelope_required`；reports 保持 `request_context_required`，不会伪造持久 collection。
- HTML 无外部资源与网络请求，所有 read-model 字符串都会转义；只提供本地过滤，不提供 commit、approval resolve 或执行按钮。

Stage 18 独立 reference consumer：

```bash
python -m agent_runtime.cli orchestration control-panel handoff --json | \
  python tools/control_panel_handoff_consumer.py
python -m agent_runtime.cli orchestration control-panel handoff \
  --envelope adapters/execution-envelope.examples.json \
  --json | python tools/control_panel_handoff_consumer.py
```

- consumer 只从 stdin 读取一份 UTF-8 JSON，最大 1 MiB；拒绝空输入、超限、非 UTF-8、非法 JSON 和重复 object key。
- 输出 schema 固定为 `control-plane/control-panel-host-consumer-validation/v1`，consumer id 固定为 `local-reference-consumer/v1`。
- 固定检查 schema、producer status、handoff/render identity、representation metadata、argv shape 与只读 boundary。
- `pass`/`blocked`/`validation_failed`/`error` 分别使用退出码 `0`/`2`/`5`/`1`。
- consumer 不导入 producer 实现，不读取 snapshot/HTML representation，不执行 argv，不访问网络，不写文件或 ledger。

Stage 20 Codex Desktop one-shot read-only adapter：

```bash
python tools/codex_desktop_read_only_adapter.py \
  --project-root . \
  --timeout-seconds 30 \
  --json
```

- adapter 只执行固定 handoff producer 和 `tools/control_panel_handoff_consumer.py`，不执行 descriptor 中的 `snapshot.argv` / `render.argv`。
- 输出 schema 固定为 `control-plane/codex-desktop-read-only-adapter/v1`；状态为 `ready` / `blocked` / `validation_failed` / `error`，退出码为 `0` / `2` / `5` / `1`。
- 每次调用只消费一轮 producer → consumer；默认每个子进程 30 秒，最大 60 秒，不自动重试；stdout 上限 1 MiB。
- `ready` 只表示 handoff validation 通过，不表示 snapshot/HTML representation 已读取；不启动 service、不访问网络、不写文件、ledger、draft 或 artifact。
- project root 必须包含 `pyproject.toml` 与 `agent_runtime/`；公开结果只输出 `project_root` 安全摘要，不回显绝对路径、stderr、descriptor 或 argv。

Stage 21 representation read design gate 已冻结为 validation-only；Stage 22 在该边界内新增了显式 snapshot JSON reader：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --timeout-seconds 30 \
  --json
```

说明：

- `--representation snapshot-json` 必须显式提供；没有默认 representation；
- 固定执行 handoff producer → reference consumer → snapshot producer；
- 不执行 descriptor 中的 argv；
- 未提供 envelope 时输出 `control-plane/codex-desktop-snapshot-read/v1`；
- `ready` 前校验 snapshot schema、source、guarantees、handoff identity 与 canonical hash；
- v1 不读取 HTML，不打开浏览器，不写文件，不访问网络，不启动 service，不执行真实 adapter。

Stage 24 新增显式 envelope-scoped v2：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --timeout-seconds 30 \
  --json
```

scoped mode 规则：

- 输出 `control-plane/codex-desktop-snapshot-read/v2` / `codex-desktop-envelope-snapshot-json-reader/v2`；
- 只接受 `adapters/*.json` 与 `drafts/runtime/**/*.envelope.json` project-relative allowlist；
- 拒绝绝对路径、drive/UNC、`..`、非 canonical path、root 外 symlink 和 arbitrary JSON；
- 读取前执行 1 MiB、strict UTF-8、duplicate-key、schema/consistency 与 secret scan；
- 输出 `relative_envelope`、`envelope_content_id`、`scope_id`，不输出 absolute root、raw envelope、`input`、payload refs 或 raw refs；
- snapshot 返回后再次校验 envelope content id，拒绝 one-shot 生命周期内的内容漂移。

Stage 27 filtered v3：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --task-id task-20260703-001 \
  --json

python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json
```

filtered mode 规则：

- `--task-id` / `--request-id` 至少一个，可同时提供并使用 AND；每个 flag 只能出现一次；
- filter 必须与显式 envelope 同时使用，并使用 canonical ASCII exact id；
- filter 只作用于完整验证后的 runs/approvals/artifacts 安全 summaries；
- task filter 通过 request→task 关系闭包包含缺少直接 task_id 的 response artifact；
- 合法无匹配返回 `ready` 空视图与 `matched=false`，不猜测或降级；
- 输出 `control-plane/codex-desktop-snapshot-read/v3`，包含独立 filtered payload、filter id、base snapshot id 与 view id；
- filter 不传给 handoff/consumer/snapshot child argv；仍不提供 `--filter`、`--query`、排序、分页、缓存或 export；
- 无 filter 的 envelope-scoped 调用保持 v2；无 envelope、无 filter 保持 v1。

Stage 29 filtered snapshot consumer：

```bash
python tools/codex_desktop_snapshot_json_reader.py \
  --project-root . \
  --representation snapshot-json \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --json \
| python tools/codex_desktop_filtered_snapshot_consumer.py
```

consumer 规则：

- 只从 stdin 消费一份完整 filtered v3 reader result，不接受文件、URL、payload-only 或 v1/v2；
- 最大输入 1 MiB，strict UTF-8，拒绝 duplicate key；最大输出 64 KiB；
- 验证 ready lifecycle、guarantees、scope/filter/view identity、safe sections 与 filter semantics；
- 输出只保留 base/scope/filter/view ids、checks、value-safe findings、guarantees 与 next action；
- consumer 不自动启动 reader，不执行 argv/command/adapter，不读写文件、不访问网络；
- `pass` 只表示输入符合只读展示 contract，不是 execution permission。


Stage 31 filtered snapshot one-shot host：

```bash
python tools/codex_desktop_filtered_snapshot_host.py \
  --project-root . \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --timeout-seconds 30 \
  --json
```

host 规则：

- `--task-id` / `--request-id` 至少一个，可同时提供并使用 AND；
- host 只启动固定 filtered v3 reader，再把完整 stdout 通过 stdin 交给固定 Stage 29 consumer；
- 只有 consumer `pass` / exit 0 且 base/scope/filter/view identity 交叉核对成功后，才返回 filtered payload；
- failure 时 `representation.payload` 固定为 `null`，不回显未验证 input、absolute root、relative envelope 或 stderr；
- 默认每个固定子进程 30 秒、最大 60 秒，不 retry；reader/host stdout 最大 1 MiB，consumer stdout 与 child stderr 最大 64 KiB；
- 输出 schema 为 `control-plane/codex-desktop-filtered-snapshot-host/v1`；状态/退出码为 `ready/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- 该工具只提供本地 one-shot JSON host contract，不是 Codex Desktop 专有插件或 UI；不写文件/ledger、不访问网络、不启动 service、不执行 descriptor argv、candidate command 或 adapter。

Stage 34 filtered snapshot Markdown display：

```bash
python tools/codex_desktop_filtered_snapshot_display.py \
  --project-root . \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --representation markdown \
  --timeout-seconds 30 \
  --json
```

display 规则：

- 只启动固定 Stage 31 host，不直接启动 reader/consumer，不接受 arbitrary stdin/file/URL；
- 只有 host `ready/0` 且 shape、lifecycle、guarantees、identity、safe rows、counts/matched/filter semantics 全部通过后才生成 content；
- 动态值以 escaped ASCII JSON inline literal 投影到固定 Markdown 模板；不输出 raw HTML、图片、链接或输入 Markdown；
- 顺序固定为 overview/filter/identity、runs、approvals、artifacts、reports；合法空视图显示固定 no-match 文案；
- `content_id` 是 Markdown UTF-8 bytes 的 SHA-256；最终 JSON 最大 64 KiB，超限 fail closed；
- host 非 ready 时 `content/content_id=null`；状态/退出码保持 `ready/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- one-shot、no retry、no write、no network、no service、no cache/export、no adapter execution。

Stage 37 filtered snapshot Markdown display consumer：

```bash
python tools/codex_desktop_filtered_snapshot_display.py \
  --project-root . \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --representation markdown \
  --json \
| python tools/codex_desktop_filtered_snapshot_display_consumer.py
```

consumer 规则：

- 只从 stdin 读取一份完整 display v1 JSON，最大 64 KiB；不接受参数、file、path、URL、payload-only 或 raw Markdown；
- strict UTF-8、duplicate-key、exact wrapper/status/lifecycle/guarantees gate；
- ready 时独立重算 Markdown UTF-8 content SHA-256，并验证固定 section/row grammar、安全 ASCII JSON inline literal、identity/count/filter/empty-view/report coherence；
- non-ready 只验证 withheld contract；输出不包含 content、absolute path、envelope、host payload 或上游 finding message；
- 输出 schema 为 `control-plane/filtered-snapshot-markdown-display-consumer-validation/v1`；状态/退出码为 `pass/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- 标准库-only、one-shot、no process launch、no write、no network、no service、no persistence/export、no adapter execution。

Stage 40 validated Markdown display host：

```bash
python tools/codex_desktop_filtered_snapshot_display_host.py \
  --project-root . \
  --envelope adapters/execution-envelope.examples.json \
  --request-id req-20260703-001 \
  --representation markdown \
  --timeout-seconds 30 \
  --json
```

host 规则：

- 只启动 fixed Stage 34 display，再把 complete stdout exact bytes 交给 fixed Stage 37 consumer stdin；
- display `ready/0`、consumer `pass/0`、10 项 checks 与 base/scope/filter/view/content 五项 identity 全部一致后才释放 Markdown content；
- non-ready、protocol/identity/size/timeout/cancel failure 一律 `content=null`；
- child stdout/consumer stdin 64 KiB、child stderr 64 KiB、final JSON 128 KiB，默认每 child 30 秒、最大 60 秒、no retry；
- 输出 schema 为 `control-plane/codex-desktop-filtered-snapshot-display-host/v1`；状态/退出码为 `ready/0`、`error/1`、`blocked/2`、`validation_failed/5`；
- 不重新解析 Markdown，不输出 child message/stderr/argv/path/envelope，不写入、不访问网络、不启动 service、不持久化/export、不执行 adapter。

总览聚合：

```bash
python -m agent_runtime.cli orchestration overview
python -m agent_runtime.cli orchestration overview --json
```

Adapter Capability Registry（Stage 10 source-backed registry 投影，只读）：

```bash
python -m agent_runtime.cli orchestration adapter list
python -m agent_runtime.cli orchestration adapter list --json
python -m agent_runtime.cli orchestration adapter list --type tool
python -m agent_runtime.cli orchestration adapter list --risk local
python -m agent_runtime.cli orchestration adapter list --capability local_command
python -m agent_runtime.cli orchestration adapter inspect shell-local
python -m agent_runtime.cli orchestration adapter inspect shell-local --json
```

说明：

- 这是 Stage 10 Adapter Runtime Interface 的 source-backed read model，从 `adapters/adapters.sample.json` 投影，返回 `adapter_id`、`display_name`、`adapter_type`、`capabilities`、`risk_level`、`enabled`、`supports_*`、`timeout_profile`、`input_schema_ref`、`output_schema_ref` 等结构化元数据。
- 只读、确定性、不执行真实 adapter、不访问网络、不写 ledger。
- `input_schema_ref` / `output_schema_ref` 是指向该 entry 内嵌 schema 的真实 JSON Pointer（如 `adapters/adapters.sample.json#/adapters/4/input_schema`）。
- 不过滤 disabled entries，与 `loader.load_adapters` 同批条目语义一致。

任务页：

```bash
python -m agent_runtime.cli orchestration task list
python -m agent_runtime.cli orchestration task list --status running --json
python -m agent_runtime.cli orchestration task get --task-id task-20260703-001
python -m agent_runtime.cli orchestration task get --task-id task-20260703-001 --json
```

执行页（envelope-scoped）：

```bash
python -m agent_runtime.cli orchestration run list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration run list --envelope adapters/execution-envelope.examples.json --task-id task-20260703-001 --json
python -m agent_runtime.cli orchestration run inspect --task-id task-20260703-001 --request-id req-20260703-002 --envelope adapters/execution-envelope.examples.json
```

审批页（envelope-scoped）：

```bash
python -m agent_runtime.cli orchestration approval list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration approval list --envelope adapters/execution-envelope.examples.json --status pending --json
python -m agent_runtime.cli orchestration approval get --approval-id appr-20260703-001 --envelope adapters/execution-envelope.examples.json
```

产物页（envelope-scoped）：

```bash
python -m agent_runtime.cli orchestration artifact list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration artifact list --envelope adapters/execution-envelope.examples.json --type adapter_request --json
python -m agent_runtime.cli orchestration artifact get --artifact-id req-20260703-001 --envelope adapters/execution-envelope.examples.json
```

报告页（runtime-report-backed）：

```bash
python -m agent_runtime.cli orchestration report generate \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --envelope adapters/execution-envelope.examples.json
```

Run lineage 在 read model 中的呈现（Stage 15.99）：

```bash
# retry/fallback commit 后，inspect / list / report 会 compact 展示 lineage
python -m agent_runtime.cli orchestration run inspect \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json

# 显式聚合同一 task 下与该 request 相连的 retry/fallback recovery chain
python -m agent_runtime.cli orchestration run inspect \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json \
  --events-file tasks/events.jsonl \
  --aggregate-lineage --json

python -m agent_runtime.cli orchestration run list \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json

python -m agent_runtime.cli orchestration report generate \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json \
  --events-file tasks/events.jsonl \
  --aggregate-lineage --json
```

`--aggregate-lineage` 只读取现有 run lifecycle events，输出 root/latest/leaves、attempt count、effective plan hash 与安全 request summaries。多 leaf 返回 `needs_input`，缺失 parent、跨 task parent、cycle 或重复 metadata 冲突返回 `validation_failed`。默认不传时 `run inspect` / `report generate` 输出保持不变；该模式不扫描 drafts、不写 ledger、不执行 adapter。`run list` 仍保持 envelope-scoped，暂不隐式查询 event ledger。

Stage 14 replay projection（显式只读预览）：

```bash
python -m agent_runtime.cli orchestration run inspect \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json \
  --replay --json

python -m agent_runtime.cli orchestration report generate \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --envelope drafts/runtime/task-20260703-001/req-20260703-002.envelope.json \
  --replay --json
```

`--replay` 复用同一份 runtime report，输出 `control-plane/orchestration-replay/v1`，包含 task/request、紧凑 state 和结构化 `next_action.code`。默认不传时两个入口输出严格保持原契约；该 projection 不写 ledger、不创建对象、不执行 adapter。

说明：

- 当 envelope 的 `adapter_request.context` 包含 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to` 时，上述 read model 会在 JSON / human 输出中展示；普通 run 不强制输出空字段，保持兼容。
- 输出仍不回显完整 `target`/`input`/`raw_ref`/`decision_ref`/`payload_refs`/evidence descriptions。

Routing handoff 预览（只读）：

```bash
python -m agent_runtime.cli orchestration route preview --capability git_push
python -m agent_runtime.cli orchestration route preview --capability git_push --json
python -m agent_runtime.cli orchestration route preview \
  --task-id task-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --mode dry-run
python -m agent_runtime.cli orchestration route preview --capability light_coding --preferred-adapter kimi-code-acp
python -m agent_runtime.cli orchestration route preview --capability git_push --max-risk local
python -m agent_runtime.cli orchestration route preview --capability light_coding --explain --json
```

说明：`orchestration route preview` 现在直接消费 Stage 10 source-backed adapter registry 投影作为候选集，不再依赖独立内置 registry。第一版支持 `--preferred-adapter`、`--max-risk`、`--require-background`、`--require-artifacts` 约束过滤与偏好排序。追加 `--explain` 可在默认输出不变的前提下，额外输出结构化的 `decision_trace`（matched / rejected / eligible / selected / fallback），为 Stage 12 状态模型提供可消费的路由解释。

Preflight handoff 聚合（只读）：

```bash
python -m agent_runtime.cli orchestration preflight --capability git_push --json
python -m agent_runtime.cli orchestration preflight \
  --task-id task-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --mode dry-run
python -m agent_runtime.cli orchestration preflight --capability light_coding --require-background --preferred-adapter kimi-code-acp
python -m agent_runtime.cli orchestration preflight --capability light_coding --max-risk local --explain --json
```

说明：`orchestration preflight` 现在同样消费该 source-backed registry 投影，并在投影元数据之上叠加 guardrail 判断。路由约束标志同样生效；preflight 将 routing decision passthrough 到 guardrail，不越界替 guardrail 做阻断判断。`--explain` 会让 preflight 复用 route 的 `decision_trace`，不做二次计算。

Routing decision snapshot（只读，不写 ledger，不生成持久 Run）：

```bash
python -m agent_runtime.cli orchestration route snapshot --capability light_coding --json
python -m agent_runtime.cli orchestration route snapshot \
  --capability light_coding \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --explain --json
python -m agent_runtime.cli orchestration preflight \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --mode dry-run \
  --snapshot --json
```

说明：`route snapshot` 与 `preflight --snapshot` 把 routing/preflight 决策投影为 `RoutingDecisionSnapshot` 控制面状态对象。`snapshot_id` 由内容哈希确定性生成，无时间戳；默认不持久化、不写 ledger；preflight snapshot 额外包含分层的 guardrail 摘要（仅规则 id 与计数）。

Run dry-run preview（只读，不写 ledger/envelope/draft）：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run

python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run \
  --json
```

带 routing snapshot 引用的 dry-run preview（Stage 12 → Run Preview 安全引用第一拍）：

```bash
SNAPSHOT_ID=$(python -m agent_runtime.cli orchestration route snapshot \
  --capability git_push \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --json | python -c "import sys,json; print(json.load(sys.stdin)['snapshot_id'])")

python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run \
  --routing-snapshot-id "$SNAPSHOT_ID" \
  --json
```

说明：

- 聚合 `orchestration route preview` + `orchestration preflight` + `runtime plan` 的安全摘要，输出候选 envelope/events/artifact/evidence refs 与 `plan_hash`。
- `--routing-snapshot-id` 只接受 `sha256:<64 lowercase hex>` 格式；非法值返回 `needs_input`，绝不读取任意路径或把 JSON 当参数；命中非法值时输出不会回显原始输入。
- 传入的 snapshot id 会进入 `RunDryRunResult`、candidate artifact refs、`run_planned` candidate event metadata 与 `plan_hash` canonical payload，使相同输入的 plan hash 随 snapshot id 变化；默认不传时旧输出与旧 plan hash 保持兼容。
- `--commit` 模式下传入 `--routing-snapshot-id` 会被明确拒绝（`blocked`），本拍仅 `--dry-run` preview 支持该引用。
- 不校验 snapshot 是否存在于磁盘；它是 content-addressed reference contract，不是持久化产物。
- 不回显完整 input payload、target 原文、`raw_ref`、`decision_ref`、evidence descriptions。

Run dry-run read-loop snapshot preview（只读，不写 ledger/envelope/draft/Run/Event/Report）：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run \
  --snapshot \
  --json
```

说明：

- `--snapshot` 基于真实 `RunDryRunResult` 一次性投影 `OrchestrationReadLoopSnapshot`，包含 Run Preview、candidate Event summaries 与 Report Preview。
- snapshot `snapshot_id` 由最终安全 payload 的 canonical SHA-256 哈希确定性生成，无时间戳；相同输入重复运行产生 byte-equivalent JSON。
- `events` 层只输出 `event_type`、`status=planned`、`metadata_keys`，不伪造 `event_id` 或 `timestamp`。
- `report` 层 `status=preview`，输出 candidate event/artifact/evidence 计数与类型分布、`requires_approval`、`next_action`、结构化 `next_action_code`、仅 rule_ids 的 finding 摘要；无持久 `report_id`。
- `--commit` 模式下传入 `--snapshot` 会被明确拒绝（`blocked`），本拍仅 `--dry-run` preview 支持。
- 不回显完整 input/output schema、原始 target、policy 原文、finding message 或凭据。

Run retry / fallback dry-run preview（只读，不写 ledger/envelope/draft）：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --capability git_push \
  --operation git_push \
  --target origin/main \
  --retry-of req-20260703-001 \
  --dry-run

python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-003 \
  --capability git_push \
  --operation git_push \
  --target origin/main \
  --fallback-from req-20260703-001 \
  --fallback-to shell-local \
  --dry-run \
  --json
```

说明：

- `--retry-of` 与 `--fallback-from` 不能同时使用；`--fallback-to` 必须与 `--fallback-from` 一起使用。
- retry / fallback 会生成新的 `request_id`，重新执行 route / preflight / dry-run，不自动复用旧 `plan_hash` 或 approval。
- 输出包含 `lineage_type`、`retry_of` / `fallback_from` / `fallback_to`，`plan_hash` 会随 lineage 字段变化，避免与普通 dry-run 误用同一 hash。
- retry / fallback dry-run 与 commit 都已支持；commit 时 source request 必须已在同一 task 下存在 envelope draft 或 lifecycle event 证据。

Run commit（受控写入，A+B：envelope draft export + lifecycle events append）：

```bash
# 1. 先 dry-run 拿到 plan_hash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run \
  --json

# 2. 再用匹配的 plan_hash commit（沉淀 envelope draft + run lifecycle events，不执行 adapter）
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --commit \
  --expected-plan-hash sha256:... \
  --output drafts/runtime/task-20260703-001/req-20260703-001.envelope.json \
  --events-file tasks/events.jsonl

# retry commit：source request 必须已存在
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --retry-of req-20260703-001 \
  --commit \
  --expected-plan-hash sha256:... \
  --output drafts/runtime/task-20260703-001/req-20260703-002.envelope.json \
  --events-file tasks/events.jsonl

# fallback commit：切换到 fallback adapter
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-003 \
  --capability git_push \
  --operation git_push \
  --target origin/main \
  --fallback-from req-20260703-001 \
  --fallback-to shell-local \
  --commit \
  --expected-plan-hash sha256:... \
  --output drafts/runtime/task-20260703-001/req-20260703-003.envelope.json \
  --events-file tasks/events.jsonl
```

说明：

- `--commit` 必须提供 `--expected-plan-hash` 与 `--events-file`；会重新 dry-run 并校验 hash，mismatch 返回 `blocked`，不写 A/B。
- `--output` 必须位于 `drafts/runtime/` 下、为 `.json`、不覆盖已存在文件；写入后做 schema/inspect post-check，失败删除新文件并回滚 event ledger。
- 成功路径追加 `run_planned` + `run_draft_exported` 两条 lifecycle events；若 B 失败，A 生成的 envelope draft 删除，event ledger 按原始 byte size truncate 回滚。
- retry / fallback commit 要求 source request 在同一 task 下已有 envelope draft 或 lifecycle event 证据，否则返回 `validation_failed`，不写 A/B；lineage 字段写入 envelope adapter_request context 与 lifecycle event metadata。
- 若 preflight `needs_approval`/`blocked`/`needs_input`/`error`，均不写 A/B。
- 不执行真实 adapter、不访问网络、不发送消息。

审批决议（受控写入，追加 event ledger）：

```bash
# dry-run：只生成 event preview，不写 ledger
python -m agent_runtime.cli orchestration approval resolve \
  --approval-id appr-20260703-001 \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --decision granted \
  --reason "reviewed, safe to proceed" \
  --envelope drafts/runtime/task-20260703-001/req-20260703-001.envelope.json \
  --events-file tasks/events.jsonl \
  --dry-run

# commit：追加一条 approval_resolved event，写后校验，失败回滚
python -m agent_runtime.cli orchestration approval resolve \
  --approval-id appr-20260703-001 \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --decision granted \
  --reason "reviewed, safe to proceed" \
  --envelope drafts/runtime/task-20260703-001/req-20260703-001.envelope.json \
  --events-file tasks/events.jsonl \
  --commit
```

边界说明：

- `orchestration run/approval/artifact list|get` 当前都是 envelope-scoped read model，没有独立 Run / Approval / Artifact 持久集合。
- `orchestration report generate` 是对 `runtime report` 的薄包装，每次实时聚合，不沉淀为独立 Report 集合；`report list` / `report get` 尚未实现。
- `orchestration approval resolve` 与 `orchestration run --commit` 是当前 orchestration 命名空间中的受控写入命令：
  - `approval resolve` 只追加 `approval_resolved` event，不修改输入 envelope，不直接执行原请求。
  - `run --commit` 沉淀 envelope draft 文件并追加 `run_planned` + `run_draft_exported` lifecycle events，不执行真实 adapter。
  - 两者都需显式 `--commit`、写前/写后校验、失败回滚；granted 后仍需重新发起 preflight/run。
- 所有命令都支持 `--json`，人类输出保持紧凑并脱敏。

## 当前安全边界

- 不执行外部命令。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 受控写入命令仅限 `orchestration approval resolve --commit` 与 `orchestration run --commit`：两者都遵循 `--dry-run | --commit` 显式模式、写前/写后校验、失败回滚；`run --commit` 沉淀 envelope draft 文件并追加 run lifecycle events。
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
- `tasks/tasks.jsonl` 目前只支持 CLI 查询；`tasks/events.jsonl` 可通过 `runtime event append --commit`、`runtime event import --commit`、`orchestration approval resolve --commit` 和 `orchestration run --commit` 受控追加，但必须有显式 `--commit`、写后校验与失败回滚；`orchestration run --commit` 追加 `run_planned` + `run_draft_exported` lifecycle events。
- 还没有后台服务。
- 还没有插件系统或真实 adapter 执行。

## 阶段性结论

到这一版为止，项目已经从纯文档推进到一个可运行、可测试、可审查的只读 POC。

这可以作为后续 Runtime 实现的第一块稳定地基：先验证规则、schema、registry 和 CLI 边界，再逐步扩展真实执行能力。
