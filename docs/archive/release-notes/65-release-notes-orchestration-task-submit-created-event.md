# 65 — Release Notes：Orchestration Task Submit Created Event

## 阶段定位

本阶段是 `docs/63-orchestration-task-submit-created-event-design.md` 的实现收口。

在 62 阶段，`orchestration task submit --commit` 已经作为 control-plane-facing 入口落地，但第一版只写 task ledger，也就是 A-only：

- A：向 task ledger 追加 task snapshot
- B：不自动写 event ledger

本阶段把它升级为 A+B controlled write：

- A：追加 exactly one task snapshot 到 task ledger
- B：追加 exactly one `created` event 到 event ledger
- A+B：任一环节失败，两个 ledger 都回滚到原始 byte size

这使 `orchestration task submit` 更完整地对齐 `docs/51-backend-first-api-boundary.md` 中 `TaskCollection.create` 的“新 Task + 初始 Event”语义。

## 已实现能力

### 1. `orchestration task submit --dry-run` A+B preview

`--dry-run` 仍然完全只读，不写 task ledger，不写 event ledger。

它现在会预告 commit 的 A+B 语义：

- `would_create=True`
- `would_append_created_event=True`
- 返回候选 `event_id`
- 通过临时 task/events ledger 执行 combined ledger consistency 预检

这让用户在 commit 前就能看到：提交 task 后会同时追加 `created` event。

### 2. `orchestration task submit --commit` A+B controlled write

`--commit` 成功路径现在执行：

1. 复用 runtime task create 预检 task candidate。
2. 构造安全的 `created` event candidate。
3. 使用临时 ledger 模拟 A+B 后的 cross-ledger consistency。
4. A：追加 task snapshot。
5. B：追加 `created` event。
6. 对实际落盘后的 task/events ledger 做 post-check。
7. 全部通过后返回 task id、event id、post-check 状态与下一步建议。

`--events-file` 在 `--commit` 下已变成必填；缺失时返回 `needs_input`，不写 A/B。

### 3. Created event 安全摘要

新增的 `created` event 满足现有 `tasks/event.schema.json`：

- `event_type = created`
- `task_id` 指向刚提交的 task
- `from_status = null`
- `to_status = task snapshot status`
- `actor` 来自 candidate `created_by`，缺省为 `cli`
- `message = "Task submitted."`

metadata 只保留安全摘要：

- `source`
- `actor`
- `submit_method = orchestration_task_submit`

不写入完整 title、summary、evidence descriptions、secret match、绝对路径或原始 payload。

### 4. A+B all-or-nothing rollback

本阶段新增 orchestration 层事务协调：

- A 失败：不进入 B，由 task create 自身回滚。
- B 失败：event append 自身回滚 B，orchestration 层继续回滚 A。
- A+B 都写入但 post-check 失败：先回滚 events ledger，再回滚 task ledger。

最终目标是不留下以下半成功状态：

- task 已存在但没有 `created` event
- `created` event 已存在但 task 不存在

### 5. Read model 一致性

成功 commit 后，以下视角保持一致：

- `orchestration task list` 能看到新 task
- `orchestration task get` 能看到新 task 与 event timeline
- `task events <task_id>` 能看到 `created` event
- `task check-ledger` 能通过 task/event cross-ledger consistency

本阶段仍不自动触发 route / preflight / run / adapter execution。

## 修改范围

核心代码：

- `agent_runtime/orchestration_task_submit.py`
- `agent_runtime/cli.py`

测试：

- `tests/test_orchestration_task_submit.py`

文档：

- `docs/10-cli-poc-usage.md`
- `docs/63-orchestration-task-submit-created-event-design.md`
- `docs/archive/release-notes/65-release-notes-orchestration-task-submit-created-event.md`

## 保持不变的边界

本阶段仍然不开放：

- 真实 adapter execution
- 网络访问
- 消息发送
- DB / service / UI
- 自动 route / preflight / run
- retry / fallback

`orchestration task submit --commit` 仍只是项目内 ledger controlled write。

## 验证

本阶段已完成并复核以下验证：

```bash
python -m pytest tests/test_orchestration_task_submit.py -q
python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

验证结果：

- `tests/test_orchestration_task_submit.py`：通过。
- `tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py`：通过。
- 全量 `pytest tests -q`：通过。
- `doctor`：PASS。
- `public_scan`：OK public scan。
- `git diff --check`：无空白错误，仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。

## 已知注意事项

- Kimi Code 额外生成了 `docs/superpowers/` 下的 spec/plan 工作流文件；这些文件未纳入主线索引，后续应单独决定保留还是清理。
- 当前实现直接复用 runtime task/event primitives，并在 orchestration 层做组合事务协调；后续如出现更多 A+B 事务，可再考虑抽通用 helper。
- retry / fallback 仍未进入实现，应继续作为后续独立 design gate。

## 下一步建议

本阶段完成后，后续实际已走完的路径是：

1. 先完成 retry / fallback design gate 与 dry-run preview
2. 再完成 `v0.12.0-orchestration-foundation` milestone freeze

如果以后从本阶段继续往后接，当前更自然的下一拍不再是重复 freeze 检查，而是：

1. 进入 retry / fallback commit 设计
2. 或先做 post-freeze 文档口径整理与后续 design gate 选择

默认建议优先进入 retry / fallback commit 设计，而不是重复执行已完成的 milestone freeze。
