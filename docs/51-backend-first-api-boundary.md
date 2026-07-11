# 51 — Backend-first API Boundary

## 阶段定位

本文定义中枢运行台的**后端优先操作边界（Backend-first API Boundary）**：在不进入 UI、不选协议、不做服务化的前提下，先明确未来 CLI、UI、自动化工作流共同依赖的**资源模型**和**操作模型**。

47-53 已经分别回答了：

- 47：中枢台是什么、有哪五层结构。
- 48：工具如何以积木方式接入。
- 49：能力如何路由。
- 50：控制面记录哪些状态对象。
- 52：这些抽象如何组成一次最小执行闭环。
- 53：这个闭环可能对应哪些 CLI / 脚本命令。

本文回答：这些命令背后，哪些资源与操作是稳定的、应该被未来所有入口共享的；以及在这些操作之上，**协议可以晚定，但资源与操作边界必须先定**。

## 为什么 51 必须在 UI 之前完成

如果先做 UI，后补后端边界，会出现三类问题：

1. **UI 只能反射当前 CLI 命令**，而不是反射稳定的业务资源。换一套命令或加一个入口，UI 就要返工。
2. **写入语义被藏在按钮和页面里**，审批、dry-run、commit 的边界不清晰，容易误开权限。
3. **guardrail 与操作耦合**：UI 为了好看可能绕过某些 preflight，导致后端边界被侵蚀。

先做 51 的好处：

- UI 只是资源与操作的一种消费方式；资源不变，UI 可以迭代。
- CLI、脚本、自动化工作流、未来服务化入口可以共享同一套操作语义。
- guardrail 作为操作的 preflight 约束层被显式建模，而不是散落在交互细节里。

因此本阶段结论是：

> **资源模型和操作模型必须先稳定；协议、传输格式、页面布局可以后选。**

## 资源模型

### 顶层资源

顶层资源是指具有独立标识、独立生命周期、可被直接 list/get/operate 的对象。它们对应 50 中的主要状态对象，也是未来 UI 主要面板的直接映射。

| 资源 | 标识符 | 来自 50 的状态对象 | 生命周期 | 说明 |
|:---|:---|:---|:---|:---|
| Task | `task_id` | `Task` | `planned` -> `running` / `blocked` -> `finished` / `failed` | 业务工作单元，闭环的入口和收口锚点。 |
| Run | `run_id` | `Run` | `pending` -> `running` -> `succeeded` / `failed` / `blocked` / `canceled` | 一次具体的执行尝试，绑定 task、capability、adapter、mode。 |
| Approval | `approval_id` | `ApprovalRequest` | `pending` -> `granted` / `rejected` / `expired` | 需要人工确认的动作，可独立 list/resolve。 |
| Artifact | `artifact_id` | `Artifact` | `created` -> 可被引用/预览 | 运行产物，如 draft、report、snapshot、exported json。 |
| Report | `report_id` | `Report` | 按 task/run 聚合生成 | 阶段收口摘要，面向人类或上层系统。 |

### 附属但可查询的对象

以下对象有独立标识，但主要作为顶层资源的附属信息出现，不单独构成主导航面板：

| 对象 | 标识符 | 来自 50 的状态对象 | 所属顶层资源 | 查询方式 | 说明 |
|:---|:---|:---|:---|:---|:---|
| Event | `event_id` | `Event` | `Task` | 通过 Task 的事件流查询；必要时可按 event_id 单条获取。 | 审计流，记录状态迁移、审批、写入、失败等。 |
| Evidence | `evidence_id` | `Evidence` | `Run` / `Task` | 通过 Run 详情或 Report 引用查询；必要时可按 evidence_id 单条获取。 | 完成证明，解释“为什么这一步可以通过/完成”。 |

为什么 Event / Evidence 不是顶层资源：

- Event 的本质是 Task 的时序审计日志，脱离 Task 后几乎没有独立业务含义。
- Evidence 的本质是 Run 或 Task 的证明材料，通常与某次执行或某份 Report 一起被审阅。
- 未来 UI 可以在 Task 详情页内嵌 Event 时间线，在 Run 详情页内嵌 Evidence 列表，不需要把它们提升到与 Task / Run 同级的导航面板。

