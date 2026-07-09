# 54 — UI / 看板前的后端准备

## 阶段定位

本文是 Stage 15 的设计前置文档，目标是在不进入前端实现的前提下，先梳理清楚未来看板/面板需要哪些后端资源、聚合视图、摘要字段、详情字段和操作入口。

51 已经定义了稳定的资源模型与操作模型；本文要做的，是把这些资源和操作映射到未来 UI 的**页面视角**，让后端知道该为每个页面准备什么样的数据形态，也让前端设计有明确的数据边界可依。

因此本文不是 UI 设计文档，而是**后端为 UI 准备数据的说明书**。

## 这份文档不是什么

- **不是 UI 设计稿**：不写组件、布局、颜色、字体、交互流程。
- **不是前端状态管理文档**：不写 store、reducer、缓存策略。
- **不是产品 PRD**：不写用户故事、业务目标、北极星指标。
- **不是协议设计**：不写 REST path、RPC method、WebSocket event。
- **不是数据库设计**：不写表结构、索引、分片。

本文只回答：未来看板有几个核心页面，每个页面需要读哪些资源、做哪些聚合、暴露哪些操作。

## 页面与资源映射总表

| 页面 | 主要资源 | 附属对象 | 聚合视图 / Read Model | 视图类型 |
|:---|:---|:---|:---|:---:|
| 总览页 | Task / Run / Approval / Report | — | `OverviewSummary` / `RecentRunList` / `PendingApprovalList` / `LatestReportSummary` | 只读 |
| 任务页 | Task | Event | `TaskListItem` / `TaskDetailWithEvents` | 只读 + 写入入口 |
| 执行页 | Run | Artifact / Evidence | `RunListItem` / `RunDetailWithArtifactsAndEvidence` | 只读 + 写入入口 |
| 审批页 | Approval | Task / Run | `ApprovalListItem` / `ApprovalDetail` | 只读 + 写入入口 |
| 产物页 | Artifact | Run / Task | `ArtifactListItem` / `ArtifactDetail` | 只读 + 写入入口 |
| 报告页 | Report | Task / Run / Artifact / Evidence | `ReportListItem` / `ReportDetail` | 只读 |

## 各页面后端准备详情

### 1. 总览页（Overview / Dashboard）

目标：让用户一眼看清中枢台当前整体状态。

#### 依赖资源

- `Task`（按状态聚合）
- `Run`（最近执行）
- `Approval`（待审批）
- `Report`（最新报告）

#### 聚合视图 / Read Model

| Read Model | 来源资源 | 字段摘要 |
|:---|:---|:---|
| `OverviewSummary` | Task / Run / Approval / Report | `total_tasks`、`blocked_tasks`、`running_tasks`、`pending_approvals`、`latest_next_action` |
| `TaskStatusSummary` | Task | `planned_count`、`running_count`、`blocked_count`、`finished_count`、`failed_count` |
| `RecentRunList` | Run | 最近 N 条 run 的 `run_id`、`task_id`、`adapter_id`、`capability`、`status`、`started_at` |
| `PendingApprovalList` | Approval | 待审批的 `approval_id`、`task_id`、`action`、`requested_at` |
| `LatestReportSummary` | Report | 最新报告的 `report_id`、`task_id`、`status_summary`、`next_action` |

#### 操作入口

- 只读：`refresh`（重新拉取聚合）。
- 无写入操作；所有写入通过详情页完成。

#### 与 50/51 的关系

- 所有字段都可由 50 的状态对象聚合得到。
- 对应 51 的只读操作：`TaskCollection.list`、`RunCollection.list`、`ApprovalCollection.list`、`ReportCollection.list`。

---

### 2. 任务页（Task List / Task Detail）

目标：浏览所有任务，查看单个任务的完整生命周期和事件流。

#### 依赖资源

- `Task`（顶层）
- `Event`（附属，按 task 时序查询）

#### 列表摘要字段

| 字段 | 来源 |
|:---|:---|
| `task_id` | `Task.task_id` |
| `title` | `Task.title` |
| `status` | `Task.status` |
| `requested_capability` | `Task.requested_capability` |
| `assignee` | `Task.assignee` |
| `created_at` | `Task.created_at` |
| `updated_at` | `Task.updated_at` |

