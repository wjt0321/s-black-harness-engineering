# 58 — Orchestration Run 受控执行设计

## 阶段定位

`docs/57-release-notes-orchestration-controlled-handoff.md` 已经把第一批 handoff / controlled-write 命令落地：

- `orchestration route preview`：只读 capability routing preview。
- `orchestration preflight`：只读 routing + guardrail 聚合 handoff。
- `orchestration approval resolve`：event-ledger append 方案记录审批决议。

本文档是进入 `orchestration run --dry-run / --commit` 写入实现前的 **design gate**。`orchestration run --dry-run` 与 `--commit` 第一版（A-only envelope draft export）已按本文档实现；B（run lifecycle events append）仍待实现。目标不是放开真实 adapter execution，而是先定义：

1. `orchestration run --dry-run` 输出什么产物、如何生成稳定的 `plan_hash`。
2. `orchestration run --commit` 把已审阅的 run plan 沉淀到哪些受控存储、失败如何回滚。
3. freeze guard（`--expected-plan-hash`、`--require-dry-run`）如何覆盖稳定安全字段、hash mismatch 如何处理。
4. approval handoff 如何与 run commit 衔接：granted 不是执行授权，run commit 仍需重新 preflight。
5. event / artifact / evidence / report 的沉淀规则与状态模型映射。

遵循的原则仍然是：

- guardrail 是长期内核，但不阻塞主线。
- 积木式可插拔：run 命令只负责 orchestration 执行切面，不替代 `runtime plan`、`runtime draft export`、`runtime event append/import`。
- 不引入 DB / service / UI；写入仍然受控、显式、可审计、可回滚。
- 当前阶段 `commit` 仍不等于真实外部执行；仍然禁止网络访问、消息发送、真实 adapter execution、文件系统写删（受控写入路径除外）。

## 命令候选形态

建议第一版命令形态：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260709-001 \
  --request-id req-20260709-001 \
  --capability git_push \
  [--adapter github-cli] \
  [--operation git_push] \
  [--target origin/main] \
  [--mode dry-run|commit] \
  [--expected-plan-hash sha256:...] \
  [--require-dry-run] \
  [--dry-run|--commit]
```

说明：

- `--task-id`、`--request-id`、`--capability` 必填。
- `--adapter` 可选：显式指定时校验是否支持 capability；不支持则返回 `blocked`。
- `--operation`、`--target` 可选：若 adapter `input_schema` 要求而缺失，返回 `needs_input`。
- `--mode` 默认 `dry-run`；`commit` 必须显式。
- `--expected-plan-hash`：commit 时校验当前 plan 是否与之前 dry-run 审阅结果一致。
- `--require-dry-run`：commit 必须绑定一次之前成功的 dry-run（可要求同时提供 expected hash）。
- retry / fallback 自动化（`--retry`、`--fallback-to`）不在本阶段实现。

## dry-run 产物形态

`orchestration run --dry-run` 是只读命令，输出一份 **run plan preview**，不写 ledger / envelope / draft。

输出字段建议：

| 字段 | 说明 |
|:---|:---|
| `status` | `pass` / `blocked` / `needs_approval` / `needs_input` / `validation_failed` / `error` |
| `task_id` | 任务 id |
| `request_id` | 请求 id |
| `requested_capability` | 原始 capability |
| `route` | routing decision 安全摘要（`selected_adapter_id`、`capability`、`operation`、`risk_level`、`requires_approval`、`requires_dry_run`、`fallback_candidates`、`routing_reason`） |
| `preflight` | guardrail preflight 安全摘要（`status`、`finding_count`、`blocking_findings` 的 rule_id/severity/message、effective_mode） |
| `candidate_envelope_summary` | 候选 envelope 安全摘要（artifact_count、request_id、adapter_id、operation、preflight_status、requires_approval），不含完整 input payload |
| `candidate_events_summary` | 候选 event 列表摘要（event_type、task_id、request_id、actor、安全 metadata_keys），不含 message 全文 |
| `artifact_candidate_refs` | artifact 安全引用列表（类型、request_id、run context），不含 raw payload |
| `evidence_candidate_refs` | evidence 安全引用列表（类型、producer、hash/safe summary），不含 description 正文 |
| `plan_hash` | 基于稳定安全字段生成的 hash，供后续 commit freeze guard 使用 |
| `mode` | `dry-run` |
| `constraints` | 应用的 policy / workspace / capability 约束安全摘要 |
| `next_action` | 下一步建议 |

dry-run 输出禁止包含：

- 完整 input payload。
- secret / token / credential。
- raw adapter metadata（内部 endpoint、私有配置）。
- 用户提供的原始 target 完整值（可保留类型或脱敏摘要）。
- `raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions。