## 操作模型

操作模型按资源组织。每个操作只描述**做什么**、**输入什么**、**输出什么**、**是否写数据**，不定义具体 CLI 子命令名、REST path、RPC method 或函数签名。

### Task 上的操作

| 操作 | 伪接口名 | 类型 | 输入摘要 | 输出摘要 | 对应 52 步骤 | 对应 53 草案命令 | 对应 50 对象 |
|:---|:---|:---:|:---|:---|:---:|:---|:---|
| list | `TaskCollection.list` | 只读 | filter、pagination | Task 摘要列表 | — | `orchestration task list` | `Task` |
| get | `TaskDetail.get` | 只读 | `task_id` | Task 详情 + 最新状态 | — | `orchestration task get` | `Task` |
| create | `TaskCollection.create` | 受控写入 | task intent | 新 Task + 初始 Event | 1. Submit Task | `orchestration task submit` | `Task`、`Event` |
| preview_routing | `TaskDetail.previewRouting` | 只读 | `task_id` / capability / mode | routing 结果摘要 | 2. Capability Routing | `orchestration route preview` | — |
| routing_snapshot | `TaskDetail.routingSnapshot` | 只读 | `task_id` / capability / mode | `RoutingDecisionSnapshot` | 2. Capability Routing | `orchestration route snapshot` | `RoutingDecisionSnapshot` |
| preflight | `TaskDetail.preflight` | 只读 | `task_id` / candidate run | preflight 结果 | 3. Guardrail Preflight | `orchestration preflight` | — |
| preflight_snapshot | `TaskDetail.preflightSnapshot` | 只读 | `task_id` / candidate run | 带 guardrail 的 `RoutingDecisionSnapshot` | 3. Guardrail Preflight | `orchestration preflight --snapshot` | `RoutingDecisionSnapshot` |
| run | `TaskAction.run` | 受控写入 | `task_id` / mode / input context | 新 Run + 初始 Event | 4. Adapter Dry-run / Commit | `orchestration run` | `Run`、`Event` |
| retry | `TaskAction.retry` | 受控写入 | `task_id` / `run_id` | 新 Run（`retry_of`） | 7. Fallback / Retry | `orchestration run --retry` | `Run`、`Event` |
| fallback | `TaskAction.fallback` | 受控写入 | `task_id` / target adapter | 新 Run（`fallback_from`） | 7. Fallback / Retry | `orchestration run --fallback-to` | `Run`、`Event` |
| report | `TaskDetail.report` | 只读 | `task_id` | Report 摘要或详情 | 7. Generate Report | `orchestration report` | `Report` |

### Run 上的操作

| 操作 | 伪接口名 | 类型 | 输入摘要 | 输出摘要 | 对应 52 步骤 | 对应 53 草案命令 | 对应 50 对象 |
|:---|:---|:---:|:---|:---|:---:|:---|:---|
| list | `RunCollection.list` | 只读 | `task_id` filter、status filter | Run 摘要列表 | — | `orchestration run list` | `Run` |
| get | `RunDetail.get` | 只读 | `run_id` | Run 详情 + Artifact / Evidence 引用 | 5. Record State | `orchestration inspect` | `Run`、`Artifact`、`Evidence` |
| inspect | `RunDetail.inspect` | 只读 | `run_id` | 紧凑摘要（artifact counts、evidence counts） | 5. Record State | `orchestration inspect` | `Run`、`Artifact`、`Evidence` |

### Approval 上的操作

| 操作 | 伪接口名 | 类型 | 输入摘要 | 输出摘要 | 对应 52 步骤 | 对应 53 草案命令 | 对应 50 对象 |
|:---|:---|:---:|:---|:---|:---:|:---|:---|
| list | `ApprovalCollection.list` | 只读 | status filter、task filter | Approval 摘要列表 | — | `orchestration approval list` | `ApprovalRequest` |
| get | `ApprovalDetail.get` | 只读 | `approval_id` | Approval 详情 | 6. Resolve Approval | `orchestration approval get` | `ApprovalRequest` |
| resolve | `ApprovalResolution.resolve` | 受控写入 | `approval_id` / decision / reason | 更新后的 Approval + Event | 6. Resolve Approval | `orchestration approval resolve` | `ApprovalRequest`、`Event` |