#### 详情字段

| 字段 | 来源 |
|:---|:---|
| `summary` / `workspace` / `priority` / `labels` | `Task` |
| `event_timeline[]` | `Event`：按 `timestamp` 排序，含 `event_type`、`from_status`、`to_status`、`actor`、`message` |
| `latest_report_id` | 由 Report 聚合查询得到 |

#### 操作入口

| 操作 | 类型 | 对应 51 操作 | 对应 53 命令 |
|:---|:---:|:---|:---|
| 查看任务列表 | 只读 | `TaskCollection.list` | `orchestration task list`（已存在） |
| 查看任务详情 | 只读 | `TaskDetail.get` | `orchestration task get`（已存在） |
| 创建任务 | 受控写入 | `TaskCollection.create` | `orchestration task submit`（草案） |
| 预览路由 | 只读 | `TaskDetail.previewRouting` | `orchestration route preview`（草案） |
| 执行预检 | 只读 | `TaskDetail.preflight` | `orchestration preflight` |
| 执行 dry-run / commit | 受控写入 | `TaskAction.run` | `orchestration run` |
| 重试 | 受控写入 | `TaskAction.retry` | `orchestration run --retry` |
| 回退 | 受控写入 | `TaskAction.fallback` | `orchestration run --fallback-to` |
| 查看报告 | 只读 | `TaskDetail.report` | `orchestration report` |

#### 与 50/51 的关系

- `Task` 和 `Event` 来自 50。
- 列表/详情读取对应 51 的 `TaskCollection.list` / `TaskDetail.get`。
- 事件流是 `TaskDetail.get` 返回的 read model，不是独立页面资源。

---

### 3. 执行页（Run List / Run Detail）

目标：查看每次具体执行尝试的状态、产物和证据。

#### 依赖资源

- `Run`（顶层）
- `Artifact` / `Evidence`（附属，按 run 查询）

#### 列表摘要字段

| 字段 | 来源 |
|:---|:---|
| `run_id` | `Run.run_id` |
| `task_id` | `Run.task_id` |
| `adapter_id` | `Run.adapter_id` |
| `capability` | `Run.capability` |
| `operation` | `Run.operation` |
| `mode` | `Run.mode` |
| `status` | `Run.status` |
| `started_at` / `ended_at` | `Run` |
| `retry_of` / `fallback_from` | `Run` |

#### 详情字段

| 字段 | 来源 |
|:---|:---|
| 基础 run 字段 | `Run` |
| `artifacts[]` | `Artifact`：`artifact_id`、`artifact_type`、`producer`、`summary`、`safe_to_preview` |
| `evidence[]` | `Evidence`：`evidence_id`、`evidence_type`、`summary`、`artifact_refs` |
| `guardrail_status` | 由 Run 关联的 preflight 结果聚合 |

#### 操作入口

| 操作 | 类型 | 对应 51 操作 | 对应 53 命令 |
|:---|:---:|:---|:---|
| list | 只读 | `RunCollection.list`（当前为 envelope-scoped read model，非持久 Run 存储） | `orchestration run list`（已存在） |
| inspect | 只读 | `RunDetail.inspect` | `orchestration run inspect`（已存在，`runtime report` 薄包装） |
| 重试 | 受控写入 | `TaskAction.retry` | `orchestration run --retry`（草案） |
| 回退 | 受控写入 | `TaskAction.fallback` | `orchestration run --fallback-to`（草案） |
| 取消 | 暂不开放 | — | — |

#### 与 50/51 的关系

- `Run`、`Artifact`、`Evidence` 来自 50。
- 对应 51 的 `RunCollection.list`、`RunDetail.get`、`RunDetail.inspect`。

---

### 4. 审批页（Approval List / Approval Detail）

目标：查看所有需要人工确认的动作，并做出决议。

#### 依赖资源

- `Approval`（顶层）
- `Task` / `Run`（用于展示上下文）

#### 列表摘要字段