### plan_hash 覆盖字段

`plan_hash` 应覆盖以下稳定且安全的字段（按项目现有 hash 风格，建议 sha256）：

- `task_id`
- `request_id`
- `requested_capability`
- `selected_adapter_id`
- `operation`（如有）
- `target_safe_summary`（target 的脱敏摘要，而非原文）
- `mode`
- `route.risk_level`
- `route.requires_approval`
- `route.requires_dry_run`
- `preflight.status`
- `preflight.effective_mode`
- `candidate_envelope_summary` 关键指纹（version、artifact_count、request_id、adapter_id、operation、preflight_status）
- `candidate_events_summary` 关键指纹（event_type 序列、task_id、request_id）

`plan_hash` 不覆盖：

- 完整 input payload。
- target 原文。
- reason / message 全文。
- timestamp、event_id 等每次 dry-run 可能变化但不影响计划语义的可再生字段（或仅覆盖事件类型序列而不覆盖具体 id）。

## commit 产物形态

`orchestration run --commit` 不执行真实外部 adapter；它只把已审阅的 run plan 沉淀到项目内受控存储。

第一版已按 **A-only** 落地：只生成 envelope draft/export 文件，不追加 run lifecycle events。B（run lifecycle events append）作为 immediate follow-up，仍在设计/实现队列中。

设计目标建议按 **A + B 组合产物策略** 演进，但做成 all-or-nothing：

- **A. envelope draft export**：生成新的 adapter execution envelope draft 文件（通过 `runtime draft export --commit` 机制）。
- **B. run lifecycle events**：追加一条或多条 run 生命周期 event 到 event ledger（通过 `runtime event append/import --commit` 机制）。

### A. envelope draft export

- 输出路径建议在 `drafts/runtime/<task_id>/<request_id>.envelope.json`。
- 内容包含 `adapter_request`、`approval_record`（如需）、`execution_event` 等 artifact，结构与 `runtime plan --draft-json` 产物兼容。
- 必须走 `runtime draft export --commit` 的 pre-check / secret scan / public scan / post-inspect / 禁止覆盖 / 失败删除新文件回滚机制。
- 不原地修改输入 envelope；如果同路径已存在文件，返回 `blocked` 而不是覆盖。

### B. run lifecycle events

建议第一版至少追加一条 `run_planned` event；如需更细状态，可追加：

- `run_planned`：run plan 已生成并准备沉淀。
- `run_draft_exported`：envelope draft 文件已导出。
- `run_blocked`：run 因 guardrail / approval / hash mismatch 被阻断。

> 注意：这些 event_type 属于候选提案，若进入实现阶段，需要在 `tasks/event.schema.json` 的 enum 中新增并补测试。

event 安全字段：

- `event_id`、`task_id`、`timestamp`、`actor`、`event_type`、`message`。
- `metadata`：只保留 `request_id`、`adapter_id`、`capability`、`operation`、`mode`、`plan_hash`、`envelope_path`、`approval_status` 等安全字段。
- 不保留完整 input、target 原文、reason 原文、`decision_ref`、evidence descriptions。

