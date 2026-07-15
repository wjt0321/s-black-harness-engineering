# 70 — Orchestration Run Retry / Fallback Commit 设计

## 阶段定位

`docs/66-orchestration-run-retry-fallback-design.md` 已完成 retry / fallback 的第一版 design gate，`docs/archive/release-notes/67-release-notes-orchestration-run-retry-fallback.md` 已完成 dry-run preview 落地。

当前基线已经具备：

- `orchestration task submit --commit` A+B
- `orchestration run --commit` A+B
- `orchestration run --retry-of ... --dry-run`
- `orchestration run --fallback-from ... --fallback-to ... --dry-run`
- `v0.12.0-orchestration-foundation` milestone baseline

因此，post-freeze 后最自然的下一拍不是继续扩真实 adapter execution，而是先把 **retry / fallback commit** 的边界、产物、lineage、freeze guard、event trail 与 rollback 规则设计清楚，作为新的 design gate。

本文档只定义 retry / fallback commit 的受控写入边界，不直接放开真实 adapter execution，不访问网络，不发送消息，不引入 DB / service / UI。

## 目标

把当前只读的 retry / fallback preview，升级成**受控写入的 run commit 分支**：

- Retry commit：在同一个 task 下，为新的 `request_id` 生成 lineage-aware envelope draft，并追加对应 lifecycle events。
- Fallback commit：在同一个 task 下，为新的 `request_id` 与新的 adapter 生成 lineage-aware envelope draft，并追加对应 lifecycle events。
- 两者都继续沿用现有 `orchestration run --commit` 的 A+B 事务模型。

也就是说，新增能力仍然只是：

- A：envelope draft/export
- B：lifecycle events append

而不是：

- 真实执行 adapter
- 自动发送消息
- 自动访问 GitHub / Shell / Lark / WebBridge

## 为什么现在可以进入 commit 设计

当前链路已经补齐到足以承载 lineage-aware commit：

1. `task submit` 入口 A+B 已具备。
2. `run --commit` 普通路径 A+B 已具备。
3. retry / fallback dry-run 已能稳定输出 lineage 字段与新的 `plan_hash`。
4. `plan_hash` 已纳入 `retry_of` / `fallback_from` / `fallback_to`，避免普通 run 与恢复性 run 混淆。
5. 现有 `run_planned` / `run_draft_exported` lifecycle event trail 已存在，可继续扩展到带 lineage 的 commit。

因此，当前缺的不是底层写入积木，而是：

- retry / fallback commit 的语义边界
- 是否新增 event type
- 如何表达 lineage
- 如何防止重复 commit / lineage 冲突
- 如何处理 approval / blocked / stale hash 分支

## 非目标

本阶段明确不做：

- 真实 adapter execution
- adapter response / evidence 真实落盘
- approval 自动复用
- 自动重放旧 input payload
- 自动选择 fallback adapter
- 独立 Run storage / DB / service
- UI / dashboard / API 服务化
- 自动修改旧 run 状态为 succeeded / failed / superseded

## 候选命令形态

### Retry commit

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260710-001 \
  --request-id req-20260710-002 \
  --capability git_push \
  --operation git_push \
  --target origin/main \
  --retry-of req-20260710-001 \
  --output drafts/runtime/task-20260710-001/req-20260710-002.envelope.json \
  --events-file tasks/events.jsonl \
  --expected-plan-hash sha256:... \
  --commit
```

### Fallback commit

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260710-001 \
  --request-id req-20260710-003 \
  --capability git_push \
  --operation git_push \
  --target origin/main \
  --fallback-from req-20260710-001 \
  --fallback-to shell-local \
  --output drafts/runtime/task-20260710-001/req-20260710-003.envelope.json \
  --events-file tasks/events.jsonl \
  --expected-plan-hash sha256:... \
  --commit
```

第一版建议继续沿用现有 `orchestration run` 命令，而不是拆出新的 `retry commit` / `fallback commit` 子命令。

## 输入约束

Retry / fallback commit 第一版至少必须要求：

- `task_id`
- 新 `request_id`
- `capability`
- `--output`
- `--events-file`
- `--expected-plan-hash`
- `--commit`
- `--retry-of` 或 `--fallback-from` 二选一
- fallback 分支额外要求 `--fallback-to`

保持与当前 dry-run 一致：