| 字段 | 来源 |
|:---|:---|
| `approval_id` | `Approval.approval_id` |
| `task_id` | `Approval.task_id` |
| `run_id` | `Approval.run_id` |
| `target` | `Approval.target` |
| `action` | `Approval.action` |
| `status` | `Approval.status` |
| `requested_at` | `Approval.requested_at` |
| `resolved_at` | `Approval.resolved_at` |
| `resolver` | `Approval.resolver` |

#### 详情字段

| 字段 | 来源 |
|:---|:---|
| 基础 approval 字段 | `Approval` |
| `reason` | `Approval.reason` |
| `scope` | `Approval.scope`（task_id / adapter_id / operation / target） |
| `related_task_link` | `Task` |
| `related_run_link` | `Run` |

#### 操作入口

| 操作 | 类型 | 对应 51 操作 | 对应 53 草案命令 |
|:---|:---:|:---|:---|
| list | 只读 | `ApprovalCollection.list`（当前为 envelope-scoped read model，非持久 Approval 存储） | `orchestration approval list`（已存在） |
| get | 只读 | `ApprovalDetail.get`（当前为 envelope-scoped read model） | `orchestration approval get`（已存在） |
| resolve | 受控写入 | `ApprovalResolution.resolve` | `orchestration approval resolve`（草案，未实现） |
| 查看关联 task/run | 只读 | `TaskDetail.get` / `RunDetail.get` | `orchestration task get` / `orchestration inspect` |

#### 与 50/51 的关系

- `Approval` 来自 50 的 `ApprovalRequest`。
- 对应 51 的 `ApprovalCollection.list`、`ApprovalDetail.get`、`ApprovalResolution.resolve`。

---

### 5. 产物页（Artifact List / Artifact Detail）

目标：浏览运行产物，查看产物元数据和可预览内容。

#### 依赖资源

- `Artifact`（顶层）
- `Run` / `Task`（用于上下文）

#### 列表摘要字段

| 字段 | 来源 |
|:---|:---|
| `artifact_id` | `Artifact.artifact_id` |
| `task_id` / `run_id` | `Artifact` |
| `artifact_type` | `Artifact.artifact_type` |
| `producer` | `Artifact.producer` |
| `created_at` | `Artifact.created_at` |
| `safe_to_preview` | `Artifact.safe_to_preview` |

#### 详情字段

| 字段 | 来源 |
|:---|:---|
| `summary` | `Artifact.summary` |
| `path_or_ref` | `Artifact.path_or_ref`（安全引用，不直接暴露完整 payload） |
| `preview` | 仅在 `safe_to_preview == true` 时提供脱敏摘要 |
| `related_run_link` | `Run` |

#### 操作入口

| 操作 | 类型 | 对应 51 操作 | 对应 53 草案命令 |
|:---|:---:|:---|:---|
| list | 只读 | `ArtifactCollection.list`（当前为 envelope-scoped read model，非持久 Artifact 存储） | `orchestration artifact list`（已存在） |
| get | 只读 | `ArtifactDetail.get`（当前为 envelope-scoped read model） | `orchestration artifact get`（已存在） |
| 导出/持久化 | 受控写入 | `ArtifactAction.export` | `runtime draft export --commit` |

#### 与 50/51 的关系

- `Artifact` 来自 50。
- 对应 51 的 `ArtifactCollection.list`、`ArtifactDetail.get`、`ArtifactAction.export`。

---

### 6. 报告页（Report List / Report Detail）

目标：查看阶段收口摘要，获取下一步行动建议。

#### 依赖资源

- `Report`（顶层）
- `Task` / `Run` / `Artifact` / `Evidence`（聚合来源）

#### 列表摘要字段

| 字段 | 来源 |
|:---|:---|
| `report_id` | `Report.report_id` |
| `task_id` | `Report.task_id` |
| `scope` | `Report.scope` |
| `status_summary` | `Report.status_summary` |
| `created_at` | `Report.created_at` |

#### 详情字段

| 字段 | 来源 |
|:---|:---|
| `key_findings[]` | `Report.key_findings` |
| `artifact_refs[]` | `Report.artifact_refs`（指向 Artifact） |
| `evidence_refs[]` | `Report.evidence_refs`（指向 Evidence） |
| `next_action` | `Report.next_action` |
| `related_task_link` | `Task` |

