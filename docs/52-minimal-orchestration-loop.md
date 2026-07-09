# 52 — 中枢台最小编排闭环

## 阶段定位

本文是 Stage 14 的设计前置文档，目标是在不进入真实多系统放权、不展开 API 边界、不做 UI 的前提下，定义一个可被 CLI / 脚本 / 未来自动化工作流模拟执行的**最小编排闭环**。

47-50 已经分别回答了：

- 47：中枢台是什么、有哪五层结构
- 48：工具如何以积木方式接入
- 49：能力如何路由
- 50：控制面要记录哪些状态对象

本文回答：这些抽象如何组合成一次可审计、可回放、可收口的最小执行循环。

## 为什么需要最小编排闭环

没有闭环，48/49/50 容易停留在各自独立的抽象层：

- adapter 接口定义了，但没人说清楚一次调用从哪开始、到哪结束。
- capability routing 定义了，但没人说清楚路由结果如何变成一次受控执行。
- 状态模型定义了，但没人说清楚哪些事件会触发哪些状态对象的创建。

最小闭环把这些散点串成一条可重复的流程，同时为后续 Stage 15/16 的后端准备和 UI 接入提供可消费的运行语义。

## 什么叫“最小”

本文坚持的最小含义：

- **不真正执行外部系统**：adapter run 仍处于受控模拟或 dry-run 阶段，不访问网络、不发送消息、不写真实外部状态。
- **不实现真实调度引擎**：不涉及并发、定时、后台 worker、事件总线。
- **不做服务化**：不选 HTTP / RPC / WebSocket / 数据库。
- **不做 UI**：只定义后端状态和动作，未来 UI 可消费这些状态。
- **只关注一条主线**：一个 task intent 如何走完 routing -> guardrail -> adapter -> state -> report。

最小不等于简陋。它要求把一次执行的边界、输入输出、失败处理和收口证据都讲清楚。

## 闭环包含哪些步骤

一个最小编排闭环由以下步骤组成：

```text
1. Submit Task
2. Capability Routing
3. Guardrail Preflight
4. Adapter Dry-run / Commit
5. Record Run + Event + Artifact + Evidence
6. Resolve Approval（如需要）
7. Generate Report
```

### 1. Submit Task

入口接收一个任务意图，至少包含：

- `task_type`
- `requested_capability`
- `title` / `summary`
- `workspace`
- `assignee`（可选，可作为 routing 偏好）
- `execution_mode`（inspect / dry-run / commit / review）

输出：

- 一个 `Task` 对象（来自 50），状态为 `planned` 或 `running`。
- 一条初始 `Event`（来自 50），记录任务创建。

### 2. Capability Routing

消费 49 的路由模型：

- 输入：`requested_capability`、`available_adapters`（来自 48）、`policy_constraints`、`workspace_scope` 等。
- 输出：`selected_adapter_id`、`fallback_adapter_ids`、`requires_approval`、`requires_dry_run`、`routing_reason`、`blocked_reason`。

如果 routing 失败，闭环在此结束：

- 生成 `Event`（`blocked`）。
- 生成 `Report`，说明无法路由及原因。
- 任务状态变为 `blocked`。

### 3. Guardrail Preflight

routing 输出进入 guardrail 内核，执行：

- path check
- secret scan
- action rule
- publish rule
- completion rule（如适用）

guardrail 的结果不阻塞闭环本身的设计，但会决定闭环的**执行模式**：

| guardrail 结果 | 闭环行为 |
|:---|:---|
| `ALLOWED` | 可按 `execution_mode` 继续执行 |
| `ALLOWED_WITH_CONSTRAINTS` | 强制降级为 dry-run 或需要审批 |
| `BLOCKED` | 生成本次 `Run`（状态 `blocked`）、`Event`、`Report`，任务保持 `blocked` |
| `NEEDS_APPROVAL` | 创建 `ApprovalRequest`（来自 50），任务状态变为 `blocked`，等待审批 |

