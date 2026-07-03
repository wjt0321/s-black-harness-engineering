# 05 — Agent 注册表

## 这份文档解决什么问题

Agent Runtime 需要知道有哪些 Agent、每个 Agent 擅长什么、工作区在哪里、不能做什么、该怎么调用、做完后由谁验收。

这就是 Agent 注册表要解决的问题。

第一版注册表只做“可读配置”和“路由参考”，不实现真实自动路由。

## 为什么需要注册表

没有注册表时，多 Agent 协作依赖聊天记忆和人工判断，容易出现这些问题：

- 不知道哪个 Agent 当前可用。
- 不知道哪个 Agent 适合做哪类任务。
- 不知道某个 Agent 的工作区和边界。
- 委派后缺少统一验收标准。
- 后续换宿主框架时，Agent 信息散落在提示词、记忆和配置里。

注册表的目标，是把这些信息集中、结构化、可审查地记录下来。

## 注册表不是什么

第一版注册表不是：

- 不是权限系统。
- 不是自动调度器。
- 不是模型计费系统。
- 不是实时健康检查。
- 不是替代 QwenPaw 的 agent.json。

它只是 Agent Runtime 的一份外部索引，供后续路由层读取。

## 推荐文件位置

```text
agents/
  agents.schema.json
  agents.sample.json
```

早期优先用 JSON，方便 schema 校验。以后如果需要给人手写，可以再补 YAML 版本。

## Agent 对象字段

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `id` | string | 是 | Agent 唯一 ID，例如 `orchestrator` |
| `name` | string | 是 | 人类可读名称，例如 `Orchestrator` |
| `role` | string | 是 | 定位说明 |
| `enabled` | boolean | 是 | 是否启用 |
| `workspace` | string | 是 | 工作区绝对路径 |
| `runtime` | object | 是 | 调用方式与宿主信息 |
| `capabilities` | array | 是 | 能力标签 |
| `default_tasks` | array | 否 | 默认适合的任务类型 |
| `avoid_tasks` | array | 否 | 不建议交给它的任务 |
| `hard_boundaries` | array | 否 | 硬边界，不能越过 |
| `handoff` | object | 否 | 委派和验收关系 |
| `cost_profile` | object | 否 | 成本/额度备注 |
| `notes` | array | 否 | 其他备注 |

## runtime 字段

`runtime` 用于说明怎么调用这个 Agent。

```json
{
  "kind": "qwenpaw_agent",
  "call_method": "chat_with_agent",
  "agent_id": "media-agent",
  "workspace": "./workspaces/media-agent"
}
```

常见 kind：

| kind | 含义 |
|:---|:---|
| `qwenpaw_agent` | QwenPaw 内部 Agent |
| `acp_runner` | ACP runner，例如 Kimi Code / Claude Code / OMP |
| `cli_tool` | 命令行工具，例如 kimi CLI |
| `external_service` | 外部服务 |
| `manual` | 只作为人工参考，不自动调用 |

## capabilities 能力标签

能力标签尽量稳定，不要写成长句。

建议第一批能力标签：

| 标签 | 含义 |
|:---|:---|
| `planning` | 规划、拆解、文档策略 |
| `quality_review` | 质量审查 |
| `memory_distillation` | 记忆提炼 |
| `content_creation` | 内容创作 |
| `minimax_media` | MiniMax 图、音频、视频能力 |
| `web_search` | 网页搜索 |
| `light_coding` | 轻量编程 |
| `heavy_coding` | 重度编程 |
| `novel_writing` | 小说写作 |
| `policy_guardrail` | 规则门禁 |
| `daily_ops` | 日常杂务 |

## default_tasks 默认任务类型

用于给未来路由层做参考。

示例：

```json
"default_tasks": [
  "规划 Agent Runtime 架构",
  "审查下游 Agent 输出",
  "起草规则和策略文档"
]
```

注意：这里不是硬规则，只是默认倾向。

## avoid_tasks 不建议任务

用于避免把任务派错人。

示例：

```json
"avoid_tasks": [
  "让Media Agent处理密钥统筹",
  "让Orchestrator长期挂普通天气定时任务"
]
```

## hard_boundaries 硬边界

硬边界是不能靠模型“自觉”绕开的规则。未来可以和 Policy Schema 结合。

示例：

```json
"hard_boundaries": [
  "未经用户明确授权不得 push Obsidian 仓库",
  "不得读取或外泄其他 Agent 的敏感内容",
  "不得删除 ./workspace 内容"
]
```

## handoff 委派与验收

`handoff` 说明谁可以委派给它，以及完成后谁负责验收。

```json
{
  "can_receive_from": ["orchestrator"],
  "default_reviewer": "orchestrator",
  "requires_review": true
}
```

当前原则：

- Orchestrator是专业性中枢，负责规划、调度和质量审查。
- Media Agent适合内容创作、MiniMax 任务和轻量日常活。
- Memory Agent负责记忆整理和记忆问答，不越界处理普通执行任务。
- 编程任务默认优先 Kimi Code；Claude Code 主要留给小说创作或明确必要场景。

## cost_profile 成本备注

成本信息只作为路由参考，不作为底层硬门禁。

```json
{
  "cost_level": "high",
  "notes": "高成本模型，适合中枢判断和质量审查，不适合长期跑普通杂活。"
}
```

建议 cost_level：

- `low`
- `medium`
- `high`
- `unknown`

## 第一版样例包含哪些 Agent

第一版样例先记录：

1. Orchestrator：专业性中枢 Agent。
2. Media Agent：内容创作和轻量日常事务执行者。
3. Memory Agent：记忆守护者。
4. Kimi Code：搜索、看图、中度编程优先下游。
5. Claude Code：小说写作专用，非小说工程谨慎使用。
6. OMP / pi：工程协作和模型路由候选下游。

## 和任务路由的关系

注册表本身不决定任务去向。未来路由层会综合：

- 用户意图
- 任务风险
- Agent 能力
- Agent 边界
- 成本参考
- 当前可用性
- policy 检查结果

然后给出建议路由。

例如：

```text
任务：写 MiniMax 音乐 prompt 并生成歌曲
建议：Media Agent
原因：命中 minimax_media + content_creation，且Orchestrator不应亲自处理普通创作执行。
```

## 第一版落地范围

Stage 3 第一版交付物：

1. `docs/05-agent-registry.md`：Agent 注册表说明。
2. `agents/agents.schema.json`：注册表 JSON Schema 草案。
3. `agents/agents.sample.json`：第一批 Agent 样例。

## 暂不解决的问题

- 不实现真实自动路由。
- 不做 Agent 在线状态探测。
- 不读取或改写 QwenPaw 的真实配置。
- 不处理权限授予和撤销。
- 不记录敏感密钥、token 或内部凭据。