#### 操作入口

| 操作 | 类型 | 对应 51 操作 | 对应 53 草案命令 |
|:---|:---:|:---|:---|
| generate | 只读（聚合计算） | `ReportAction.generate` | `orchestration report` |
| 查看 | 只读 | `ReportDetail.get` | `orchestration report` |

#### 与 50/51 的关系

- `Report` 来自 50。
- 对应 51 的 `ReportCollection.list`、`ReportDetail.get`、`ReportAction.generate`。
- `generate` 是只读聚合；如果需要缓存 Report，缓存写入应走单独的受控写入规则。

## 顶层资源 vs 页面聚合视图

### 顶层资源

来自 51 的持久资源，具有独立标识和生命周期：

- `Task`
- `Run`
- `Approval`
- `Artifact`
- `Report`

这些资源会被持久化到 ledger / draft / envelope 中，是后端真正的数据实体。

### 页面聚合视图 / Read Model

为了服务页面展示而临时组合的数据形态，**不是持久资源**，例如：

- `OverviewSummary`：由 Task / Run / Approval / Report 聚合得到。
- `TaskDetailWithEvents`：由 Task + 其 Event 流组成。
- `RunDetailWithArtifactsAndEvidence`：由 Run + 其 Artifact / Evidence 组成。
- `PendingApprovalList`：由 Approval 按 status 过滤得到。
- `LatestReportSummary`：由 Report 按时间排序取最新。

关键区别：

| 维度 | 顶层资源 | 聚合视图 / Read Model |
|:---|:---|:---|
| 是否有独立持久身份 | 是 | 否 |
| 是否可被 ledger 回放 | 是 | 否（它是资源的投影） |
| 是否跨多个资源 | 否（通常） | 是 |
| 是否随页面需求变化 | 相对稳定 | 可能因页面需求调整 |
| 示例 | `Task`、`Run` | `OverviewSummary`、`TaskDetailWithEvents` |

这意味着：未来 UI 改页面布局时，通常只需要改 Read Model 的字段组合，不需要改顶层资源本身。

## CLI 输出与页面数据的映射

### 已存在命令可直接提供雏形

| 页面数据 | 现有 CLI 命令 |
|:---|:---|
| 总览聚合 | `python -m agent_runtime.cli orchestration overview` |
| 任务列表 | `python -m agent_runtime.cli orchestration task list` |
| Task 详情 + 事件时间线 | `python -m agent_runtime.cli orchestration task get` |
| Task 详情 / 事件流（原始） | `python -m agent_runtime.cli task status`、`task events` |
| Run 检查 / 聚合报告 | `python -m agent_runtime.cli orchestration run inspect` |
| Run 列表（envelope-scoped） | `python -m agent_runtime.cli orchestration run list` |
| Run 关联的 envelope 摘要 | `python -m agent_runtime.cli runtime draft inspect` |
| 聚合报告 | `python -m agent_runtime.cli runtime report` |
| Approval 状态 | `python -m agent_runtime.cli adapter approval check` |
| Gate 状态 | `python -m agent_runtime.cli runtime gate check` |

### 仍需要草案命令补充

| 页面数据 | 53 草案命令 |
|:---|:---|
| 执行列表 | `orchestration run list`（已存在，envelope-scoped） |
| 重试 / 回退 | `orchestration run --retry`、`orchestration run --fallback-to` |
| 审批列表/详情 | `orchestration approval list`（已存在，envelope-scoped）、`orchestration approval get`（已存在，envelope-scoped） |
| 产物列表/详情 | `orchestration artifact list`（已存在，envelope-scoped）、`orchestration artifact get`（已存在，envelope-scoped） |
| 报告列表/生成 | `orchestration report list`、`orchestration report` |

说明：

- 现有 CLI 命令的输出是人类/JSON 摘要，已经脱敏，可以直接作为页面数据的雏形。
- 53 的草案命令未来可能需要增加 `--json` 输出，以便页面/脚本消费。
- 51 的操作边界保持不变，只是命令形态可能随页面需求细化。

## 只读视图与写入操作入口

### 纯只读页面/视图