- `--retry-of` 与 `--fallback-from` 互斥。
- `--fallback-to` 必须与 `--fallback-from` 一起使用。
- 新 `request_id` 不得等于 source request id。

新增 commit 侧约束：

- 不允许缺失 `--expected-plan-hash`。
- 不允许缺失 `--output`。
- 不允许缺失 `--events-file`。
- lineage 参数只影响新 run，不修改旧 run 记录。

## 与普通 run commit 的关系

retry / fallback commit 应被视为 **普通 `orchestration run --commit` 的 lineage-aware 变体**，而不是独立写入系统。

复用不变的部分：

- route / preflight / dry-run 重新计算
- `plan_hash` freeze guard
- A：draft export 受控写入
- B：event ledger append + post-check
- all-or-nothing rollback

新增变化只在：

- candidate envelope metadata 带 lineage 字段
- lifecycle events metadata 带 lineage 字段
- fallback 分支会切换 effective adapter

## A+B 事务模型

### A. envelope draft export

Retry / fallback commit 的 A 仍是导出新的 envelope draft 文件：

- 路径仍建议为 `drafts/runtime/<task_id>/<request_id>.envelope.json`
- 文件必须是全新的，不覆盖旧 run 的 envelope
- envelope 中必须包含新的 `request_id`
- metadata 中必须带 lineage 字段

候选 lineage metadata：

### Retry envelope metadata

- `lineage_type = retry`
- `retry_of_request_id`
- `source_request_id`

### Fallback envelope metadata

- `lineage_type = fallback`
- `fallback_from_request_id`
- `fallback_to_adapter_id`
- `source_request_id`

第一版不建议写：

- `attempt_number`
- `supersedes_request_id`
- `resolved_failure_reason`

因为当前没有独立 Run storage，自动维护这些聚合字段容易歧义。

### B. lifecycle events append

Retry / fallback commit 的 B 仍是向 event ledger 追加 lifecycle events。

第一版有两种可选策略：

#### 策略 1：复用现有 event_type

继续使用：

- `run_planned`
- `run_draft_exported`
- `run_blocked`

只是在 metadata 中增加 lineage 字段。

优点：

- 不扩展 schema enum
- read model 与现有 event trail 兼容
- 实现成本更低

缺点：

- 从 event_type 本身无法直接看出这是 retry 还是 fallback
- 需要读取 metadata 才能区分 lineage

#### 策略 2：新增 event_type

新增候选：

- `run_retry_planned`
- `run_retry_draft_exported`
- `run_fallback_planned`
- `run_fallback_draft_exported`

优点：

- event timeline 更直观
- 后续 report / UI 更容易聚合

缺点：

- schema enum 扩张更快
- 与现有 `run_planned` / `run_draft_exported` 的关系要再解释

### 第一版推荐

**第一版推荐采用策略 1：复用现有 event_type，只在 metadata 中增加 lineage 字段。**

原因：

- 与当前 dry-run 的 lineage 模型一致
- 减少 schema 扩张
- 先把 commit 边界跑通，再决定是否需要语义更细的 event type

## Lifecycle event metadata 建议

无论 retry 还是 fallback，event metadata 建议至少包含：

- `request_id`
- `adapter_id`
- `capability`
- `operation`
- `mode = commit`
- `plan_hash`
- `envelope_path`
- `lineage_type`
- `retry_of`（retry 分支）
- `fallback_from` / `fallback_to`（fallback 分支）

禁止写入：

- 完整 input payload
- target 原文
- reason 原文
- raw_ref / decision_ref / payload_refs
- secret / token / credential
- 绝对路径

## Freeze guard

retry / fallback commit 必须比普通 run commit 更保守：

1. **必须重跑 dry-run / route / preflight**
2. **必须重新计算 lineage-aware `plan_hash`**
3. **必须要求 `--expected-plan-hash`**
4. **hash mismatch 一律 blocked，不写 A/B**

解释：

- 普通 run commit 已经依赖 `plan_hash` 保护“审阅的是 A、提交的是 B”这种 drift 风险。
- retry / fallback 比普通 run 更多一层 lineage 变化，因此不应支持“无 expected hash 直接 commit”。

因此建议第一版把：

- retry/fallback commit -> `--expected-plan-hash` 必填
- 普通 run commit -> 维持现有语义

## Approval 规则

Retry / fallback commit 不自动复用旧 approval。

