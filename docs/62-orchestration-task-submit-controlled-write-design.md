# 62 — Orchestration Task Submit 受控写入设计

## 阶段定位

在 Stage 15.9 完成 `orchestration run --commit` 的 A+B controlled write 之后，当前 orchestration 主线里仍缺少一个更靠前的受控写入入口：**Task 提交本身**。

也就是说，run 侧已经可以在既有 task 上沉淀 envelope draft 与 lifecycle events，但 task 入口仍然依赖底层 `runtime task create --commit`，尚未有一个真正位于 orchestration 命名空间、面向 control plane 语义的 `task submit` 写入边界。

本文档的目标不是立刻实现真实的任务分发自动化，而是先把 `orchestration task submit --dry-run / --commit` 的边界、产物、回滚、状态映射与安全约束设计清楚，作为下一批低风险 orchestration 写入的 design gate。

遵循原则仍然不变：

- 先只做项目内受控写入，不放开真实 adapter execution。
- 复用已有 Runtime controlled-write 积木，不平地起新存储。
- 先补入口，再谈 retry / fallback 自动化。
- 不引入 UI / service / database / 独立 Task queue。

## 为什么先做 task submit，而不是 retry / fallback

当前三条后续线都还没做完：

- `orchestration task submit --commit`
- `orchestration run --retry`
- `orchestration run --fallback-to`

优先级上，task submit 更应该先落地，原因有三点：

1. **它是入口级能力，不是恢复性能力**。
   - retry / fallback 都建立在“已有 task + 已有 run + 已有失败上下文”之上。
   - task submit 则是整个编排闭环的起点，更符合 Stage 14 最小闭环的顺序。

2. **它更贴近已有 `runtime task create --commit` 能力，风险更低**。
   - 已有 task ledger append、schema validate、post-check、rollback 都已存在。
   - orchestration 层可以先做受控包装，再决定是否引入额外 event / routing hints。

3. **它能补齐 control plane 语义上的“入口对齐”**。
   - 现在 orchestration 命名空间已经有 route / preflight / run / approval / artifact / report。
   - 如果连 task submit 都没有，就还不是一个完整的 orchestrator-facing backend surface。

因此，推荐下一阶段先做 task submit 的 design gate，再视情况进入实现；retry / fallback 继续保留为更后面的恢复性能力。

## 目标命令

候选命令形态：

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

也可保留后续更面向 orchestration 的输入形态，例如：

```bash
python -m agent_runtime.cli orchestration task submit \
  --title "Read adapter layer doc" \
  --capability read_file \
  --workspace project-root \
  --mode dry-run
```

但第一版**不建议**直接实现这种高层字段拼装写入；应优先复用与对齐现有 `runtime task create` 的 candidate JSON 输入边界，降低歧义和 schema 映射成本。

## 第一版推荐范围

### 推荐第一版：薄包装现有 task create

第一版 `orchestration task submit` 推荐采用：

- `--file <candidate-task.json>` 或 `--stdin`
- `--dry-run | --commit` 显式二选一
- 复用 `runtime task create --dry-run / --commit` 的底层校验与写入能力
- 仅在 orchestration 层做：
  - control-plane 语义命名
  - 更紧凑的人类输出
  - 与后续 route / preflight / run 的 next_action 对齐

这样做的优点：

- 复用现有 task schema、public scan、secret scan、ledger consistency、rollback。
- 不需要为第一版单独发明新的 task intent schema。
- 不会把“task 提交”误做成“自动创建 task + 自动路由 + 自动执行”的一步到位命令。

### 暂不做的第一版能力

以下内容仍然暂缓：

- 自动根据 `--capability` / `--title` 现场生成完整 task snapshot。
- 自动同时写入 `created` event。
- submit 成功后自动调用 route preview / preflight / run。
- 自动生成 approval request。
- 自动触发 retry / fallback。
- 写独立 submit receipt / queue / report。

## dry-run / commit 语义

### dry-run

`orchestration task submit --dry-run`：

- 只做 candidate task 的 schema validation、task id 去重检查、secret/public scan、模拟追加后的 ledger consistency。
- 不写 `tasks/tasks.jsonl`。
- 不写 `tasks/events.jsonl`。
- 不写 envelope / artifact / report。
- 输出稳定、安全的 preview 摘要。

建议输出字段：

- `status`
- `task_id`
- `task_status`
- `title_present`
- `assignee_present`
- `tag_count`
- `artifact_count`
- `evidence_count`
- `would_create`
- `ledger_check`
- `metadata_keys`
- `next_action`

### commit

`orchestration task submit --commit`：

- 只允许向 task ledger 末尾追加 exactly one task JSON object。
- 写入后做 task schema validation 与 ledger consistency post-check。
- post-check 失败时按原始 byte size 回滚。
- 第一版**不自动写 event ledger**。
- 第一版**不自动触发 route / preflight / run**。

建议 commit 输出额外包含：

- `committed`
- `post_validate`
- `post_ledger_check`
- `rolled_back`
- `next_action`

