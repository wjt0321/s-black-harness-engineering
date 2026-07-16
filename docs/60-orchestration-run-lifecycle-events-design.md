# 60 — Orchestration Run Lifecycle Events 设计

## 阶段定位

`docs/archive/release-notes/59-release-notes-orchestration-run-controlled-execution.md` 已经把 `orchestration run --dry-run` 落地；本文档所设计的 B 侧 run lifecycle events 也已实现：

- `orchestration run --dry-run`：只读 run plan preview + 稳定 `plan_hash`。
- `orchestration run --commit` A+B：生成 envelope draft/export 文件，并追加 `run_planned` + `run_draft_exported` lifecycle events 到 event ledger，all-or-nothing 回滚。

本文档既是进入 B 侧实现前的 design gate，也作为实现后的设计记录。目标不是放开真实 adapter execution，而是让 run commit 具备可回放、可审计的 event trail，同时保持受控写入边界。

遵循的原则仍然是：

- guardrail 是长期内核，但不阻塞主线。
- 积木式可插拔：run lifecycle events 只补充 event trail，不替代 envelope draft export，也不改变 dry-run/commit 语义。
- 不引入 DB / service / UI；写入仍然受控、显式、可审计、可回滚。
- 当前阶段 commit 仍不等于真实外部执行；仍然禁止网络访问、消息发送、真实 adapter execution、文件系统写删（受控写入路径除外）。

## 候选 event types

建议第一版在 `tasks/event.schema.json` 的 `event_type` enum 中新增以下值：

| event_type | 触发时机 | 是否进入 schema enum | 说明 |
|:---|:---|:---:|:---|
| `run_planned` | dry-run / commit 前重新生成 plan 并通过 freeze/preflight 后 | 是 | 表示“run plan 已生成且当前上下文允许继续”。 |
| `run_draft_exported` | envelope draft 文件成功写入并通过 post-check 后 | 是 | 表示“envelope draft 已受控导出”。 |
| `run_blocked` | commit 因 preflight/approval/hash mismatch/path/post-check 被阻断后 | 是 | 表示“run 被阻断及原因”。 |
| `run_commit_failed` | A 或 B 写入失败且 rollback 也失败，或出现不可恢复错误时 | 否（预留讨论） | 记录失败事件容易引发歧义：写入失败本身意味着 event 也可能不可靠。第一版不建议写入该事件；失败信息由 CLI 输出和日志承担。 |

说明：

- 进入 schema enum 的事件必须具有清晰、无歧义的触发条件，并且能被现有 ledger consistency 规则理解。
- `run_commit_failed` 暂不进入 enum，待后续观察是否需要专门的“失败审计事件”。
- 这些事件与现有 task lifecycle 事件（`created`、`status_changed`、`blocked`、`finished` 等）并存，但语义上属于 run 侧；`task_id` 用于关联 task，metadata 中的 `request_id` 用于关联 run/request。

## event payload 安全字段

Run lifecycle event 必须复用现有 `tasks/event.schema.json` 的基础字段，并在 `metadata` 中只保留安全摘要：

### 顶层字段

- `event_id`：稳定生成，避免冲突。
- `task_id`：关联 task ledger。
- `timestamp`：ISO 8601。
- `actor`：固定为 `cli` 或类似安全默认值，不写内部身份称谓。
- `event_type`：`run_planned` / `run_draft_exported` / `run_blocked`。
- `message`：短摘要，如 `"Run plan generated and frozen."`，不塞完整 reason 或 target 原文。
- `metadata`：只含以下安全字段。

### metadata 安全字段

- `request_id`
- `adapter_id`
- `capability`
- `operation`
- `mode`（`dry-run` / `commit`）
- `plan_hash`
- `envelope_path`：相对于项目根目录的路径。
- `freeze_check`：`pass` / `failed` / `not_run`
- `approval_status`：`not_required` / `pending` / `granted` / `denied` / `expired`（仅当相关时）
- `artifact_type`：`envelope_draft`
- `blocking_reason` / `rule_id`（仅 `run_blocked`）：规则 id 或简短原因标签，不回显完整 payload。

