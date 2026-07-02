# 04 — 任务状态模型

## 这份文档解决什么问题

Agent Runtime 不能只知道“谁在干活”，还必须知道每个任务当前处于什么状态、为什么进入这个状态、下一步该由谁处理、完成时有什么证据。

任务状态模型的目标是让任务从提交到完成的过程可追踪、可恢复、可审计。

第一版不做复杂项目管理系统，只定义最小可用状态机和账本格式。

## 核心状态

第一版只保留五个核心状态：

| 状态 | 中文含义 | 说明 |
|:---|:---|:---|
| `planned` | 已计划 | 任务已记录，但还没开始执行 |
| `running` | 执行中 | 已分配执行者，正在推进 |
| `blocked` | 被阻塞 | 因缺权限、缺信息、工具失败、等待用户确认等原因暂停 |
| `finished` | 已完成 | 任务完成，并有完成证据 |
| `failed` | 已失败 | 任务明确失败，短期内不继续自动重试 |

## 状态流转

推荐的状态流转如下：

```text
planned
  -> running
  -> finished

planned
  -> blocked
  -> running
  -> finished

running
  -> blocked
  -> running

running
  -> failed

blocked
  -> failed
```

不建议直接跳转：

- `planned -> finished`：除非是纯记录型任务，否则缺少执行过程。
- `failed -> running`：失败后如果要继续，应新建恢复事件或新任务，避免覆盖失败原因。
- `finished -> running`：已完成任务不要复活；如需返工，应创建 follow-up 任务。

## 状态定义细则

### planned

表示任务已经进入账本，但尚未开始。

典型场景：

- 用户提出后，先记录到 backlog。
- 长任务拆分出子任务，但还没派发。
- 需要排队等待前置任务完成。

必须字段：

- `id`
- `title`
- `status`
- `created_at`
- `created_by`

### running

表示任务已经开始执行。

典型场景：

- Orchestrator自己正在处理。
- 已委派给Media Agent、Memory Agent、Kimi、Claude、OMP 等。
- 已启动某个脚本、适配器或检查流程。

进入 running 时应记录：

- `assignee`
- `started_at`
- `current_step`
- `source`：任务来源，如 console、飞书、cron、CLI。

### blocked

表示任务暂时不能继续。

常见阻塞原因：

| reason | 说明 |
|:---|:---|
| `need_user_approval` | 等待用户明确授权 |
| `need_user_input` | 缺少用户提供的信息 |
| `permission_denied` | 权限不足 |
| `tool_failed` | 工具失败 |
| `network_error` | 网络异常 |
| `policy_blocked` | 被 policy 门禁拦截 |
| `external_dependency` | 等待外部系统或他人处理 |
| `unclear_scope` | 范围不清，需要重新确认 |

blocked 不是失败。它表示：任务还有价值，但当前不能继续自动推进。

进入 blocked 时必须记录：

- `blocked_reason`
- `blocked_message`
- `next_action`
- `needs_user`：是否需要用户介入。

### finished

表示任务完成，且至少有一种完成证据。

完成证据可以是：

| evidence | 说明 |
|:---|:---|
| `file_written` | 文件已落盘 |
| `test_output` | 测试或脚本输出 |
| `diff_review` | 已审查关键差异 |
| `screenshot` | 截图或网页快照 |
| `external_confirmation` | 外部系统确认 |
| `blocker_report` | 如果任务目标是排查，也可用明确 blocker 作为交付 |

进入 finished 时必须记录：

- `finished_at`
- `summary`
- `evidence`
- `artifacts`：产物路径或外部链接。

### failed

表示任务已经失败，且不应在没有新决策的情况下继续自动重试。

典型场景：

- 方案被证明不可行。
- 外部依赖长期不可用。
- 连续多次工具失败。
- 任务目标已过期。
- 用户取消任务。

进入 failed 时必须记录：

- `failed_at`
- `failure_reason`
- `summary`
- `recommendation`：后续建议。

## 任务记录字段

第一版推荐任务对象结构：

