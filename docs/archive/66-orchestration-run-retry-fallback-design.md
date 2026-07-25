# 66 — Orchestration Run Retry / Fallback 设计

## 阶段定位

`orchestration task submit --commit` 已经完成入口级 A+B controlled write：

- task ledger 追加 task snapshot
- event ledger 追加 `created` event
- A+B all-or-nothing rollback

`orchestration run --commit` 也已经完成 run 侧 A+B controlled write：

- A：导出 envelope draft
- B：追加 `run_planned` + `run_draft_exported` lifecycle events

因此，当前 orchestration 主线的下一个自然 design gate 是恢复性能力：

- `orchestration run --retry`
- `orchestration run --fallback-to`

本文档只定义 retry / fallback 的设计边界，不直接实现真实 adapter execution，不放开网络访问、不发送消息、不引入 DB / service / UI。

## 为什么现在可以设计 retry / fallback

在 62 / 63 / 65 之前直接做 retry / fallback 风险偏高，因为入口 task 与 run lifecycle event trail 还不完整。

现在顺序已经补齐：

1. task submit 入口已存在。
2. task submit 已能写 `created` event。
3. run dry-run 已能生成稳定 `plan_hash`。
4. run commit 已能沉淀 envelope draft + lifecycle events。
5. route preview / preflight 已能提供 fallback candidates 与 guardrail 摘要。

这意味着 retry / fallback 不再是凭空新增自动化，而是建立在已有 task、route、preflight、run event trail 之上的恢复性分支。

## 概念边界

### Retry

Retry 表示：在同一个 task 下，基于已有 run/request 的上下文，对同一 capability / adapter / operation 再尝试一次。

建议语义：

- 新 request_id 必须不同于原 request_id。
- 新 run 与旧 run 通过 `retry_of` 关联。
- 默认复用原 capability / adapter / operation / target 安全摘要。
- 必须重新执行 route / preflight / dry-run，不信任旧结果。
- 不自动复用旧 `plan_hash`；新尝试必须生成新 plan。

Retry 适合：

- 上一次 run 被 transient failure 阻断。
- 用户修复了输入 / ledger / approval 后，希望同 adapter 再跑一次。
- 仍希望保持同一执行路径，而不是切换 adapter。

### Fallback

Fallback 表示：在同一个 task 下，基于已有 run/request 的上下文，切换到另一个 adapter 或 mode 继续尝试。

建议语义：

- 新 request_id 必须不同于原 request_id。
- 新 run 与旧 run 通过 `fallback_from` 关联。
- 新 adapter 必须来自 route preview / preflight 的 fallback candidates，或由用户显式指定并通过 capability 支持性校验。
- 必须重新执行 route / preflight / dry-run。
- 不自动继承旧 approval；除非后续独立设计 approval reuse。

Fallback 适合：

- 原 adapter 不支持 capability 或被 blocked。
- 原 adapter preflight 不通过，但另一个 adapter 可走 dry-run / commit。
- 需要从高风险模式降级到更安全模式。

## 第一版推荐范围

第一版只建议做 design + dry-run preview，不直接做 commit 自动链路。

### 推荐第一版能力

- `orchestration run --retry --dry-run`
- `orchestration run --fallback-to <adapter_id> --dry-run`
- 输出 retry/fallback plan preview。
- 复用 existing run 的安全摘要。
- 重新跑 route preview / preflight。
- 输出新的 candidate request_id、lineage、route/preflight 摘要与 next_action。

### 暂不做的第一版能力

- 不自动 commit retry/fallback run。
- 不直接执行真实 adapter。
- 不自动选择 fallback adapter。
- 不自动重用 approval。
- 不自动修改旧 run 状态。
- 不引入独立 Run storage。
- 不自动生成 report cache。

## 命令形态草案

### Retry dry-run

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --retry-of req-20260703-001 \
  --dry-run
```

或者保留显式开关：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-002 \
  --retry \
  --retry-of req-20260703-001 \
  --dry-run
```

### Fallback dry-run

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-003 \
  --fallback-from req-20260703-001 \
  --fallback-to shell-local \
  --dry-run