### all-or-nothing / rollback

组合产物策略必须保证 all-or-nothing：

1. 先执行所有 dry-run / preflight / freeze guard 校验；任一失败直接返回，不写任何产物。
2. 校验通过后，按顺序执行：
   - 生成 envelope draft 文件（A）。
   - 追加 run lifecycle events（B）。
3. 若 A 失败，不写 B；若 B 失败，必须回滚 A（删除刚生成的 envelope draft 文件）并按 byte size 回滚 B 已追加的 event ledger 内容。
4. 成功后返回写入证据：`envelope_path`、`event_ids`、`plan_hash`、`appended_bytes`。

> 第一版已降级为只做 A（envelope draft export），把 B 作为 immediate follow-up。当前实现不追加 event ledger，也不变更 `tasks/event.schema.json`。

## freeze guard

### dry-run 输出 `plan_hash`

dry-run 必须输出稳定的 `plan_hash`，作为审阅锚点。

### commit 支持 `--expected-plan-hash`

- commit 前重新计算当前 plan hash。
- 若 `--expected-plan-hash` 提供且 mismatch，返回 `blocked`，不写任何产物。
- hash mismatch 不是 error，而是“审阅上下文已变，需要重新 dry-run”。

### commit 支持 `--require-dry-run`

- 若提供 `--require-dry-run`，commit 必须要求同时提供 `--expected-plan-hash`（或从本地缓存读取最近一次 dry-run hash，但优先要求显式传入）。
- 未提供 expected hash 时返回 `needs_input`。

## approval handoff

### preflight needs_approval 时

- `orchestration run --dry-run` 可正常输出 `needs_approval` 的 plan preview 和 `plan_hash`，但不生成 commit 产物。
- `orchestration run --commit` 在 preflight `needs_approval` 时直接返回 `blocked` / `needs_approval`，不写任何产物。
- next_action 必须提示先走 `orchestration approval resolve`。

### 已有 `approval_resolved` event 时

- `orchestration run --commit` 仍必须重新执行 preflight，确认当前 approval 状态与请求上下文。
- 不可直接复用旧 preflight 结果或旧 `plan_hash` 绕过重新校验。
- granted 只是解除“需要人工决议”这一分支，不是“允许执行 adapter”的授权；当前阶段 commit 仍然只沉淀 draft/event，不执行外部动作。

## state model mapping

### Run

第一版 **不引入独立 Run 持久集合**。一次 run 可由三元组 `(task_id, request_id, envelope_path)` 代理，再加上 event ledger 中的 run lifecycle events 共同描述。

这意味着：

- `orchestration run inspect` 当前仍按 `(task_id, request_id, envelope)` 聚合，与已有实现一致。
- 未来如需 `run list`、`run get by run_id`，需引入独立 Run storage；本阶段不做。

### Event

run 侧引入的候选 event types（如 `run_planned`、`run_draft_exported`、`run_blocked`）应在 `tasks/event.schema.json` 中新增 enum 值，并补对应测试。

### Artifact

envelope draft/export 文件是 artifact candidate，但不是独立 Artifact storage。`orchestration artifact list` 仍 envelope-scoped，从已存在的 envelope 文件中提取 artifact 摘要。

### Evidence

run commit 不生成真实 evidence（因不执行真实 adapter）。如需记录 evidence candidate，只存安全摘要：evidence type、producer adapter_id、safe ref/hash placeholder、长度/存在性标记。不回显 evidence description 正文。

### Report

`orchestration report generate` / `runtime report` 继续 runtime-report-backed，每次实时聚合，不沉淀为独立 Report 集合。

## rollback / post-check

### draft export commit 的 rollback

- 复用 `runtime draft export --commit` 机制：
  - 写入前检查路径安全、不覆盖、目录存在。
  - 写入后对文件做 secret scan / public scan / schema validate / inspect。
  - 若任一 post-check 失败，删除刚生成的文件（如果创建了新文件）或保持未写状态。

