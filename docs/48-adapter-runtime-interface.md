# 48 — Adapter Runtime Interface

## 阶段定位

本文定义中枢运行台如何统一接入 Agent、工具与外部系统。目标不是立刻实现所有 adapter，而是先建立一套稳定的后端抽象，让 QwenPaw、Kimi、Claude、OMP、Shell、GitHub、飞书、WebBridge、Obsidian 等能力都能被纳入同一套 Runtime 语义。

## 为什么需要统一接口

如果每个工具都各写一套命令、参数和结果格式，会带来这些问题：

- 上层 workflow 无法稳定复用
- UI 以后无法统一展示和操作
- approval / evidence / artifact 无法统一沉淀
- audit / report / retry / timeout / cancel 难以收口

因此中枢台内部不应直接面向“某个脚本”或“某个 ACP runner”，而应面向一组统一的 adapter 接口。

## Adapter 的定位

Adapter 是中枢台与外部执行能力之间的边界层。

它负责：

- 描述某个工具或宿主的能力范围
- 将上层统一 request 转成底层工具可理解的调用
- 将底层结果映射为统一 response / artifact / evidence / error
- 暴露风险等级、前置条件、审批要求和失败语义

Adapter 不负责：

- 决定任务该交给谁（那是 routing 的职责）
- 决定任务是否完成（那要结合 evidence / report）
- 直接绕过 guardrail 静默执行高风险动作

## Adapter 分类

### 1. Agent Adapter

用于会话型或任务型智能体，例如：

- QwenPaw Agent API
- Kimi Code ACP
- Claude Code ACP
- OMP / pi

特点：

- 可能有会话状态
- 可能支持后台任务
- 可能支持中断后续跑
- 可能涉及 approval 往返

### 2. Tool Adapter

用于无会话或短生命周期工具，例如：

- Shell
- GitHub CLI
- WebBridge
- Obsidian CLI
- public scan / doctor / local scripts

特点：

- 一次 request 对应一次执行
- 更强调输入、输出、超时、退出码与 artifact

### 3. Service Adapter

用于外部平台或业务系统，例如：

- 飞书
- GitHub API
- 邮件
- 日历
- Gitea
- NAS 服务

特点：

- 可能是高风险外发
- 可能需要审批、凭据、组织边界
- 更强调 publish / send / sync / fetch 等操作语义

## 统一能力声明

每个 adapter 至少要声明：

- `adapter_id`
- `display_name`
- `adapter_type`
- `capabilities`
- `risk_level`
- `supports_session`
- `supports_background`
- `supports_approval_roundtrip`
- `supports_artifacts`
- `supports_cancel`
- `timeout_profile`
- `input_schema_ref`
- `output_schema_ref`

示意：

```json
{
  "adapter_id": "kimi-code-acp",
  "display_name": "Kimi Code ACP",
  "adapter_type": "agent",
  "capabilities": [
    "dispatch.agent.coding",
    "inspect.repo",
    "edit.workspace"
  ],
  "risk_level": "medium",
  "supports_session": true,
  "supports_background": true,
  "supports_approval_roundtrip": true,
  "supports_artifacts": false,
  "supports_cancel": true
}
```

## 统一请求模型

中枢台不应该直接向 adapter 传“原始命令字符串”作为唯一语义，而应传统一 request。

建议核心字段：

- `request_id`
- `task_id`
- `run_id`
- `adapter_id`
- `capability`
- `operation`
- `mode`（inspect / dry-run / commit / review / report）
- `input`
- `target`
- `constraints`
- `approval_context`
- `timeout_seconds`
- `caller`

示意：

```json
{
  "request_id": "req-20260707-001",
  "task_id": "task-20260707-001",
  "adapter_id": "github-cli",
  "capability": "publish.github.push",
  "operation": "git_push",
  "mode": "commit",
  "target": "origin/main",
  "constraints": {
    "require_approval": true,
    "require_public_scan": true
  }
}
```

## 统一响应模型

无论底层工具如何返回，中枢台内部都应统一映射到一个 response 包装层。

建议核心字段：

- `request_id`
- `adapter_id`
- `status`
- `result_code`
- `summary`
- `artifacts`
- `evidence`
- `findings`
- `needs_approval`
- `next_action`
- `timing`
- `raw_ref`

注意：

- `raw_ref` 只能作为安全引用，不应默认回显完整原始载荷。
- 文本输出应优先提供 compact summary，而不是直接 dump stdout / stderr。

## Approval 模型

统一接口必须允许 adapter 表达审批往返，而不是只有 PASS / FAIL 两种结果。

至少要支持：

- `approval_required`
- `approval_pending`
- `approval_granted`
- `approval_rejected`
- `approval_expired`

这对以下场景很关键：

- GitHub push
- 飞书发消息
- 外部系统写入
- 高风险配置修改
- 需要人工确认的批量 commit

## Artifact 与 Evidence

Adapter 输出不应只有文本结果，还应能产出结构化 artifact。

常见 artifact：

- draft file
- report file
- screenshot
- exported json
- response snapshot
- log reference

常见 evidence：

- validation passed
- public scan passed
- ledger check passed
- task status changed
- artifact persisted

这些对象未来都应能被 UI、report 和 audit 读取。

## 失败与取消语义

统一接口应覆盖这些失败类型：

- 参数错误
- preflight blocked
- approval pending
- timeout
- execution failed
- partial result rejected
- post-check failed
- rollback failed
- canceled

这样中枢台才能统一处理：

- retry
- escalation
- fallback
- review required
- rollback required

## 与当前仓库的关系

当前仓库已经有一些基础积木：

- adapter schema
- execution envelope
- runtime gate / report / ledger check
- controlled write / freeze / strict freeze

但这些积木还没有被提升为“中枢台统一 adapter 接口”的完整叙事。本文的作用就是把它们从“局部能力”收束到“统一接入协议”主线上。

## 下一步衔接

本文之后应继续：

- `49 — Capability Routing Model`
- `50 — Control Plane State Model`
- `51 — Backend-first API Boundary`

这样才能把“接进来”进一步推进到“如何路由”和“如何被未来 UI 操作”。