### Artifact 上的操作

| 操作 | 伪接口名 | 类型 | 输入摘要 | 输出摘要 | 对应 52 步骤 | 对应 53 草案命令 | 对应 50 对象 |
|:---|:---|:---:|:---|:---|:---:|:---|:---|
| list | `ArtifactCollection.list` | 只读 | `task_id` / `run_id` filter | Artifact 摘要列表 | — | `orchestration artifact list` | `Artifact` |
| get | `ArtifactDetail.get` | 只读 | `artifact_id` | Artifact 元数据 + 安全引用 | 5. Record State | `orchestration artifact get` | `Artifact` |
| export | `ArtifactAction.export` | 受控写入 | envelope draft / target path | 持久化后的 Artifact | 4. Adapter Dry-run / Commit | `runtime draft export --commit` | `Artifact` |

### Report 上的操作

| 操作 | 伪接口名 | 类型 | 输入摘要 | 输出摘要 | 对应 52 步骤 | 对应 53 草案命令 | 对应 50 对象 |
|:---|:---|:---:|:---|:---|:---:|:---|:---|
| list | `ReportCollection.list` | 只读 | `task_id` filter | Report 摘要列表 | — | `orchestration report list` | `Report` |
| get | `ReportDetail.get` | 只读 | `report_id` | Report 详情 | 7. Generate Report | `orchestration report` | `Report` |
| generate | `ReportAction.generate` | 只读 | `task_id` / `run_id` | 新生成的 Report | 7. Generate Report | `orchestration report` | `Report` |

说明：`Report.generate` 是聚合计算，不修改 task/run/artifact/evidence 本身，因此归类为只读。如果需要缓存 Report，缓存写入应走单独的受控写入规则。

## 什么是“资源稳定、协议未定”

本文定义的边界是**资源与操作语义**的边界，不是传输协议的边界。具体含义：

| 已确定 | 未确定 |
|:---|:---|
| 有哪些顶层资源（Task / Run / Approval / Artifact / Report） | 是 REST path、RPC method、本地函数还是 CLI 子命令 |
| 每个资源的标识符和核心字段 | 具体的序列化格式细节（虽然会复用现有 JSON schema 风格） |
| 每个操作做什么、读还是写、输入输出语义 | 认证鉴权机制、分页格式、错误码映射 |
| guardrail 作为每个写操作的 preflight 约束层 | guardrail 检查是由调用方触发还是由服务端自动触发 |
| Event / Evidence 是附属对象 | 它们的索引和查询协议 |

举例：

- `TaskAction.run` 这个操作是稳定的：它表示“为指定 Task 发起一次 Run”，输入是 task 标识和执行模式，输出是新 Run。
- 但它未来可以是 CLI 子命令、RPC 方法、本地函数或 REST endpoint；具体形式不影响资源与操作的定义。

先做 51 的价值就在于：无论未来选哪种协议，资源与操作不需要返工。

## Guardrail 在 API Boundary 中的位置

Guardrail 不是顶层资源，也不是独立操作。它是**每个写操作（write-like action）的前置约束层**。

```text
调用方请求写操作
  -> API Boundary 接收请求
  -> Guardrail Preflight  <-- guardrail 在这里
  -> 操作执行（dry-run / commit / blocked）
  -> 状态对象更新
  -> Event / Evidence 记录
```

适用写操作：

- `TaskCollection.create`
- `TaskAction.run`
- `TaskAction.retry`
- `TaskAction.fallback`
- `ApprovalResolution.resolve`
- `ArtifactAction.export`

Guardrail 的结果决定写操作如何执行：

| guardrail 结果 | 写操作行为 |
|:---|:---|
| `ALLOWED` | 按请求模式执行 |
| `ALLOWED_WITH_CONSTRAINTS` | 强制降级为 dry-run 或要求额外审批 |
| `BLOCKED` | 拒绝执行，生成 blocked Run / Event / Report |
| `NEEDS_APPROVAL` | 创建 Approval，操作暂停等待决议 |

这意味着：

- 任何写操作都不能绕过 guardrail preflight。
- guardrail 不阻塞 API boundary 的设计，它只约束每个写操作的执行模式。
- 未来 UI 调用写操作时，本质上是在调用同一个带 guardrail preflight 的操作边界。

