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
  - `needs-approval-missing-record`：`requires_approval` 且 `preflight.status == "needs_approval"` 的请求必须有 pending/granted 的 `approval_record`。
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