关键点：guardrail 卡住的是**本次执行尝试**，不是闭环的推进。即使本次 blocked，闭环仍然完成了一次完整的审计记录。

### 4. Adapter Dry-run / Commit

如果 preflight 允许继续，中枢台组装 48 定义的 adapter request：

- `request_id`
- `task_id`
- `run_id`
- `adapter_id`（来自 routing 输出）
- `capability` / `operation`
- `mode`
- `input`
- `constraints`

当前阶段：

- `dry-run`：只生成 envelope draft、artifact 引用、验证结果，不触发真实外部执行。
- `commit`：在受控写入边界内执行，例如写入项目内 draft、追加 ledger、导出 report，但仍不访问外部系统。

输出：

- `adapter_response`（来自 48）
- `Artifact` 列表（来自 50）
- 执行结果状态：`succeeded` / `failed` / `timeout` / `canceled` / `partial`

### 5. Record Run + Event + Artifact + Evidence

adapter 执行结果被沉淀到 50 定义的状态对象：

- `Run`：记录本次执行尝试，绑定 `adapter_id`、`capability`、`mode`、`status`、`fallback_from`。
- `Event`：记录 `run_started`、`run_completed`、`run_failed`、`artifact_persisted` 等状态迁移。
- `Artifact`：记录 draft、report、snapshot、exported json 等产物引用。
- `Evidence`：记录 guardrail passed、public scan passed、artifact persisted 等完成证明。

这些对象共同构成可回放的基础。

### 6. Resolve Approval（如需要）

如果 preflight 或 routing 触发了审批：

- 创建 `ApprovalRequest`（来自 50）。
- 任务状态变为 `blocked`。
- 闭环暂停，等待外部决议。
- 审批 granted 后，可基于同一 task 发起新的 `Run`；审批 rejected 后，生成失败 `Event` 和 `Report`。

审批是闭环的一个正常分支，不是异常。

### 7. Generate Report

无论本次执行成功与否，闭环最后都生成一个 `Report`（来自 50）：

- 汇总同一 task 下的 `Run`、`Artifact`、`Evidence`。
- 给出 `status_summary`、`key_findings`、`next_action`。
- 如果是 blocked，说明原因和恢复路径。
- 如果是成功，说明还需要哪些后续步骤（例如 dry-run 通过，等待 commit）。

Report 是闭环的收口对象，也是未来 UI / CLI 总览的直接数据来源。

## 各步骤的输入输出

| 步骤 | 主要输入 | 主要输出 | 来自 48/49/50 |
|:---|:---|:---|:---|
| Submit Task | 任务意图 | `Task`、`Event` | 50 |
| Capability Routing | `requested_capability`、`available_adapters` | `selected_adapter_id`、`fallback_*`、`requires_*` | 48 输出作为 49 输入；49 输出作为后续输入 |
| Guardrail Preflight | routing 输出、policy、workspace | preflight 结果、审批要求 | guardrail 内核 |
| Adapter Run | routing 输出、adapter metadata | `adapter_response`、`Artifact` | 48 |
| Record State | adapter response、preflight 结果 | `Run`、`Event`、`Artifact`、`Evidence` | 50 |
| Approval | preflight 触发 | `ApprovalRequest`、状态迁移 | 50 |
| Report | task 下所有对象 | `Report` | 50 |

## Guardrail 在闭环中的位置

在整个闭环中，guardrail 处于**pre-filter**位置，而不是**end-gate**：

```text
Task intent
  -> Capability routing
  -> Guardrail preflight  <-- guardrail 在这里
  -> Adapter dry-run / commit
  -> Run / Artifact / Evidence
  -> Report
```

这意味着：

- guardrail 决定本次尝试能不能按原模式执行。
- guardrail 不决定任务最终能不能完成；任务最终完成由 evidence + report 共同判断。
- guardrail blocked 不会导致闭环“跑不下去”，只会把本次执行记录为 blocked，并给出恢复路径。
- 如果后续发现 guardrail 规则有缺口，可以在不破坏闭环结构的前提下补规则，闭环本身不需要重写。

