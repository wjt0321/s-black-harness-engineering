# 63 — Orchestration Task Submit Created Event 设计

## 阶段定位

`docs/62-orchestration-task-submit-controlled-write-design.md` 已经把 `orchestration task submit --dry-run / --commit` 的第一版入口边界定清楚，并且当前第一版实现已经落地：

- `orchestration task submit --dry-run`：只读校验 candidate task。
- `orchestration task submit --commit`：只向 task ledger 追加 task snapshot。

但这还没有完全补齐 `docs/51-backend-first-api-boundary.md` 中 `TaskCollection.create` 的语义。

在 51 里，`TaskCollection.create` 对应的是：

- **A：新 Task**
- **B：初始 Event**

而当前 orchestration 层只完成了 A，没有完成 B。这导致 control-plane 入口虽然已经能创建 task，但在 event timeline / audit trail / read model 一致性上，仍然存在一个明显缺口：

- `orchestration task list` / `task get` 可以看到 task；
- 但 `task events` 或后续依赖事件流的视角，不一定能看到与创建动作对应的初始 `created` 事件；
- 结果是“任务存在，但入口事件缺失”。

因此本文档的目标，是把 `orchestration task submit --commit` 从 A-only 升级为 **A+B controlled write**：

- A：向 task ledger 追加新 task snapshot。
- B：向 event ledger 追加 `created` event。
- A+B：必须 all-or-nothing，并且对 read model 保持一致。

本文档是下一拍进入实现前的 design gate，不放开 retry / fallback，不放开真实 adapter execution，不引入 DB / service / UI。

## 为什么先做这个，而不是直接 retry / fallback

当前 orchestration 主线中，后续至少有两类工作都还没做：

- 入口补齐：`orchestration task submit` A+B
- 恢复性能力：`orchestration run --retry` / `orchestration run --fallback-to`

优先级上，`task submit` 的 A+B 更应该先落地，原因有四点。

### 1. 它仍然是入口级写入，不是恢复性写入

`retry` / `fallback` 都建立在：

- 已有 task
- 已有 run
- 已有失败或阻断上下文
- 已有 routing / approval / artifact / event trail

之上。

而 `task submit` 是整个 control plane 的入口动作。

如果入口动作自己都还没有形成完整的 A+B 审计闭环，就过早进入恢复性自动化，会导致主线先把“异常分支”做复杂了，但“起点动作”还不完整。

### 2. 它直接补齐 51 里 `TaskCollection.create` 的语义

`docs/51-backend-first-api-boundary.md` 已经把 `TaskCollection.create` 定义为：

- 输入 task intent
- 输出新 Task + 初始 Event

现在 orchestration 层只完成了“新 Task”，还没有完成“初始 Event”。

因此 63 的作用不是新发明一个能力，而是把 51 早就定义好的 control-plane 资源语义真正落到 orchestration 入口上。

### 3. 风险显著低于 retry / fallback

`task submit` A+B 复用的还是现有、已经熟悉的积木：

- task ledger append
- event ledger append
- schema validate
- ledger consistency check
- byte-size rollback

而 retry / fallback 会立刻引入更多语义复杂度：

- run lineage（`retry_of` / `fallback_from`）
- adapter 切换语义
- approval / preflight 重算
- freeze 复用还是重算
- failure reason 与阻断态映射
- 重试是否自动沉淀额外 lifecycle events

从工程顺序看，先补 task submit A+B，风险更可控，也更符合“先补入口、再做恢复”的节奏。

### 4. 它能顺带补齐 read model 与 event timeline 的一致性

当前 orchestration 读侧已经有：

- `orchestration task list`
- `orchestration task get`
- `task events`
- 各类基于 ledger 的 overview / report 视角

如果 task submit 只写 task、不写 created event，那么：

- 任务集合视角和事件流视角并不完全一致；
- 后续如果 UI / report 更依赖 event timeline，会出现“为什么这个 task 没有 created 事件”的语义缺口；
- 同样会增加未来解释成本。

因此先补 `created` event，是对 read model 一致性的一次低风险修补。

## 当前状态与目标差异

### 当前状态（A-only）

`orchestration task submit --commit` 当前第一版语义：

- 写入 `tasks/tasks.jsonl`
- 做 task schema validate
- 做 ledger consistency post-check
- 失败时回滚 task ledger append
- **不写** `tasks/events.jsonl`

### 目标状态（A+B）

升级后建议语义：

- A：写入 `tasks/tasks.jsonl`
- B：追加一条 `created` event 到 `tasks/events.jsonl`
- post-check：同时校验 task ledger、event ledger 与 task/event cross-ledger consistency
- 失败时对 A+B 做 all-or-nothing 回滚

