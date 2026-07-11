# 49 — Capability Routing Model

## 阶段定位

本文定义中枢运行台如何把“任务意图”路由到具体 Agent 或 Tool Adapter。目标不是让上层 workflow 直接绑定某个底层实现，而是先抽象出 capability 层，让中枢台按能力、风险、边界和可用性做路由决策。

## 为什么要先做 Capability

如果上层直接写成：

- 代码任务永远交给 Kimi
- 发消息永远走飞书脚本
- push 永远走 GitHub CLI

会带来这些问题：

- 更换底层实现时，上层 workflow 会整体断裂
- 无法表达 fallback 和多实现竞争
- UI 以后只能记住工具名，不能表达业务能力
- 风险控制与能力选择耦合在一起

因此中枢台不应优先面向工具名，而应优先面向 capability。

## Capability 的定义

Capability 表示中枢台可调度的一类稳定能力，而不是某个具体命令。

例子：

- `inspect.repo`
- `search.web`
- `dispatch.agent.coding`
- `read.workspace`
- `write.ledger.event`
- `publish.github.push`
- `message.lark.send`
- `report.runtime.status`

Capability 是上层任务意图和底层 adapter 实现之间的中间层。

## 路由输入

一次 routing 至少要消费以下输入。其中 `available_adapters` 来自 `48 — Adapter Runtime Interface` 中定义的 adapter 能力声明与约束；`policy_constraints` 来自安全与审计内核。

- `task_type`
- `requested_capability`
- `risk_level`
- `execution_mode`（inspect / dry-run / commit / review）
- `workspace_scope`
- `user_approval_state`
- `available_adapters`（来自 adapter registry / adapter metadata）
- `preferred_agent`
- `policy_constraints`
- `cost / latency / reliability profile`

## 路由输出

Routing 的输出不只是“选中了谁”，还应包括选择理由和后续约束。这些输出会直接进入下游执行与状态沉淀：

- `selected_adapter_id` -> 交给 `48 — Adapter Runtime Interface` 生成并执行具体 adapter request。
- `requires_approval` / `requires_dry_run` / `requires_review` -> 交给 guardrail 内核决定 preflight 策略。
- `fallback_adapter_ids` -> 作为 retry / escalation 时的候选链。
- `expected_artifacts` / `routing_reason` / `blocked_reason` -> 写入 `50 — Control Plane State Model` 的 `Run` / `Event` / `Report`。

建议输出：

- `selected_adapter_id`
- `selected_capability`
- `fallback_adapter_ids`
- `requires_approval`
- `requires_dry_run`
- `requires_review`
- `expected_artifacts`
- `routing_reason`
- `blocked_reason`（如果无法路由）

## 三层路由模型

### 1. Capability Match

先找有哪些 adapter 声称自己支持该 capability。

例如：

- `search.web`
  - `kimi-webbridge`
  - `kimi-search-cli`
- `dispatch.agent.coding`
  - `kimi-code-acp`
  - `omp-acp`
  - `claude-code-acp`

### 2. Constraint Filter

再根据当前约束过滤：

- 是否需要网络
- 是否需要审批
- 是否允许外部写入
- 是否要求只读
- 是否在工作区内
- 是否支持后台执行
- 是否支持 artifact

### 3. Preference / Fallback Rank

最后根据偏好与可用性排序：

- 主偏好
- 成本
- 稳定性
- 延迟
- 当前 runner 是否可用
- 是否已有活跃会话

## 已实现的第一版约束路由（Stage 11）

当前已实现 capability routing 的第一版，作为 Stage 11 的最小落地。它只扩展路由决策的输入面，不执行真实 adapter、不访问网络、不写 ledger。

### 处理流程

第一版仍按三层模型执行，但把第二层从“设计意图”变成可配置约束：

1. **Capability Match**：从 source-backed adapter registry 投影中找出声明支持该 capability 的 adapter。
2. **Constraint Filter**：根据 CLI / policy 传入的约束过滤候选集。
3. **Preference Rank**：若存在显式 `preferred_adapter` 则优先置顶；其余候选保持 registry 原始顺序作为 fallback 链。

### 已支持的约束

CLI 通过以下标志传入：

| 标志 | 作用 |
|:---|:---|
| `--preferred-adapter <id>` | 将指定 adapter 排在首位；若其不满足 capability 或功能/风险约束，则降级到 source-order 的下一个可用候选，并在 `constraints.preferred_adapter_rejected` 中说明原因。 |
| `--max-risk <local\|external\|destructive\|privileged>` | 只保留 risk_level 不超过该级别的候选。 |
| `--require-background` | 只保留声明支持 `supports_background: true` 的候选。 |
| `--require-artifacts` | 只保留声明支持 artifact（`supports_artifacts: true`）的候选。 |

这些约束通过 `RouteConstraints` 对象传给 routing 函数，并在 `orchestration route preview` 与 `orchestration preflight` 中生效。

