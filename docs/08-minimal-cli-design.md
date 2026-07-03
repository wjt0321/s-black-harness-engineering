# 08 — 最小 CLI 设计

## 这份文档解决什么问题

前面已经定义了：

- Policy Schema
- Task State Model
- Agent Registry
- Adapter Layer
- Policy 与 Task 状态衔接

下一步不是马上写完整 Runtime，而是先定义最小 CLI 的命令边界。

CLI 的目标，是让这些 schema 和样例能以最小方式被检查、查看和串起来，为后续实现提供稳定入口。

## 设计原则

1. **先 check，不执行**
   第一版 CLI 优先做检查和查询，不直接执行高风险动作。

2. **输出可读，也可机器读**
   默认输出人类可读摘要；支持 `--json` 输出机器可读结果。

3. **所有高风险动作只生成判断，不自动执行**
   例如 GitHub push、飞书发送、删除文件，第一版只做 preflight 判断。

4. **不启动后台服务**
   CLI 是短命令，不常驻。

5. **不接管现有工具链**
   只读取本项目内 schema、sample 和未来 runtime 数据文件。

## 命令总览

第一版建议命令：

```text
agent-runtime check action
agent-runtime check text
agent-runtime check path
agent-runtime task status
agent-runtime task events
agent-runtime agents list
agent-runtime adapters list
agent-runtime policies list
agent-runtime doctor
```

## 全局参数

| 参数 | 说明 |
|:---|:---|
| `--root <path>` | 指定项目根目录，默认当前目录 |
| `--json` | 输出 JSON |
| `--no-color` | 禁用彩色输出 |
| `--quiet` | 只输出必要结果 |
| `--verbose` | 输出更多诊断信息 |

## agent-runtime check action

### 用途

检查一个即将执行的动作是否会被 policy 阻断，或是否需要用户授权、密钥扫描、postflight。

### 示例

```bash
agent-runtime check action --adapter github-cli --operation git_push --target origin/main
```

### 输入字段

| 字段 | 说明 |
|:---|:---|
| `--adapter` | Adapter id，例如 `github-cli` |
| `--operation` | 操作名，例如 `git_push` |
| `--target` | 目标，例如 repo、路径、会话、分支 |
| `--payload-file` | 待检查正文或参数文件 |
| `--risk-level` | 可选，覆盖 adapter 默认风险级别 |

### 输出示例

```text
BLOCKED
Rule: git-push
Action: require_user_approval
Reason: GitHub push requires user approval and secret scan.
Next: Ask for approval, then run secret scan.
```

JSON 输出：

```json
{
  "status": "needs_approval",
  "findings": [
    {
      "rule_id": "git-push",
      "severity": "block",
      "action": "require_user_approval",
      "message": "GitHub push requires user approval and secret scan."
    }
  ],
  "next_action": "Ask for approval, then run secret scan."
}
```

## agent-runtime check text

### 用途

对文本或文件做密钥扫描。

### 示例

```bash
agent-runtime check text --file BODY.md
agent-runtime check text --stdin
```

### 规则

- 默认不回显命中的完整密钥。
- 输出命中的 pattern id 和位置摘要。
- 对 GitHub 发文、飞书发送、邮件发送等外发内容必须使用。

### 输出示例

```text
BLOCKED
- github-token: potential secret detected; redact before publishing.
```

## agent-runtime check path

### 用途

检查路径是否触碰只读区、放错目录或违反路径归属规则。

### 示例

```bash
agent-runtime check path ./image-output/report.md
agent-runtime check path ./workspace/review-area --write
```

### 参数

| 参数 | 说明 |
|:---|:---|
| `--write` | 检查写入动作 |
| `--read` | 检查读取动作 |
| `--delete` | 检查删除动作 |

### 输出示例

```text
BLOCKED
Rule: readonly-path
Reason: Target path is read-only under current policy.
```

## agent-runtime task status

### 用途

查看任务当前快照。

### 示例

```bash
agent-runtime task status task-20260703-001
```

### 输出示例

```text
Task: task-20260703-001
Title: Design adapter layer
Status: finished
Assignee: orchestrator
Artifacts:
- docs/06-adapter-layer.md
Evidence:
- adapter schema validated
```

## agent-runtime task events

### 用途

查看任务事件流。

### 示例

```bash
agent-runtime task events task-20260703-001
```

### 输出示例

```text
2026-07-03T10:00:00+08:00 created
2026-07-03T10:05:00+08:00 status_changed planned -> running
2026-07-03T10:30:00+08:00 evidence_added
2026-07-03T10:40:00+08:00 finished
```

## agent-runtime agents list

### 用途

列出 Agent Registry 中的 Agent。