必须遵守：

- retry 也要重新 preflight
- fallback 更要重新 preflight
- 即使 source request 曾经 approved，新 request 仍可能触发新的 `needs_approval`

当新计划触发 `needs_approval`：

- 返回 `needs_approval`
- 不写 A/B
- 不自动创建 approval request
- 提示继续走 `orchestration approval resolve` 的既有路径

## Source request 存在性与 lineage 完整性

第一版至少要检查：

- `retry_of` / `fallback_from` 指向的 source request id 在当前 task 上有可识别的既有 run 证据
- 该证据可来自：
  - 现有 envelope draft
  - 现有 event ledger metadata
  - 或两者之一

若无法定位 source request：

- 返回 `needs_input` 或 `validation_failed`
- 不写 A/B

第一版不要求定位 source request 的全部原始 payload，但至少要确认：

- source request 确实存在
- source request 属于同一 `task_id`

## 重复 commit / 幂等保护

需要保护两类重复：

### 1. 同一新 request_id 重复 commit

若：

- `--output` 已存在
- 或 event ledger 已存在同一 `request_id` + `plan_hash` + `run_draft_exported`

则返回 `blocked`，不覆盖、不重复追加。

### 2. 同一 source request 反复 retry/fallback

这是允许的。

例如：

- `req-002 retry_of req-001`
- `req-003 retry_of req-001`
- `req-004 fallback_from req-001`

都应允许，只要：

- 新 `request_id` 唯一
- 每次都独立 dry-run / preflight / freeze guard

## 回滚边界

继续复用现有 run commit 的组合回滚：

- A 失败 -> 不写 B
- B 失败 -> 删除 A，并按 byte size 回滚 B
- post-check 失败 -> 回滚 B，再回滚 A

新增 retry/fallback 特别要求：

- rollback 后不应留下“lineage 已写入一半”的残留状态
- 不允许只留下带 `retry_of` / `fallback_from` 的 envelope，但没有对应 lifecycle events
- 不允许只留下 lifecycle events，但 envelope 文件缺失

## Read model 影响

第一版不要求修改现有 read model 结构，但应保证现有命令至少能看见 lineage：

- `orchestration run inspect`：应能在 envelope / metadata 中显示 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`
- `task events`：应能通过 metadata 看见 lineage 字段
- `orchestration run list`：可先不额外聚合 lineage，但后续应考虑显示一个简短 lineage 标识

## Report 影响

第一版不新增独立 report 集合。

但后续 `orchestration report generate` / `runtime report` 应能安全摘要以下信息：

- 当前 run 是否为 retry / fallback
- source request id
- fallback adapter id（如有）
- 不泄露完整 target / payload

## 测试建议

如果后续进入实现，最少要覆盖：

1. retry commit 成功：
   - 写入新的 envelope
   - 追加 lifecycle events
   - metadata 带 `lineage_type=retry`

2. fallback commit 成功：
   - 写入新的 envelope
   - 追加 lifecycle events
   - metadata 带 `lineage_type=fallback`

3. hash mismatch：
   - blocked
   - A/B 都不写

4. `needs_approval`：
   - 返回 `needs_approval`
   - A/B 都不写

5. source request 不存在：
   - `needs_input` 或 `validation_failed`
   - A/B 都不写

6. A 成功 B 失败：
   - 删除 A
   - 回滚 B

7. 不泄露：
   - 无完整 payload
   - 无 target 原文
   - 无 raw_ref / decision_ref
   - 无 secret match

## 验收标准

当未来进入实现时，至少应满足：

1. retry/fallback commit 继续保持“受控写入，不是真实执行”。
2. 必须显式 `--expected-plan-hash`。
3. 必须显式 `--output` 与 `--events-file`。
4. 每次 commit 都重新 route / preflight / dry-run。
5. lifecycle events 至少能通过 metadata 区分 retry 与 fallback。
6. 通过：
   - `python -m pytest tests -q`
   - `python -m agent_runtime.cli doctor`
   - `python tools/public_scan.py`
   - `git diff --check`

## 当前推荐下一步

推荐顺序：

1. 先审本文档，固定 retry/fallback commit 的 A+B、lineage、freeze guard 与 event 策略。
2. 若 design gate 通过，再进入实现。
3. 实现完成后，再补对应 release notes。

在此之前，不建议直接跳去真实 adapter execution。