### 禁止字段

- 完整 `input` payload。
- 用户提供的原始 `target` 完整值。
- `raw_ref`、`decision_ref`、`payload_refs`。
- evidence descriptions。
- `--reason` 原文。
- secret / token / credential match。
- 绝对路径、内部 endpoint、环境变量。

## B 侧 controlled append 方案

### 复用现有机制

B 侧优先复用 `runtime event append --commit` / `runtime event import --commit` 的受控写入思路：

- 写前记录原始文件 byte size。
- 写入后做 `task validate --schema event`、`task check-ledger`、`runtime check-ledger`（如 envelope 与 ledger 有关联）。
- 失败按原始 byte size truncate 回滚。

### 单条 vs 批量

- 如果只追加一条 event（例如只做 `run_planned`），使用 append 语义即可。
- 如果一次 commit 需要追加多条 lifecycle events（`run_planned` + `run_draft_exported`），优先使用 import batch 语义，把整批事件作为一个连续 JSONL block 写入，确保 all-or-nothing。

### 事件顺序

正常成功路径：

1. `run_planned`：plan 已生成并通过 freeze/preflight。
2. envelope draft 文件写入 A。
3. `run_draft_exported`：envelope draft 已成功导出并通过 post-check。

`run_blocked` 仅在 A/B 写入前被阻断时使用，且只写一条 blocked 事件；不写失败细节 payload。

## 与 envelope draft commit 的组合策略

### 当前 A+B

- 生成 envelope draft/export 文件（A）。
- 追加 `run_planned` + `run_draft_exported` lifecycle events 到 event ledger（B）。

### A+B 组合流程

组合 commit 流程：

1. 重新 dry-run / preflight / freeze guard 校验；任一失败直接返回，不写 A/B。
2. 校验通过后：
   - A. 生成 envelope draft 文件。
   - B. 追加 run lifecycle events block（`run_planned` + `run_draft_exported`）。
3. all-or-nothing：
   - 若 A 失败，不写 B。
   - 若 B 失败，删除 A 生成的文件，并按 byte size 回滚 B 已追加内容。
   - 成功后返回 `envelope_path`、`event_ids`、`plan_hash`、`appended_bytes`。

### `--events-file` 要求

B 第一版建议要求显式 `--events-file`，避免默认写真实仓库 `tasks/events.jsonl`。若未提供 `--events-file`，B 侧返回 `needs_input`。

## freeze guard 与 idempotency

### plan_hash 不变

- B 侧事件不改变 `plan_hash` 语义。
- `plan_hash` 仍由 dry-run plan 的安全字段决定（task_id、request_id、capability、adapter_id、operation、target 安全摘要、mode、route/preflight 关键字段、candidate envelope/event 指纹）。
- `plan_hash` 不覆盖 event_id、timestamp、ledger file path。

### event_id 生成

- 必须避免与现有 event ledger 冲突。
- 建议基于 `request_id` + `event_type` + 单调计数或时间戳哈希生成，例如 `evt-{request_id}-{event_type}-N`。
- 生成后需检查 event ledger 是否已存在相同 `event_id`；若存在，返回 `error`，不写。

### 重复 commit 防护

- 同一 `--output` 路径已存在文件 -> `blocked`（A 已存在）。
- 同一 `plan_hash` + `request_id` 已成功 commit 过 -> 第二版可考虑通过查询 event ledger 检测并 `blocked`；第一版至少依赖 output path 已存在拦截。
- 不覆盖、不重复 append。

## approval / blocked 分支

### preflight needs_approval

- 不写 A/B，返回 `needs_approval`。
- 不生成 `run_blocked`。

### hash mismatch

- 不写 A/B，返回 `blocked`。
- 第一版不建议写 `run_blocked` 事件：写事件本身也是写入，且 mismatch 属于审阅上下文变化，应由 CLI 输出和日志承载。