```json
{
  "id": "task-20260702-001",
  "title": "设计任务状态模型",
  "status": "running",
  "created_at": "2026-07-02T21:55:00+08:00",
  "updated_at": "2026-07-02T21:58:00+08:00",
  "created_by": "user",
  "source": "console",
  "assignee": "s-black",
  "priority": "normal",
  "tags": ["agent-runtime", "task-ledger"],
  "current_step": "起草状态模型文档",
  "summary": "定义 planned/running/blocked/finished/failed 五种状态。",
  "artifacts": ["docs/04-task-state-model.md"],
  "evidence": [],
  "blocked_reason": null,
  "blocked_message": null,
  "next_action": "补充 JSONL 样例",
  "parent_id": null
}
```

## 事件记录字段

任务对象代表“当前状态”，事件记录代表“发生过什么”。

建议每次状态变化都追加事件，不覆盖历史。

```json
{
  "event_id": "evt-20260702-001",
  "task_id": "task-20260702-001",
  "timestamp": "2026-07-02T21:58:00+08:00",
  "actor": "s-black",
  "event_type": "status_changed",
  "from_status": "planned",
  "to_status": "running",
  "message": "开始起草任务状态模型。",
  "artifacts": []
}
```

事件类型建议：

| event_type | 说明 |
|:---|:---|
| `created` | 创建任务 |
| `status_changed` | 状态变化 |
| `assigned` | 分配执行者 |
| `progress` | 普通进展 |
| `blocked` | 进入阻塞 |
| `unblocked` | 解除阻塞 |
| `artifact_added` | 增加产物 |
| `evidence_added` | 增加完成证据 |
| `finished` | 完成任务 |
| `failed` | 任务失败 |

## JSONL 还是 SQLite

第一版推荐使用 **JSONL**，暂不使用 SQLite。

原因：

1. 文件可直接查看，方便早期调试。
2. 追加写入简单，不容易误覆盖。
3. 适合 Git diff 和人工审查。
4. 后续可以无损迁移到 SQLite。

推荐文件：

| 文件 | 用途 |
|:---|:---|
| `tasks/tasks.jsonl` | 任务当前快照，一行一个任务 |
| `tasks/events.jsonl` | 任务事件流，一行一个事件 |
| `tasks/progress.md` | 人类可读进度账本 |

注意：早期可以只维护 `progress.md` 和样例 JSONL，不急着把真实任务全部写入 JSONL。

## task status 输出格式

未来 CLI 查询任务时，建议输出简洁状态卡片。

```text
任务：task-20260702-001
标题：设计任务状态模型
状态：running
执行者：s-black
当前步骤：起草状态模型文档
产物：docs/04-task-state-model.md
下一步：补充 JSONL 样例
```

机器可读输出则使用 JSON：

```json
{
  "id": "task-20260702-001",
  "title": "设计任务状态模型",
  "status": "running",
  "assignee": "s-black",
  "current_step": "起草状态模型文档",
  "artifacts": ["docs/04-task-state-model.md"],
  "next_action": "补充 JSONL 样例"
}
```

## 与 Policy Schema 的关系

任务状态模型和 Policy Schema 互相配合：

- 如果命中 `block` 级 policy，任务应进入 `blocked`，原因是 `policy_blocked`。
- 如果命中 `require_user_approval`，任务应进入 `blocked`，原因是 `need_user_approval`。
- 如果 completion rule 要求完成证据但证据不足，任务不能进入 `finished`。
- 如果 postflight 验证失败，任务可以回到 `running` 或进入 `blocked`。

## 第一版落地范围

Stage 2 第一版交付物：

1. `docs/04-task-state-model.md`：任务状态模型说明。
2. `tasks/task.schema.json`：任务对象 JSON Schema 草案。
3. `tasks/event.schema.json`：事件对象 JSON Schema 草案。
4. `tasks/examples.jsonl`：样例任务记录。
5. `tasks/events.examples.jsonl`：样例事件记录。

## 暂不解决的问题

- 不做复杂依赖图。
- 不做甘特图或项目管理 UI。
- 不接入真实后台任务队列。
- 不实现自动重试策略。
- 不强制所有日常聊天都进任务账本。
