# 50 — Control Plane State Model

## 阶段定位

本文定义中枢运行台应该记录哪些核心状态对象，供 CLI、未来 UI、自动化工作流、审计和回放共同使用。目标不是立刻实现数据库或服务，而是先把状态模型讲清楚，避免后续只剩零散 stdout、聊天记录和临时文件。

## 为什么需要 Control Plane State

如果系统状态只存在于：

- 终端输出
- 聊天上下文
- 某个工具自己的临时日志
- 某个 Agent 的内部记忆

就会带来这些问题：

- 无法统一看“现在跑到哪一步”
- 无法知道为什么被 blocked
- 无法给未来 UI 提供稳定数据源
- 无法做回放、审计、统计和故障排查

因此中枢台必须拥有自己的一层控制面状态，而不是只依赖底层工具的原生输出。

## 这些状态对象从哪里来

控制面状态不是凭空产生的，它由上游路由决策和 adapter 执行共同写入：

- `Task`：由任务提交入口创建，携带 `requested_capability`、assignee、workspace 等业务上下文。
- `Run`：由 `49 — Capability Routing Model` 的输出触发，记录最终选中的 `adapter_id`、`capability`、`operation`、`mode` 以及 routing reason。
- `ApprovalRequest`：由 guardrail preflight 或 routing 的 `requires_approval` 触发，记录审批目标、原因和决议。
- `Artifact`：由 `48 — Adapter Runtime Interface` 的执行结果产出，例如 draft、report、snapshot、exported json。
- `Evidence`：由 guardrail 检查、adapter 执行后校验、或 artifact 持久化动作产生，作为“可以进入下一步”的证明。
- `Event`：记录上述任何一次状态迁移或动作，形成按时间排列的审计流。
- `Report`：基于同一 task 下的 run、artifact、evidence 聚合生成，用于阶段收口。

也就是说，50 是 48 和 49 的执行结果沉淀层；没有 48 的 adapter 语义和 49 的路由决策，控制面状态只会变成无意义的日志堆砌。

## 核心状态对象

### 1. Task

Task 是中枢台中的顶层业务对象，代表一个需要被推进、审查或完成的工作单元。

建议字段：

- `task_id`
- `title`
- `summary`
- `status`
- `requested_capability`
- `assignee`
- `reviewer`
- `workspace`
- `created_at`
- `updated_at`
- `source_channel`
- `priority`
- `labels`

Task 解决的问题是：

- 这件事是什么
- 现在归谁推进
- 当前处于什么状态

### 2. Event

Event 是 Task 的过程性事件流，记录状态变化、审批、验证、导出、写入、失败等动作。

建议字段：

- `event_id`
- `task_id`
- `timestamp`
- `actor`
- `event_type`
- `from_status`
- `to_status`
- `message`
- `artifacts`
- `metadata`

Event 解决的问题是：

- 这件事经历了哪些关键步骤
- 是谁触发了变化
- 哪一步导致 blocked 或 failed

### 3. Run

Run 表示一次具体执行尝试，是 Task / Capability / Adapter 的一次绑定执行记录。

建议字段：

- `run_id`
- `task_id`
- `request_id`
- `adapter_id`
- `capability`
- `operation`
- `mode`
- `status`
- `started_at`
- `ended_at`
- `timeout_seconds`
- `retry_of`
- `fallback_from`

Run 解决的问题是：

- 哪个 adapter 实际执行了哪一次动作
- 这次执行成功、失败、超时还是被取消
- 是否是 fallback 或 retry

### 4. Routing Decision Snapshot（Stage 12 第一版）

`RoutingDecisionSnapshot` 是 Stage 12 控制面状态模型的最小第一拍：它把 Stage 11 的 route/preflight 决策投影成一个稳定、只读、可消费的状态对象，供未来 `Run` / `Event` / API 使用。

它**不是**持久化对象，也不写入 task/event/run ledger；当前只是 ephemeral read model。它的作用是：

- 让上层不需要再解析 `route preview` / `preflight` 的 stdout 就能拿到结构化决策。
- 为 future UI / API 提供与 CLI 一致的 routing decision 视图。
- 明确 routing 状态与 guardrail 状态的分层（`routing.status` vs `guardrail.status`）。

