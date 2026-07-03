# 06 — 工具适配器层

## 这份文档解决什么问题

Agent Runtime 不应该把所有工具调用都写死在某一个宿主框架里。

工具适配器层的目标，是把不同宿主、CLI、Agent runner、外部服务和本地命令包装成统一的调用边界，让上层路由、任务账本和规则门禁不用关心每个工具的细节。

第一版只定义接口和边界，不实现真实适配器代码。

## Adapter 的统一目标

Adapter 负责把一个具体能力封装成可检查、可记录、可恢复的调用单元。

它应该回答这些问题：

- 这个工具能做什么？
- 输入需要什么字段？
- 输出会返回什么结构？
- 是否会离开本地？
- 是否需要用户授权？
- 执行前需要哪些 policy preflight？
- 执行后需要哪些 postflight / evidence？
- 失败时应该进入 `blocked` 还是 `failed`？

## Adapter 不做什么

Adapter 不应该：

- 绕过 Policy Schema。
- 绕过用户授权。
- 吞掉错误并假装成功。
- 在没有 evidence 的情况下把任务标记为 `finished`。
- 私自改写任务状态账本。
- 把模型成本当成硬门禁。
- 把真实密钥、token 或用户隐私写入日志。

Adapter 只负责执行边界清晰的动作，并返回结构化结果。是否继续、是否重试、是否升级给用户，由 Runtime 的任务层和策略层决定。

## Adapter 顶层字段

第一版 Adapter 注册项建议包含：

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `id` | string | 是 | 稳定唯一 id |
| `name` | string | 是 | 人类可读名称 |
| `kind` | string | 是 | 适配器类型 |
| `description` | string | 否 | 用途说明 |
| `enabled` | boolean | 是 | 是否启用 |
| `capabilities` | array | 是 | 能力标签 |
| `risk_level` | string | 是 | `local`、`external`、`destructive`、`privileged` |
| `requires_approval` | boolean | 是 | 默认是否需要用户授权 |
| `input_schema` | object | 是 | 输入结构说明 |
| `output_schema` | object | 是 | 输出结构说明 |
| `preflight_checks` | array | 否 | 执行前检查 |
| `postflight_checks` | array | 否 | 执行后检查 |
| `failure_mapping` | object | 否 | 失败到任务状态的映射 |
| `notes` | array | 否 | 备注 |

## kind 类型

| kind | 含义 |
|:---|:---|
| `qwenpaw_agent_api` | QwenPaw Agent API 或内部 Agent 调用 |
| `acp_runner` | ACP runner，例如 Kimi Code、Claude Code、OMP |
| `cli_tool` | 命令行工具，例如 Kimi CLI |
| `shell` | 本地 shell 命令 |
| `lark` | 飞书消息、文档、卡片等能力 |
| `github` | GitHub CLI / API |
| `webbridge` | 真实浏览器网页读取或交互桥接 |
| `manual` | 暂时只做人工步骤说明 |

## risk_level 风险级别

| risk_level | 含义 | 默认处理 |
|:---|:---|:---|
| `local` | 只读或低风险本地操作 | 通常不需要授权 |
| `external` | 会访问网络、外部 API 或发送内容 | 通常需要 preflight |
| `destructive` | 删除、覆盖、强杀、不可逆修改 | 需要用户授权 |
| `privileged` | 改代理、权限、系统配置、凭据 | 需要用户授权和 postflight |

风险级别不是唯一判断来源。最终是否阻断，仍由 Policy Schema 和当前任务上下文决定。

## 统一输入格式

Runtime 调用 Adapter 时，建议统一传入一个 envelope：

```json
{
  "task_id": "task-20260703-001",
  "adapter_id": "github-cli",
  "operation": "repo_create",
  "actor": "orchestrator",
  "input": {
    "name": "s-black-harness-engineering",
    "visibility": "public"
  },
  "context": {
    "source": "console",
    "requires_user_approval": true,
    "approval_ref": "user-message-20260703-001"
  }
}
```

## 统一输出格式

Adapter 返回结果也应该统一：

```json
{
  "status": "succeeded",
  "adapter_id": "github-cli",
  "operation": "repo_create",
  "message": "Repository created and pushed.",
  "artifacts": [
    "https://github.com/example/s-black-harness-engineering"
  ],
  "evidence": [
    {
      "type": "external_confirmation",
      "description": "Remote repository URL returned by GitHub CLI.",
      "ref": "https://github.com/example/s-black-harness-engineering"
    }
  ],
  "raw_ref": null
}
```

## status 结果状态

| status | 含义 | 对任务状态的建议 |
|:---|:---|:---|
| `succeeded` | 执行成功 | 可继续，必要时增加 evidence |
| `blocked` | 被规则、权限、缺输入或等待用户阻塞 | 任务进入 `blocked` |
| `failed` | 工具失败且短期不应继续重试 | 任务进入 `failed` 或交由人工判断 |
| `needs_approval` | 需要用户授权 | 任务进入 `blocked`，reason=`need_user_approval` |
| `needs_input` | 需要更多输入 | 任务进入 `blocked`，reason=`need_user_input` |
| `skipped` | 条件不满足或不需要执行 | 通常记录事件，不改变任务状态 |

## preflight_checks

执行前检查建议写成列表：

```json
"preflight_checks": [
  "policy_check",
  "secret_scan",
  "target_confirmed",
  "user_approval"
]
```

常见 preflight：