## 只读、受控写入、仍然不开放

### 只读操作

| 操作 | 说明 |
|:---|:---|
| `TaskCollection.list` / `TaskDetail.get` | 查询任务 |
| `TaskDetail.previewRouting` | 预览路由 |
| `TaskDetail.preflight` | 预检 |
| `TaskDetail.report` | 查看报告 |
| `RunCollection.list` / `RunDetail.get` / `RunDetail.inspect` | 查询执行 |
| `ApprovalCollection.list` / `ApprovalDetail.get` | 查询审批 |
| `ArtifactCollection.list` / `ArtifactDetail.get` | 查询产物 |
| `ReportCollection.list` / `ReportDetail.get` / `ReportAction.generate` | 查询/生成报告 |

### 受控写入操作

| 操作 | 说明 |
|:---|:---|
| `TaskCollection.create` | 新增 task |
| `TaskAction.run` | 创建 run |
| `TaskAction.retry` | 基于已有 run 重试 |
| `TaskAction.fallback` | 切换到 fallback adapter |
| `ApprovalResolution.resolve` | 审批决议 |
| `ArtifactAction.export` | 持久化产物 |

这些操作必须满足：

- 显式触发（不是某个只读查询的副作用）。
- 写前 schema / public scan / secret scan 校验。
- 写后 consistency validation。
- 失败可回滚。
- 每次写入只作用于 `this operation + this task_id + this request_id + this target`。

### 仍然故意不开放

| 不开放的能力 | 原因 |
|:---|:---|
| 真实 adapter execution | 仍在受控模拟 / dry-run 阶段 |
| 网络访问 / 消息发送 / 外部系统写入 | 安全边界 |
| 删除操作（delete task / delete run / delete artifact） | 审计要求 append-only / 软删除 |
| 批量并发调度 | 不在最小闭环范围内 |
| 自动自愈 / 自动重试策略 | 需要更多运行时数据 |
| 用户鉴权 / 权限系统 | 属于后续协议/服务化层 |
| 数据库持久化 / 缓存 / 索引 | 属于实现层 |

## 与 52、53 的关系

```text
50 (Control Plane State Model)  <- 定义状态对象
  -> 52 (Minimal Orchestration Loop)  <- 把状态对象串成执行闭环
  -> 53 (CLI / Script Command Draft)  <- 把闭环翻译成命令面草案
  -> 51 (Backend-first API Boundary)  <- 本文：把命令背后的资源与操作抽象成稳定边界
```

- 53 是“命令长什么样”的草案；51 是“命令背后依赖什么稳定资源与操作”的定义。
- 同一个 51 操作边界可以被 53 的 CLI 消费，也可以被未来 UI、自动化脚本、服务化接口消费。
- 52 的七步闭环中的每一步都对应 51 中的一个或多个操作；50 的每个状态对象都对应 51 中的一个资源。

## 当前阶段不做什么

本文不实现：

- HTTP / REST / RPC / WebSocket 协议设计。
- 具体 endpoint、path、method、状态码。
- JSON schema 细节（复用已有 schema 风格，不新建）。
- UI 页面、看板、交互流程。
- 数据库选型与持久化。
- 用户鉴权、权限模型、多租户。
- 服务部署、负载均衡、高可用。
- 真实 adapter execution。

本文只定义后端优先的资源与操作边界，让后续协议选择和 UI 设计都有稳定依托。

## 下一步衔接

本文之后，后续可以并行或先后进入：

- **协议层选择**：根据使用场景决定 CLI、本地进程调用、RPC 还是 HTTP。
- **Stage 15：UI / 看板前的后端准备**：按 51 的资源与操作梳理未来“总览页、任务页、执行页、审批页、产物页、报告页”分别需要什么。
- **Stage 16：UI / Control Panel**：在 51 确定的操作边界上长出前端。

但在此之前，中枢台后端已经具备：

- 统一接入语义（48）
- 能力路由语义（49）
- 控制面状态模型（50）
- 最小执行闭环语义（52）
- 命令面草案（53）
- 后端优先 API 边界（51）

这是 UI 和服务化之前需要的最小后端上下文。