核心字段：

- `schema_version`: `"control-plane/routing-decision/v1"`
- `snapshot_id`: 对 canonical safe payload 的 SHA-256 内容哈希，确定性生成。
- `status`: routing 结果状态（`pass` / `blocked` / `needs_input` / `needs_approval` / `error`）。
- `routing`: 请求 capability/mode、选中 adapter/operation、risk、approval/dry-run 约束、routing reason、fallback adapter ids。
- `constraints`: adapter kind、preflight checks、可选 `routing_constraints`。
- `trace`: 可选 compact decision trace（`--explain` 时包含）。
- `guardrail`: preflight snapshot 特有的 guardrail 摘要（status / finding_count / blocking_rule_ids）；route snapshot 为 null。
- `source`: `task_id`、`request_id` 等安全标识。

生成方式：

- `orchestration route snapshot` 调用 `preview_route`，将 `RoutePreviewResult` 直接投影为 `RoutingDecisionSnapshot`。
- `orchestration preflight --snapshot` 调用 `check_preflight`，将 `PreflightResult` 直接投影为 `RoutingDecisionSnapshot`，并附加 guardrail 层。

安全边界：snapshot 不暴露完整 input/output schema、原始 target、policy 原文、finding message 或凭据；guardrail 只保留规则 id 列表与计数。

### 5. Approval Request

Approval Request 用于承接需要人工确认的动作。

建议字段：

- `approval_id`
- `task_id`
- `run_id`
- `target`
- `action`
- `reason`
- `status`
- `requested_at`
- `resolved_at`
- `resolver`

Approval 解决的问题是：

- 哪一步在等人工
- 人工批准还是拒绝了
- 审批作用于哪个 run / task

### 5. Artifact

Artifact 是运行过程中产出的结构化落盘物或引用物。

常见类型：

- draft file
- report file
- screenshot
- exported json
- validation result
- scan summary
- adapter response snapshot

建议字段：

- `artifact_id`
- `task_id`
- `run_id`
- `artifact_type`
- `path_or_ref`
- `created_at`
- `producer`
- `summary`
- `safe_to_preview`

Artifact 解决的问题是：

- 产物在哪里
- 哪次执行生成了它
- 是否适合直接展示给人看

### 6. Evidence

Evidence 用于表达“为什么这一步可以被视为完成 / 通过 / 合规”。

常见类型：

- schema validation passed
- public scan passed
- ledger check passed
- approval granted
- artifact persisted
- completion proof linked

建议字段：

- `evidence_id`
- `task_id`
- `run_id`
- `evidence_type`
- `summary`
- `artifact_refs`
- `created_at`

Evidence 解决的问题是：

- 为什么可以宣称完成
- 完成依据指向哪里

### 7. Report

Report 是面向人类或上层系统的摘要对象，用于阶段收口和总览。

建议字段：

- `report_id`
- `task_id`
- `scope`
- `status_summary`
- `key_findings`
- `artifact_refs`
- `evidence_refs`
- `next_action`
- `created_at`

Report 解决的问题是：

- 现在最重要的结论是什么
- 下一步应该做什么

## 状态关系

这些对象之间的关系可简化为：

```text
Task
  -> Event[]
  -> Run[]
      -> ApprovalRequest[]
      -> Artifact[]
      -> Evidence[]
  -> Report[]
```

含义：

- Task 是顶层
- Event 记录过程
- Run 记录具体执行尝试
- Approval / Artifact / Evidence 依附于 Run
- Report 面向汇总和收口

## 最小链路样例：从任务意图到 Report

以下是一个后端视角的完整链路，说明 `49 — Capability Routing Model` 和 `48 — Adapter Runtime Interface` 如何共同产出 `50` 中的状态对象。本样例不进入 API / HTTP / UI，只展示状态如何沉淀。

### 任务意图

```text
task_type: coding_request
requested_capability: dispatch.agent.coding
title: 为 workspace 内一个代码修改请求生成 dry-run draft
workspace: <repo-root>
execution_mode: dry-run
```

### 1. Capability Routing

`49` 根据 `requested_capability` 和可用 adapter 做路由：