| 页面/视图 | 原因 |
|:---|:---|
| 总览页 | 聚合展示，不直接修改数据 |
| 报告页 | Report 是聚合产物，generate 不修改底层资源 |
| Artifact 预览 | 预览是只读渲染 |
| Event 时间线 | 审计流只追加不修改 |
| Evidence 列表 | 完成证明只读展示 |

### 允许写入入口的页面

| 页面 | 写入操作 | 说明 |
|:---|:---|:---|
| 任务页 | 创建任务、执行 run、重试、回退 | 所有写入都受 guardrail preflight 约束 |
| 执行页 | 重试、回退 | 基于已有 Run 发起新 Run |
| 审批页 | resolve | 需要显式 decision 和 reason |
| 产物页 | export | 持久化 draft 到受控路径 |

### 仍然不开放的操作入口

| 操作 | 原因 |
|:---|:---|
| 删除 task / run / artifact | 审计要求 append-only / 软删除 |
| 直接修改 event / evidence | 破坏审计链 |
| 绕过审批直接 commit | 违反受控写入原则 |
| 真实 adapter execution | 仍在 dry-run / 受控模拟阶段 |

## Guardrail 在页面中的体现

Guardrail 不是独立页面，而是**贯穿各页面的状态显示和写入约束层**。

### 显示方式

| 场景 | 页面体现 |
|:---|:---|
| Task 被 blocked | 任务列表/详情显示 `blocked` 状态 + `blocked_reason` |
| Run 需要审批 | 执行页/审批页显示 `NEEDS_APPROVAL` + 关联 Approval |
| Run 被强制 dry-run | 执行页显示 `ALLOWED_WITH_CONSTRAINTS` + `mode forced to dry-run` |
| Artifact 通过 public scan | 产物页显示 `secret_scan_passed` / `public_scan_passed` evidence |
| Report 提示 next_action | 报告页/总览页显示 `next_action` |

### 写入约束

- 每个写入操作入口在点击后，后端必须先跑 guardrail preflight。
- UI 不应自行判断“能不能执行”，而应显示 guardrail 返回的结果和原因。
- 对于 `NEEDS_APPROVAL`，UI 只应提供“提交审批”入口，而不是直接执行。

这就是“guardrail 是长期内核，但不阻塞主线”在 UI 准备阶段的体现：

- guardrail 不决定页面有哪些；
- guardrail 决定页面上的写入操作能不能按预期执行。

## 与 50/51/52/53 的关系

```text
50 (Control Plane State Model)
  -> 51 (Backend-first API Boundary)
  -> 52 (Minimal Orchestration Loop)
  -> 53 (CLI / Script Command Draft)
  -> 54 (Backend Preparation before UI)  <- 本文：把 51 的资源/操作映射到未来页面
```

- 50 提供状态对象。
- 51 提供资源与操作边界。
- 52 提供执行闭环语义。
- 53 提供命令面草案。
- 54 提供页面视角下的数据需求与操作入口映射。

## 当前阶段不做什么

本文不实现：

- 前端组件、布局、样式、交互。
- 前端状态管理（store、reducer、缓存）。
- 具体页面路由或 URL 设计。
- 协议选择（REST / RPC / WebSocket）。
- 数据库表结构或索引。
- 用户鉴权、权限模型、多租户。
- 真实 adapter execution。
- 实时推送或订阅机制。

本文只定义未来看板需要的数据准备边界，让 Stage 16 的 UI 实现有明确的后端依托。

## 下一步衔接

本文之后，后续可以进入：

- **Stage 16：UI / Control Panel**：在 54 定义的页面数据边界上设计前端。
- **协议层落地**：根据 UI / CLI / 自动化需求，选择 REST / RPC / 本地进程调用等协议。
- **实现层细化**：为每个 Read Model 设计查询路径、缓存策略、分页格式。

但在此之前，中枢台已经具备：

- 统一接入语义（48）
- 能力路由语义（49）
- 控制面状态模型（50）
- 后端优先 API 边界（51）
- 最小执行闭环语义（52）
- 命令面草案（53）
- UI 前的后端准备（54）

这是开始真正 UI 设计之前需要的最小后端上下文。