| 检查项 | 说明 |
|:---|:---|
| `policy_check` | 根据 Policy Schema 检查动作是否允许 |
| `secret_scan` | 对准备外发的正文、diff 或参数做密钥扫描 |
| `target_confirmed` | 确认目标仓库、目标会话、目标文件或目标目录 |
| `user_approval` | 用户明确授权 |
| `diff_review` | 审查 Git diff 或文件变更 |
| `working_tree_clean` | 确认工作树状态符合预期 |
| `network_available` | 网络或代理可用 |

## postflight_checks

执行后检查用于生成 evidence 或恢复环境：

```json
"postflight_checks": [
  "artifact_exists",
  "remote_status_verified",
  "proxy_restored"
]
```

常见 postflight：

| 检查项 | 说明 |
|:---|:---|
| `artifact_exists` | 产物文件存在 |
| `json_valid` | JSON / JSONL 语法有效 |
| `remote_status_verified` | 远端仓库、Issue、消息等可确认 |
| `git_status_clean` | Git 工作树干净 |
| `proxy_restored` | 代理或系统配置已恢复 |
| `test_output` | 测试或脚本输出可作为证据 |

## failure_mapping

不同失败应该映射到不同任务状态。

```json
"failure_mapping": {
  "permission_denied": "blocked",
  "network_error": "blocked",
  "invalid_input": "blocked",
  "tool_crash": "failed",
  "policy_blocked": "blocked"
}
```

建议默认规则：

- 缺权限、缺用户授权、缺输入、网络不通：进入 `blocked`。
- 工具自身崩溃、命令不存在、重复失败：进入 `failed` 或由 Orchestrator 判断。
- Policy 命中硬阻断：进入 `blocked`，reason=`policy_blocked`。

## 第一批适配器

Stage 4 第一版先定义这些适配器，不实现代码。

### QwenPaw Agent API

用途：调用 QwenPaw 中已配置的 Agent。

典型操作：

- `chat_with_agent`
- `submit_to_agent`
- `check_agent_task`

风险：通常是 `external`，因为它可能触发其他 Agent 调工具或访问外部系统。

要求：委派结果必须由 Orchestrator 验收，不能只凭下游口头说完成。

### Kimi CLI / ACP

用途：搜索、看图、读取网页、脚本查询、中度编程。

典型操作：

- `kimi_search`
- `delegate_external_agent(kimi_code)`

要求：搜索结果要收敛成结论；代码结果要做抽查或测试。

### Claude Code ACP

用途：特定长文创作、深度工程协作或需要 Claude 风格能力的任务。

风险：成本较高，作为路由参考，不作为硬门禁。

要求：非必要不默认使用；完成后需要 Orchestrator 验收。

### OMP / pi

用途：工程协作、模型路由、LSP/DAP 场景和中重度技术排查。

要求：适合工程任务，但需要明确任务边界、成本预期和验收方式。

### Shell

用途：本地文件检查、格式验证、测试、Git 状态查询等。

风险：跨度很大，从低风险只读到高风险删除都有。

要求：命令必须先按 Policy Schema 检查；破坏性命令必须授权。

### 飞书

用途：发送消息、卡片、读取或写入飞书文档、多维表格等。

风险：外部发送和协作平台写入，通常需要目标确认和用户授权。

要求：多行消息优先卡片；发送前确认目标会话或文档。

### GitHub

用途：创建仓库、Issue、PR、评论、push、读取远端状态。

风险：公开发布和远端写入。

要求：发布前必须做密钥扫描、目标确认、diff review 和用户授权。

### WebBridge

用途：真实浏览器登录态下的网页读取、搜索和交互。

风险：访问外部网页，可能触发登录态、隐私或远端动作。

要求：网页任务默认优先 WebBridge；写入或提交动作必须授权。

## 与 Policy Schema 的关系

Adapter 执行前必须先产生一个可检查的 action 描述，交给 policy 层判断。

示例：

```json
{
  "adapter_id": "github-cli",
  "operation": "push",
  "risk_level": "external",
  "target": "origin/main",
  "payload_refs": ["git_diff", "commit_message"]
}
```

Policy 层返回：

- `pass`：可以继续。
- `warn`：可以继续，但记录提醒。
- `blocked`：Adapter 不得执行。
- `needs_approval`：任务进入 `blocked`，等待用户授权。

## 与 Task State 的关系

Adapter 结果会影响任务状态：

- `succeeded`：追加 progress / evidence。
- `needs_approval`：任务进入 `blocked`。
- `needs_input`：任务进入 `blocked`。
- `blocked`：任务进入 `blocked`，记录原因。
- `failed`：任务进入 `failed` 或由 Orchestrator 判断是否改为 blocked。

任务是否最终进入 `finished`，由 completion rules 决定，不由 Adapter 单独决定。

## 与 Agent Registry 的关系

Agent Registry 告诉 Runtime “谁适合做什么”。Adapter Registry 告诉 Runtime “怎么调用能力”。

两者关系：

```text
用户任务
  -> 任务路由
  -> Agent Registry 选择执行者
  -> Adapter Registry 选择调用方式
  -> Policy preflight
  -> Adapter 执行
  -> Postflight / evidence
  -> Task ledger 更新
```

## 第一版落地范围

Stage 4 第一版交付物：

1. `docs/06-adapter-layer.md`：工具适配器层设计文档。
2. `adapters/adapter.schema.json`：Adapter 注册项 JSON Schema 草案。
3. `adapters/adapters.sample.json`：第一批适配器样例。

## 暂不解决的问题

- 不实现真实 Adapter 代码。
- 不做后台任务队列。
- 不接管 QwenPaw 现有工具调用。
- 不做权限系统 UI。
- 不自动执行外部发布。