### terminal task / path invalid / scan hit / post-check failure

- 不写 A/B。
- post-check 失败时 A 已生成文件需删除回滚；B 未写或已写部分按 byte size 回滚。

## read-model 影响

### `orchestration run list`

- 当前为 envelope-scoped read model。
- B 侧实现后，**可考虑**从 event ledger 读取 `run_planned` / `run_draft_exported` 事件来补充 run lifecycle 摘要，但本设计不强制要求；优先保持 envelope-scoped 不变，降低风险。

### `task events`

- 会自然显示 run lifecycle events，因为它们是标准 task event。

### `orchestration report generate`

- 继续 runtime-report-backed。
- 后续可再决定是否把 lifecycle events 纳入 report 聚合。

## 验收标准

进入 B 侧实现前必须明确：

1. `tasks/event.schema.json` 中新增 enum 值并补测试。
2. JSON 输出结构（含 `status`、稳定 `plan_hash`、写入证据、`event_ids`、`next_action`）。
3. 人类可读输出结构（紧凑、脱敏）。
4. 测试覆盖：
   - dry-run 不写文件 / ledger / events。
   - commit A+B 成功并产生 envelope draft + lifecycle events。
   - A 成功 B 失败回滚（删除 draft + byte size truncate）。
   - hash mismatch / missing expected hash / missing events-file 的稳定 blocked / needs_input 行为。
   - preflight needs_approval 时 A/B 不写。
   - 输出和 event ledger 中不出现完整 input / secret / raw_ref / decision_ref / payload_refs / evidence descriptions / reason 原文。
5. 通过 `python -m pytest tests -q`。
6. 通过 `python -m agent_runtime.cli doctor`。
7. 通过 `python tools/public_scan.py`。
8. 通过 `git diff --check`。

## 与 51 / 52 / 53 / 54 / 56 / 57 / 58 / 59 的关系

- `docs/51-backend-first-api-boundary.md` 定义了 Run 作为顶层资源；本文档把 Run 的生命周期事件沉淀规则细化到可执行层面。
- `docs/52-minimal-orchestration-loop.md` 描述了“执行受控运行”这一步；本文档说明这一步成功后应留下哪些事件轨迹。
- `docs/archive/53-minimal-orchestration-loop-cli-draft.md` 提供了 `orchestration run` 命令草案；本文档为其 B 侧扩展提供设计前置。
- `docs/54-backend-preparation-before-ui.md` 定义了执行页 read model；本文档说明 lifecycle events 如何补充执行页数据。
- `docs/56-orchestration-controlled-write-boundary.md` 定义了 dry-run/commit 统一语义；本文档将其扩展到 event ledger append。
- `docs/archive/release-notes/57-release-notes-orchestration-controlled-handoff.md` 记录了 route preview / preflight / approval resolve 落地；这些命令仍是 run commit 的前置。
- `docs/58-orchestration-run-controlled-execution-design.md` 定义了 A/B 产物策略；本文档把 B 侧 event append 的 schema、payload、顺序、回滚规则讲清楚。
- `docs/archive/release-notes/59-release-notes-orchestration-run-controlled-execution.md` 记录了 A-only 落地；本文档是 B 侧实现的直接前置。

## 实现状态

- `tasks/event.schema.json` 已新增 `run_planned`、`run_draft_exported`、`run_blocked` enum 值，并补测试。
- `orchestration run --commit` 已按 A+B 实现：先 A（envelope draft export），再 B（lifecycle events batch append），all-or-nothing 回滚。
- commit 要求显式 `--events-file`，默认不写真实仓库 ledger。

## 下一步建议

1. 观察 A+B commit 在实际使用中的稳定性，再决定是否引入 `run_blocked` 事件写入或 `run_commit_failed` 预留讨论。
2. 在此稳定前，不实现 retry / fallback 自动化、`orchestration task submit --commit`、真实 adapter execution。