### event append/import commit 的 rollback

- 复用 `runtime event append --commit` / `runtime event import --commit` 机制：
  - 写入前记录原始文件 size。
  - 写入后做 `task validate --schema event`、`task check-ledger`、可选 `runtime check-ledger`。
  - 失败按原始 byte size truncate 回滚。

### run commit 组合 rollback

若 A + B 组合实现：

- 若 A 失败，不写 B。
- 若 B 失败，删除 A 生成的文件并按 byte size 回滚 B。
- 回滚失败时返回 `error` 并提示手动恢复。

### post-check 清单

commit 后至少执行：

1. envelope draft schema validation（`adapters/execution-envelope.schema.json`）。
2. envelope consistency check（跨 artifact 引用、approval scope 等）。
3. event ledger schema validation（`tasks/event.schema.json`）。
4. task / event ledger consistency check。
5. runtime check-ledger（如 envelope 与 ledger 有关联）。
6. secret / public scan（针对新生成的 envelope draft 文件）。

## 验收标准

每个新增命令在实现前必须明确：

1. JSON 输出结构（含 `status`、稳定 `plan_hash`、写入证据、`next_action`）。
2. 人类可读输出结构（紧凑、脱敏）。
3. 测试覆盖：
   - dry-run 不写文件 / ledger。
   - commit 成功并产生可追溯产物（envelope draft / event）。
   - commit 失败回滚（删除新文件 / byte size truncate）。
   - hash mismatch / missing expected hash 的稳定 blocked / needs_input 行为。
   - preflight needs_approval 时 commit 不写产物。
   - 已有 `approval_resolved` event 后 commit 仍重新 preflight。
   - 输出中不出现完整 input / secret / raw_ref / decision_ref / payload_refs / evidence descriptions。
4. 通过 `python -m pytest tests -q`。
5. 通过 `python -m agent_runtime.cli doctor`。
6. 通过 `python tools/public_scan.py`。
7. 通过 `git diff --check`。

## 与 51 / 52 / 53 / 54 / 56 / 57 的关系

- `docs/51-backend-first-api-boundary.md` 定义了 Run / Approval / Artifact / Report 等资源与操作边界；本文档把 `Run.execute` 操作的 dry-run/commit 语义细化到可执行层面。
- `docs/52-minimal-orchestration-loop.md` 描述了“执行受控运行”这一步；本文档定义这一步的产物与 freeze guard。
- `docs/53-minimal-orchestration-loop-cli-draft.md` 提供了 `orchestration run` 命令草案；本文档为其进入实现提供设计前置。
- `docs/54-backend-preparation-before-ui.md` 定义了执行页 read model；本文档说明执行页操作入口（run dry-run/commit）在写入侧应如何沉淀产物。
- `docs/56-orchestration-controlled-write-boundary.md` 定义了 dry-run/commit 统一语义；本文档将其应用到 run 命令。
- `docs/57-release-notes-orchestration-controlled-handoff.md` 记录了 route preview / preflight / approval resolve 落地；本文档是 run 侧落地的直接前置。

## 下一步建议

1.  review 并确认本文档中的 A/B 产物策略（建议 A+B，但允许第一版先做 A）。
2.  若采用 B（event append），先在 `tasks/event.schema.json` 中新增候选 event types 并补测试。
3.  ~~实现 `orchestration run --dry-run`：只读 plan preview + `plan_hash`。~~ 已落地。
4.  ~~实现 `orchestration run --commit` A-only：按本文档产物形态沉淀 envelope draft，支持 `--expected-plan-hash` / `--require-dry-run`。~~ 已落地；B（run lifecycle events）仍待实现。
5.  在此稳定前，不实现 `orchestration task submit --commit`、retry / fallback 自动化、真实 adapter execution。