### 示例

```bash
agent-runtime agents list
agent-runtime agents list --capability light_coding
```

### 输出示例

```text
orchestrator  enabled  planning, quality_review, policy_guardrail
kimi-code     enabled  web_search, light_coding, vision
media-agent   enabled  content_creation, media_generation
```

## agent-runtime adapters list

### 用途

列出 Adapter Registry 中的适配器。

### 示例

```bash
agent-runtime adapters list
agent-runtime adapters list --kind github
agent-runtime adapters list --risk external
```

### 输出示例

```text
github-cli       github      external    approval required
shell-local      shell       local       no default approval
webbridge        webbridge   external    no default approval
```

## agent-runtime policies list

### 用途

列出当前可用 policy 文件和规则数量。

### 示例

```bash
agent-runtime policies list
```

### 输出示例

```text
policies/s-black.sample.policy.json     path=4 secret=5 command=5 publish=2 completion=1
policies/wangcai.sample.policy.json     path=4 secret=4 command=3 publish=2 completion=1
policies/dabai.sample.policy.json       path=4 secret=4 command=3 publish=1 completion=1
```

## agent-runtime doctor

### 用途

检查项目结构、JSON 语法和样例数据是否有效。

### 检查项

- 必要目录是否存在。
- README 是否存在。
- schema JSON 是否有效。
- sample JSON 是否有效。
- sample JSONL 是否逐行合法。
- sample 是否能通过对应 schema。
- 是否存在明显的公开发布风险文本或密钥模式。

### 输出示例

```text
OK docs
OK policies/policy.schema.json
OK policies/*.sample.policy.json
OK agents/agents.sample.json
OK adapters/adapters.sample.json
OK tasks/*.jsonl
PASS public scan
```

## 最小文件读取约定

第一版 CLI 默认读取：

| 文件 | 用途 |
|:---|:---|
| `policies/policy.schema.json` | policy schema |
| `policies/*.sample.policy.json` | policy 样例或本地 policy |
| `agents/agents.schema.json` | agent registry schema |
| `agents/agents.sample.json` | agent registry 样例 |
| `adapters/adapter.schema.json` | adapter schema |
| `adapters/adapters.sample.json` | adapter registry 样例 |
| `tasks/*.jsonl` | 任务和事件样例 |

后续真实运行时可以把 sample 文件替换为：

- `policies/local.policy.json`
- `agents/local.agents.json`
- `adapters/local.adapters.json`
- `tasks/tasks.jsonl`
- `tasks/events.jsonl`

## 返回码约定

| 返回码 | 含义 |
|:---|:---|
| `0` | 通过或查询成功 |
| `1` | CLI 使用错误或内部错误 |
| `2` | policy 阻断 |
| `3` | 需要用户授权 |
| `4` | 需要更多输入 |
| `5` | 校验失败 |

## 输出状态约定

| 状态 | 含义 |
|:---|:---|
| `PASS` | 可以继续 |
| `WARN` | 有提醒但不阻断 |
| `BLOCKED` | 被规则阻断 |
| `NEEDS_APPROVAL` | 需要用户授权 |
| `NEEDS_INPUT` | 需要补充输入 |
| `ERROR` | CLI 或 checker 自身失败 |

## 与未来实现的关系

第一版 CLI 可以只实现只读检查：

- 不执行 Adapter。
- 不写真实 task ledger。
- 不修改外部系统。
- 不删除文件。
- 不发送消息。

等 schema 和流程稳定后，再逐步实现：

1. `doctor`
2. `check text`
3. `check path`
4. `agents list`
5. `adapters list`
6. `policies list`
7. `check action`
8. `task status`
9. `task events`

## 实现与验收分工

当进入真实 CLI 实现时，编码者可以根据本设计直接实现 POC；实现过程不需要重新解释项目背景。

实现者应优先保持第一版 CLI 的只读属性：

- 检查代码是否只读优先。
- 检查危险动作是否没有被实现为自动执行。
- 跑 `doctor`、JSON 校验和样例命令。
- 审查关键逻辑和错误处理。

最终合入前仍需要 Orchestrator 做验收，确认实现符合 policy、task、adapter 三层边界。

## 第一版落地范围

Stage 5 前置设计交付物：

1. `docs/08-minimal-cli-design.md`：最小 CLI 命令边界设计。

后续可交给编码 Agent 实现：

- `agent_runtime/cli.py`
- `agent_runtime/policy.py`
- `agent_runtime/doctor.py`
- `tests/`

## 暂不解决的问题

- 不实现后台服务。
- 不实现自动任务队列。
- 不执行真实外发动作。
- 不处理长期授权缓存。
- 不做 UI。
