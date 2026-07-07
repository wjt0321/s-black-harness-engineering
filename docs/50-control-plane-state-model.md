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

### 4. Approval Request

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