### 第一版未实现的内容

以下排序/可用性维度目前**未实现**，保留给后续阶段：

- 成本（cost）评分
- 延迟（latency）评分
- 可用性 / 健康度（availability）打分
- 在线状态 / 活跃会话感知
- 真实并发调度

### 示例输出形状

```json
{
  "status": "pass",
  "requested_capability": "light_coding",
  "capability": "light_coding",
  "selected_adapter_id": "kimi-code-acp",
  "operation": "light_coding",
  "requested_mode": "dry-run",
  "selected_mode": "dry-run",
  "risk_level": "external",
  "requires_approval": true,
  "requires_dry_run": true,
  "fallback_candidates": [
    {"adapter_id": "omp-acp", "reason": "passes constraints and supports capability"}
  ],
  "routing_reason": "Selected adapter 'kimi-code-acp' for capability 'light_coding' based on preferred adapter and capability match.",
  "constraints": {
    "adapter_kind": "acp_runner",
    "risk_level": "external",
    "requires_approval": true,
    "requires_dry_run": true,
    "preflight_checks": ["policy_check", "scope_confirmed"],
    "routing_constraints": {
      "preferred_adapter": "kimi-code-acp",
      "require_background": false,
      "require_artifacts": false,
      "max_risk": "external"
    }
  }
}
```

若约束过滤后无候选，则 `status` 为 `blocked`，`selected_adapter_id` 被显式输出为 `null`；不存在单独的 `blocked_reason` 字段，原因由 `routing_reason` 给出，被拒绝的候选详情位于 `constraints.rejected_candidates`（若指定了 `--preferred-adapter` 且被拒绝，还会包含 `constraints.preferred_adapter_rejected`）。

## 路由示例

### 示例 1：中度编程任务

上层任务意图：

```text
requested_capability = dispatch.agent.coding
risk_level = medium
execution_mode = execute
```

候选：

- `kimi-code-acp`
- `omp-acp`
- `claude-code-acp`

策略：

- 默认优先 `kimi-code-acp`
- 若 Kimi 不可用或任务需要更强工程编排，再考虑 `omp-acp`
- `claude-code-acp` 仅在特定成本/领域约束满足时启用

### 示例 2：网页交互任务

上层任务意图：

```text
requested_capability = search.web
execution_mode = inspect
```

候选：

- `kimi-webbridge`
- `kimi-search-cli`

策略：

- 优先 `kimi-webbridge`
- 真实浏览器抓取失败时才降级 `kimi-search-cli`

### 示例 3：GitHub push

上层任务意图：

```text
requested_capability = publish.github.push
execution_mode = commit
risk_level = high
```

候选：

- `github-cli`

策略：

- 命中高风险 publish capability
- 必须先过 preflight / public scan / approval gate
- approval 未满足时 routing 输出 blocked，而不是直接执行

## 与 Guardrail 的关系

Routing 不代替 guardrail。

两者的关系应该是：

```text
Task intent
  -> Capability routing
  -> Guardrail preflight
  -> Adapter execution / dry-run / commit
  -> Post-check / evidence / report
```

也就是说：

- routing 负责“该找谁做”
- guardrail 负责“这一步能不能做”

## 与 UI 的关系

未来 UI 不应该强迫用户直接选择底层工具名，而应优先让用户选择：

- 我要做什么能力
- 这一步是否 dry-run
- 是否需要审批
- 是否允许 fallback

然后由中枢台显示：

- 当前命中的 adapter
- 选择理由
- fallback 链
- 被 block 的原因

## 当前阶段不做什么

本文不实现：

- 自动路由引擎代码
- 在线打分器
- 成本监控系统
- 真实多 adapter 并发调度
- UI 交互层

本文只先定义 capability routing 的后端模型。

## 本文的产出与下游消费

本文产生的 routing 结果会由 48 和 50 继续消费：

| 本文产出 | 下游文档 | 消费方式 |
|:---|:---|:---|
| `selected_adapter_id` / `selected_capability` / `operation` 推断 | `48 — Adapter Runtime Interface` | 组装 adapter request 并执行 |
| `requires_approval` / `requires_dry_run` / `requires_review` | Guardrail Core + `48` | 决定 preflight 与执行模式 |
| `fallback_adapter_ids` / `routing_reason` / `blocked_reason` | `50 — Control Plane State Model` | 写入 `Run`、`Event`、`Report` |

整个链条可简化为：

```text
Task intent
  -> Capability routing (本文)
  -> Guardrail preflight
  -> Adapter execution / dry-run / commit (48)
  -> Run / Artifact / Evidence / Report (50)
```

## 下一步衔接

本文之后应继续：

- `50 — Control Plane State Model`
- `51 — Backend-first API Boundary`

这样 routing 才能真正沉淀到控制面状态，并为未来 UI / API 做准备。