## 目标命令形态

候选命令形态保持不变：

```bash
python -m agent_runtime.cli orchestration task submit \
  --file candidate-task.json \
  --dry-run
```

```bash
python -m agent_runtime.cli orchestration task submit \
  --file candidate-task.json \
  --commit \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

与 62 相比，这里唯一关键变化是：

- `--commit` 进入 A+B 之后，`--events-file` 不再只是占位参数，而变成**必填输入**。
- 若缺失 `--events-file`，必须返回 `needs_input`，不写 A/B。

## A：Task Ledger Append

A 侧仍复用现有 `runtime task create --commit` 的核心写入机制。

### A 的职责

- 向 `tasks/tasks.jsonl` 末尾追加 exactly one task snapshot。
- 保持 task schema 有效。
- 保持与已有 task ledger 的 id 唯一性。
- 保持模拟追加后 ledger consistency 通过。

### A 成功条件

至少包括：

- candidate task 通过 schema validate
- `task_id` 未冲突
- public / secret scan 通过
- 追加后 task ledger 可被重新读取
- task ledger post-check 通过

### A 失败处理

- 若 A 在真正写入前失败：直接返回，不进入 B。
- 若 A 在写入后 post-check 失败：按现有 byte-size rollback 回滚 task ledger。

## B：Created Event Append

B 侧是在 A 成功之后，向 event ledger 追加一条与新 task 对应的 `created` event。

### 为什么是 `created`

`created` 是当前最自然、最稳定的入口事件：

- 它不依赖 routing / approval / run 结果；
- 它只表达“这个 task 已作为 control-plane 任务被正式接纳”；
- 它能与现有 task lifecycle 语义自然对齐。

### B 的职责

- 向 `tasks/events.jsonl` 追加 exactly one `created` event。
- 该 event 必须引用刚刚写入成功的 `task_id`。
- event payload 只保留安全摘要，不回显完整 task 内容。
- 追加后 event ledger 必须通过 event schema validation 与 task/event consistency 校验。

### 候选 event 字段

建议复用现有 `tasks/event.schema.json`：

- `event_id`
- `task_id`
- `timestamp`
- `actor`
- `event_type = created`
- `message`
- `metadata`

其中建议的安全 `metadata` 字段：

- `submission_mode`: `commit`
- `source`: `orchestration.task_submit`
- `task_status`
- `requested_capability`（如存在）
- `workspace`（如 schema 中有且可安全摘要化）
- `tag_count`
- `artifact_count`
- `evidence_count`

### 禁止字段

B 侧 event 中禁止写入：

- 完整 `title` / `summary` / long description
- secret / token / credential match
- evidence descriptions
- 绝对路径
- 内部 endpoint / env 值
- 原始 payload 全量拷贝

### event_id 生成

建议保证稳定且避免冲突，例如：

- `evt-{task_id}-created`
- 或 `evt-{task_id}-created-{short_hash}`

要求：

- 写入前必须检查 event ledger 中是否已存在相同 `event_id`
- 若冲突，返回 `blocked` 或 `error`，不提交 B；并触发 A+B 回滚策略

## A+B all-or-nothing rollback

这是 63 的核心。

一旦 `orchestration task submit --commit` 进入 A+B，就不能接受以下状态：

- task 已落盘，但没有 created event
- created event 已落盘，但 task 不存在

因此事务语义必须是 all-or-nothing。

### 推荐组合流程

1. 读取 candidate task，执行 dry-run 级别的预检。
2. 校验 `--tasks-file` 与 `--events-file` 均已显式提供。
3. 记录两份 ledger 的原始 byte size：
   - task ledger size
   - event ledger size
4. 执行 A：追加 task snapshot。
5. 对 A 做 task-side post-check。
6. 若 A 成功，执行 B：追加 `created` event。
7. 对 B 完成后的**实际落盘状态**做 cross-ledger post-check。
8. 只有当 A、B、cross-ledger post-check 都成功时，整体 commit 才算成功。

### 回滚规则

#### 情况 1：A 失败

- 不进入 B
- 回滚 task ledger 到原始 byte size（若已发生写入）

#### 情况 2：A 成功，B 失败

- 回滚 event ledger 到原始 byte size
- 回滚 task ledger 到原始 byte size
- 最终状态应等价于“本次 commit 从未发生”

#### 情况 3：A、B 都写入了，但 cross-ledger post-check 失败

- 回滚 event ledger 到原始 byte size
- 回滚 task ledger 到原始 byte size
- 返回 `error` 或 `blocked`，并说明 post-check failed

### 回滚顺序建议

若 A 已写、B 也已写，而 post-check 失败，建议回滚顺序为：

1. 先回滚 event ledger
2. 再回滚 task ledger

原因：

- event 依赖 task 存在；
- 先删依赖项，再删被依赖项，语义更自然；
- rollback 中途若出现不可恢复错误，也更容易解释当前残留状态。

## dry-run / commit 语义更新

### dry-run

`orchestration task submit --dry-run` 仍然保持只读，不模拟真实 A+B 写入，但输出应开始对齐未来 A+B 语义。

建议 dry-run 输出新增或明确：

- `would_create_task`
- `would_append_created_event`
- `event_type = created`
- `ledger_check`
- `next_action`

这样用户能在 dry-run 时就知道：commit 之后将发生 A+B，而不是只有 task append。

### commit

`orchestration task submit --commit` 建议输出新增：

- `task_committed`
- `created_event_appended`
- `event_id`
- `tasks_file`
- `events_file`
- `post_validate_task`
- `post_validate_event`
- `post_ledger_check`
- `rolled_back`
- `next_action`

## 输出与 Read Model 一致性

这是 63 的第四个重点。

### 目标一致性

当一次 commit 成功后，至少以下视角应当互相对齐：

- `orchestration task list` 能看到新 task
- `orchestration task get` 能看到新 task 详情
- `task events <task_id>` 能看到 `created` event
- 任何基于 task/event ledger 的 overview / report，不应出现“task 已存在但 timeline 为空”的入口缺口

### 不追求的第一版一致性

第一版仍然**不要求**：

- 自动产生 run
- 自动产生 approval
- 自动产生 artifact
- 自动产生 report cache

也就是说，63 只修补**Task 与 Event timeline 的入口一致性**，不把整个 orchestration 流水线自动串起来。

### 对 `task get` / `task list` 的影响

原则上，A+B 不必强迫改造 `task get` / `task list` 的底层读逻辑；只要：

- 它们已经能从 task ledger 读取 task
- `task events` / timeline 读取能从 event ledger 读取 `created`

那么 read model 一致性就已经明显改善。

若后续 `orchestration task get` 计划内嵌事件时间线，则 63 也会成为这个增强的前置条件。

## 与 62 的关系

62 解决的是：

- orchestration 命名空间下终于有了 task submit 入口
- 第一版先保守落地 A-only，降低风险

63 解决的是：

- 把 62 的 A-only 入口升级成 A+B
- 让 task submit 真正对齐 51 中 `TaskCollection.create` 的“Task + 初始 Event”语义
- 补齐 read model 与 event timeline 的入口一致性

因此 63 不是推翻 62，而是对 62 的自然升级。

## 与 retry / fallback 的边界

63 落地后，仍然不意味着可以直接跳过 retry / fallback 的独立 design gate。

因为 retry / fallback 还会涉及新的问题：

- `retry_of` / `fallback_from` 的 lineage 表达
- 新 run 与旧 run 的状态继承关系
- approval 与 preflight 的重算策略
- failure cause 与 blocking reason 的建模
- lifecycle events 的扩展

所以顺序仍应是：

1. 62：task submit A-only
2. 63：task submit A+B (`created` event)
3. 64：版本治理与 tag 策略
4. 后续再进入 retry / fallback design gate

## 实现建议

进入实现时，建议复用现有两类积木：

- task append / rollback 相关实现
- event append / rollback 相关实现

实现层建议重点检查：

- `--events-file` 缺失时必须 hard fail，不得默认写真实 ledger
- post-check 必须针对**实际落盘后的** task + events ledger 做校验
- rollback 失败时输出只能给安全摘要，不回显敏感内容
- 不得为了省事把整份 task snapshot 塞进 event metadata

## 验收标准

本阶段实现完成后，至少应满足：

- `orchestration task submit --dry-run` 明确预告 A+B 语义
- `orchestration task submit --commit` 成功时，同时写入 task 与 `created` event
- 任一环节失败时，task ledger 与 event ledger 都能回滚到原始状态
- `task events <task_id>` 能稳定看到新写入的 `created` event
- task/event cross-ledger consistency 校验通过
- 不访问网络、不执行真实 adapter、不发送消息、不引入 DB / service / UI

## 下一步建议

63 完成后，下一步最自然的是二选一：

1. 先实现 63，并补对应 release notes
2. 再进入 retry / fallback design gate

推荐顺序仍然是：**先实现 63，再做 retry / fallback**。