其中 `next_action` 建议直接对齐 orchestration 主线，例如：

- `Task submitted; run orchestration route preview or orchestration preflight next.`

## 与 `runtime task create` 的关系

### 第一版关系：orchestration 是 control-plane 包装层

第一版推荐明确：

- `runtime task create` 仍是底层 controlled-write primitive。
- `orchestration task submit` 是面向 orchestration/control-plane 语义的包装层。

分工建议：

- `runtime task create`
  - 强调 ledger append、schema、rollback、写入正确性。
- `orchestration task submit`
  - 强调 task 作为 control-plane 入口的语义。
  - 输出更贴近后续 route / preflight / run 流程。

### 为什么不直接让用户一直用 `runtime task create`

因为长期看，control plane 语义应该尽量聚拢在 orchestration 命名空间下：

- `orchestration task submit`
- `orchestration route preview`
- `orchestration preflight`
- `orchestration run`
- `orchestration approval resolve`
- `orchestration report`

否则用户从“提交任务”开始就需要掉回 runtime 子系统，命名空间体验是不连续的。

## 事件策略

### 第一版：不自动写 `created` event

虽然 51 里的 `TaskCollection.create` 语义可以对应“新 Task + 初始 Event”，但第一版仍建议保持保守：

- `orchestration task submit --commit` 只写 task ledger。
- 如需 `created` event，仍显式调用 `runtime event append --commit` 或后续单独设计 orchestration task event 策略。

原因：

1. 现有 `runtime task create --commit` 已清晰定义为“只写 task ledger”。
2. 一旦把 task submit 扩展成 task + event 双写，就必须立即处理 A+B 回滚、event payload、created event 文案与 actor 归属。
3. 当前更需要先补齐 orchestration 入口，而不是提前把入口也变成双写事务。

### 后续可选升级

后续如需要，可设计 Stage 62.5 / 63 一类扩展：

- A：task ledger append
- B：`created` event append
- all-or-nothing rollback

但这不应阻塞第一版 orchestration task submit。

## 输入边界

第一版 candidate task 仍需满足现有 `tasks/task.schema.json`。

因此：

- 推荐只支持 `--file` / `--stdin` 输入完整 candidate task JSON。
- 不在第一版支持半结构化高层字段自动拼 task snapshot。
- 输出中不回显完整 `title` / `summary` / evidence descriptions / secret match。

## 安全边界

第一版必须继续保持：

- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不读取 `.env` / credential / token / keyring。
- 不写 `tasks/events.jsonl`。
- 不生成 envelope draft。
- 不引入独立 Task storage、DB、service、UI。

candidate task 仍需通过：

- task schema validation
- duplicate task id check
- secret scan
- public scan
- simulated / post ledger consistency

## 与 51 / 54 / 56 / 62 主线关系

- `docs/51-backend-first-api-boundary.md` 中，`TaskCollection.create` 是受控写入操作；本文档把它细化到 CLI / controlled-write 层。
- `docs/54-backend-preparation-before-ui.md` 中，任务页的“创建任务”操作入口目前仍是草案；本文档把它转成可实现的第一版写入边界。
- `docs/56-orchestration-controlled-write-boundary.md` 已明确 `orchestration task submit --commit` 应晚于 route/preflight/approval resolve、早于 retry/fallback；本文档承接这个排期。
- `docs/61-release-notes-orchestration-run-lifecycle-events.md` 已说明 run 侧 A+B 完成；本文档把下一步焦点从 run 生命周期切回 task 入口。

## 验收标准

如进入实现，第一版至少应满足：

1. CLI：`orchestration task submit --dry-run / --commit` 明确可用。
2. `--dry-run` 不写任何 ledger。
3. `--commit` 只写 task ledger，不写 events ledger。
4. post-check 失败能回滚。
5. 输出不含 title / summary / evidence description / secret match。
6. 通过：
   - `python -m pytest tests -q`
   - `python -m agent_runtime.cli doctor`
   - `python tools/public_scan.py`
   - `git diff --check`
7. 至少补一条 smoke：在临时 root 下 `task submit --dry-run` -> `task submit --commit` -> `orchestration task list/get` 可观察到新 task。

## 暂不进入实现的项

以下继续明确排除：

- retry / fallback 自动化
- task submit 自动写 `created` event
- task submit 自动触发 route/preflight/run
- run_blocked / task_blocked 自动恢复机制
- 真实 adapter execution
- 网络 / 消息 / UI / service / database

## 下一步建议

1. 先把本文档作为 Stage 16 之前的一个小 design gate 收口。
2. 若认可此边界，优先实现第一版 `orchestration task submit --dry-run / --commit`，采用 candidate JSON 薄包装 `runtime task create`。
3. 待 task submit 入口稳定后，再考虑：
   - 是否补 `created` event 双写版本
   - 是否让 `orchestration task submit` 支持更高层的 intent 输入
   - 是否再进入 retry / fallback 设计