这就是“guardrail 是长期内核，但不阻塞主线”的体现。

## Fallback 怎么表达

Fallback 在闭环中至少有两层含义：

### 1. Capability-level fallback

来自 49 的 `fallback_adapter_ids`。如果 `selected_adapter_id` 执行失败或被 block，中枢台可以按 fallback 链尝试下一个 adapter，每次尝试都生成独立的 `Run`，并通过 `fallback_from` 字段关联。

```text
Run-A: adapter=adapter-A, status=failed, fallback_from=null
Run-B: adapter=adapter-B, status=succeeded, fallback_from=Run-A
```

### 2. Mode-level fallback

如果 `commit` 模式被 guardrail blocked，可自动降级为 `dry-run` 或 `inspect`，并生成相应 `Run` 和 `Event`。

### 3. Human escalation fallback

如果所有 capability-level fallback 都失败，且任务不能自动完成，闭环生成 `Report`，建议 `next_action=escalate_to_human`，并保留所有 `Run` / `Evidence` 供人工审阅。

## Evidence 与 Report 如何收口

闭环的收口不是“adapter 返回了就算完”，而是要有证据和报告：

### Evidence 来源

| 来源 | Evidence 类型 | 作用 |
|:---|:---|:---|
| guardrail preflight | `path_check_passed` | 证明路径合规 |
| guardrail preflight | `secret_scan_passed` | 证明无敏感信息 |
| adapter dry-run | `dry_run_completed` | 证明 dry-run 已完成 |
| artifact persistence | `artifact_persisted` | 证明产物已落盘 |
| approval resolution | `approval_granted` | 证明审批通过 |
| post-check | `ledger_check_passed` | 证明 ledger 一致性 |

### Report 收口

`Report` 基于同一 task 聚合：

- 所有 `Run` 的状态
- 所有 `Artifact` 引用
- 所有 `Evidence` 引用
- 最终 `task.status`
- `next_action`

Report 的 `next_action` 可能取值：

- `proceed_to_commit`
- `needs_human_review`
- `retry_with_fallback`
- `blocked_wait_for_approval`
- `task_finished`

## 与 47/48/49/50 的关系

```text
47 (Orchestration Hub Vision)
  -> 48 (Adapter Runtime Interface)  <- 定义积木
  -> 49 (Capability Routing Model)   <- 决定用哪块积木
  -> 50 (Control Plane State Model)  <- 定义积木执行后留下什么
  -> 52 (Minimal Orchestration Loop) <- 本文：把 48/49/50 串成一次可重复闭环
  -> 51 (Backend-first API Boundary) <- 未来 UI / CLI / 自动化如何操作后端
```

- 48 的 adapter request / response / artifact / evidence 模型，是闭环第 4 步的执行语义。
- 49 的 routing 输出，是闭环第 2 步的决策输入。
- 50 的 task / run / event / approval / artifact / evidence / report，是闭环第 1/5/6/7 步的状态沉淀。

## 当前阶段不做什么

本文不实现：

- 真实多 Agent 并发调度
- 真实外部系统执行
- HTTP / RPC / WebSocket 服务
- 前端页面
- 数据库选型与持久化
- 审批系统的 UI 或消息通知
- 成本监控、在线打分、自动化自愈

本文只定义最小闭环的后端语义，为后续 CLI 命令、脚本接口和 API 边界留下可执行的设计基础。

## 下一步衔接

本文之后，自然进入：

- `51 — Backend-first API Boundary`

因为 51 才需要回答：未来 UI / CLI / automation 如何操作这个闭环里产生的 task、run、approval、artifact、report。

在进入 51 之前，中枢台后端已经具备：

- 统一接入语义（48）
- 能力路由语义（49）
- 控制面状态模型（50）
- 最小执行闭环语义（52）

这是 Stage 14 之前需要的最小设计上下文。