```

第一版建议优先使用显式 `--retry-of` / `--fallback-from` / `--fallback-to`，避免 `--retry` 这类布尔开关承载过多语义。

## 输入要求

Retry / fallback 第一版至少需要：

- `task_id`
- 新 `request_id`
- 原 `request_id` 或原 envelope path
- retry / fallback 类型
- fallback adapter（fallback 分支必填）
- 原 run 的安全摘要来源

原 run 的安全摘要可以来自：

- existing envelope draft
- runtime report
- event ledger 中的 lifecycle events
- 用户显式提供的 capability / operation / target

第一版更稳妥的选择是：继续要求用户显式提供 capability / operation / target，`retry_of` / `fallback_from` 只作为 lineage metadata，不自动从旧 envelope 反推完整 input。

## 输出建议

Retry / fallback dry-run 输出应包含：

- `status`
- `task_id`
- `request_id`
- `mode = dry-run`
- `lineage_type = retry | fallback`
- `retry_of` 或 `fallback_from`
- `selected_adapter_id`
- `fallback_to`（fallback 分支）
- route summary
- preflight summary
- candidate envelope summary
- candidate lifecycle events summary
- new `plan_hash`
- `next_action`

禁止输出：

- 完整 input payload
- target 原文中可能敏感的长文本
- raw_ref / decision_ref / payload_refs
- secret match
- 绝对路径

## Event 策略

第一版 dry-run 不写 event。

后续若进入 commit，可考虑新增 lifecycle events：

| event_type | 语义 | 第一版是否落地 |
|:---|:---|:---:|
| `run_retry_planned` | retry plan 已生成 | 否 |
| `run_fallback_planned` | fallback plan 已生成 | 否 |
| `run_draft_exported` | 仍可复用现有 draft exported 事件 | 已存在 |
| `run_blocked` | retry/fallback 被 preflight 或 lineage 校验阻断 | 已预留 |

第一版不建议立即扩展 schema enum。原因：retry/fallback dry-run 先不写 ledger，现有 `run_planned` 足以承接后续 commit 的最小语义；等 commit 设计明确后，再决定是否需要更细 event type。

## Lineage 建模

### Retry lineage

建议在 candidate envelope / event metadata 中保留：

- `retry_of_request_id`
- `retry_reason_code`（可选）
- `attempt_number`（可选，后续再做）

不建议第一版自动计算 attempt_number，因为当前没有独立 Run storage，基于 envelope/event ledger 反推容易产生歧义。

### Fallback lineage

建议在 candidate envelope / event metadata 中保留：

- `fallback_from_request_id`
- `fallback_to_adapter_id`
- `fallback_reason_code`（可选）

fallback adapter 必须重新通过 capability 支持性与 guardrail preflight。

## Guardrail 与 approval 规则

Retry / fallback 必须重新执行 guardrail preflight。

禁止假设：

- 旧 run 通过 preflight，新 run 就自动通过。
- 旧 approval 可自动覆盖新 run。
- fallback adapter 风险等级与原 adapter 相同。

如果 retry/fallback 新计划触发 `needs_approval`：

- dry-run 返回 `needs_approval` 摘要。
- 不创建 approval request，除非后续单独设计 controlled write。

## 与 `orchestration run --commit` 的关系

第一版 retry/fallback dry-run 只生成新的 run plan，不改变 `orchestration run --commit` 的现有语义。

后续 commit 可以复用现有 run commit A+B：

- A：导出新的 envelope draft。
- B：追加 lifecycle events。

差异只在于 candidate envelope / event metadata 需要带 lineage 字段。

## 回滚边界

本设计阶段不实现 retry/fallback commit，因此暂无新增回滚逻辑。

后续若实现 commit，应继续沿用：

- A 成功 B 失败：删除 A，回滚 B。
- post-check 失败：先回滚 B，再回滚 A。
- 不留下半成功 lineage。

## 验收标准

进入实现前，设计应满足：

- retry 与 fallback 语义不混淆。
- 每次 retry/fallback 都生成新 request_id。
- 每次 retry/fallback 都重新 route / preflight / dry-run。
- 不自动执行真实 adapter。
- 不自动复用 approval。
- 不新增 DB / service / UI。
- 不要求第一版扩展 event schema enum。

## 下一步建议

建议下一拍先实现 retry/fallback dry-run preview，而不是直接实现 commit。

推荐顺序：

1. `orchestration run --retry-of <request_id> --dry-run`
2. `orchestration run --fallback-from <request_id> --fallback-to <adapter_id> --dry-run`
3. 补 release notes
4. 再决定是否进入 retry/fallback commit 设计