```text
selected_adapter_id: kimi-code-acp
selected_capability: dispatch.agent.coding
operation: edit_file
requires_approval: false
requires_dry_run: true
requires_review: true
fallback_adapter_ids: [omp-acp, claude-code-acp]
routing_reason: 默认优先 Kimi Code；当前任务在工作区内、风险等级 medium，dry-run 模式无需审批
```

### 2. Guardrail Preflight

路由结果被提交给 guardrail 内核：

```text
path_check: PASS（目标路径在工作区内）
secret_scan: PASS（无命中）
action_rule: 允许 dry-run，commit 阶段需审批
preflight_result: ALLOWED_WITH_CONSTRAINTS
```

### 3. Adapter Execution

`48` 组装统一 request 并执行（当前仍为受控模拟，不触发真实外部执行）：

```text
request_id: req-20260707-001
run_id: run-20260707-001
task_id: task-20260707-001
adapter_id: kimi-code-acp
capability: dispatch.agent.coding
operation: edit_file
mode: dry-run
input: {target: agent_runtime/loader.py, instruction: 生成一个路径归一化函数修改草案}
```

### 4. 状态沉淀

执行结果写入控制面状态：

**Task**

```text
task_id: task-20260707-001
status: running
requested_capability: dispatch.agent.coding
assignee: kimi-code-acp
```

**Run**

```text
run_id: run-20260707-001
task_id: task-20260707-001
request_id: req-20260707-001
adapter_id: kimi-code-acp
capability: dispatch.agent.coding
operation: edit_file
mode: dry-run
status: completed
fallback_from: null
```

**Event**

```text
event_id: evt-20260707-001
task_id: task-20260707-001
actor: orchestration_hub
event_type: run_completed
message: kimi-code-acp dry-run 完成，等待 review
```

**Artifact**

```text
artifact_id: art-20260707-001
task_id: task-20260707-001
run_id: run-20260707-001
artifact_type: draft_file
path_or_ref: drafts/runtime/task-20260707-001/loader-normalize.envelope.json
producer: kimi-code-acp
safe_to_preview: true
```

**Evidence**

```text
evidence_id: evi-20260707-001
task_id: task-20260707-001
run_id: run-20260707-001
evidence_type: public_scan_passed
summary: 草案通过公开发布风险扫描
artifact_refs: [art-20260707-001]
```

### 5. Report 收口

```text
report_id: rep-20260707-001
task_id: task-20260707-001
scope: single_run
status_summary: dry-run 完成，待 review 后 commit
key_findings: [路径在工作区内, 无敏感信息泄露, 已生成 draft]
artifact_refs: [art-20260707-001]
evidence_refs: [evi-20260707-001]
next_action: 人工 review draft，确认后执行 commit 或驳回
```

这个样例展示了 47-50 这组文档的衔接：路由决策来自 49，adapter 语义来自 48，所有状态对象最终在 50 中沉淀成可审计、可回放、可被未来 UI 消费的格式。这里刻意把结果收束在 dry-run draft / artifact / evidence 层，而不是承诺当前阶段已经放开真实外部执行。

## 与当前仓库的关系

当前仓库已经部分具备这些基础：

- `task` / `event` ledger
- adapter execution envelope
- runtime report
- controlled write artifact
- completion verification

但缺的是把这些对象上升为统一的“控制面状态模型”。

本文的作用，就是把现在零散分布在 ledger、draft、report、check result 里的状态对象统一到一张后端心智图上。

## 对未来 UI 的意义

未来 UI 面板其实就是读取这些状态对象：

- 任务面板 -> Task / Event
- 执行面板 -> Run / ApprovalRequest
- 产物面板 -> Artifact
- 完成证明面板 -> Evidence
- 总览面板 -> Report

所以本阶段虽然不做 UI，但必须现在就把状态对象设计出来。

## 当前阶段不做什么

本文不实现：

- 数据库选型
- HTTP 服务
- 前端页面
- 实时推送
- 权限系统

本文只定义中枢台的后端状态模型。

## 下一步衔接

本文之后建议继续补：

- `51 — Backend-first API Boundary`

这样未来无论先做 CLI、脚本接口还是 Web 控制台，都能围绕统一状态对象暴露可操作边界。
