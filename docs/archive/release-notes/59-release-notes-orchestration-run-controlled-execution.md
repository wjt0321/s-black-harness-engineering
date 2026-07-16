# 59 — Release Notes：Orchestration Run 受控执行第一版

## 阶段定位

本阶段是 Stage 15.6「Orchestration Run 受控执行设计」的实现收口。

在 `docs/58-orchestration-run-controlled-execution-design.md` 把 run dry-run / commit 的产物形态、freeze guard、event/artifact/evidence 沉淀规则和 rollback 策略定清楚之后，本阶段实际落地了 run 侧第一版命令：

- `orchestration run --dry-run`：只读 run plan preview + 稳定 `plan_hash`。
- `orchestration run --commit`：A-only controlled write，把已审阅 run plan 沉淀为 envelope draft/export 文件。

这两个命令把 52 定义的“中枢台最小编排闭环”中“执行受控运行”这一步跑了起来，但仍然不执行真实 adapter、不访问网络、不引入服务/数据库/UI。

## 已实现的命令

### 1. `orchestration run --dry-run`（只读）

输入 `task_id`、`request_id`、`requested_capability`（可选 `--adapter` / `--operation` / `--target` / `--tasks-file`），输出安全 run plan preview：

- `status`
- `task_id` / `request_id` / `requested_capability`
- `mode` = `dry-run`
- `route` 安全摘要：`selected_adapter_id`、`capability`、`operation`、`risk_level`、`requires_approval`、`requires_dry_run`、`fallback_candidates`、`routing_reason`
- `preflight` 安全摘要：`status`、`effective_mode`、`finding_count`、`blocking_findings` 的 rule_id/severity/message
- `candidate_envelope_summary`：artifact_count、request_id、adapter_id、operation、preflight_status、requires_approval
- `candidate_events_summary`：event_type、task_id、request_id、安全 metadata_keys
- `artifact_candidate_refs`：artifact 安全引用（类型、request_id、adapter_id、operation）
- `evidence_candidate_refs`：当前为候选空列表
- `plan_hash`：基于稳定安全字段生成的 sha256，供后续 commit freeze guard 使用
- `constraints` / `findings` / `next_action`

边界：

- 不写 ledger、不写 envelope/draft、不执行 adapter、不访问网络。
- 若传入 `--commit` 会返回 `needs_input` 并提示使用 `--dry-run`。
- `--adapter` 显式指定但不支持该 capability 时返回 `blocked` 并给出 fallback candidates。
- 缺失 `--operation` / `--target` 而 adapter 要求时返回 `needs_input`，不猜测。
- 输出脱敏，不打印完整 input payload、target 原文、secret、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions。

### 2. `orchestration run --commit`（受控写入，A-only）

第一版仅生成 envelope draft/export 文件，不追加 event ledger、不执行真实 adapter、不引入独立 Run storage。

命令形态：

```bash
# 1. 先 dry-run 拿到 plan_hash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --dry-run \
  --json

# 2. 用匹配的 plan_hash commit（仅沉淀 envelope draft）
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability git_push \
  --adapter github-cli \
  --operation git_push \
  --target origin/main \
  --commit \
  --expected-plan-hash sha256:... \
  --output drafts/runtime/task-20260703-001/req-20260703-001.envelope.json
```

关键语义：

- 必须显式 `--dry-run | --commit` 二选一，不允许静默 commit。
- `--commit` 必须提供 `--output` 与 `--expected-plan-hash`，缺失返回 `needs_input`，不写。
- commit 前会重新调用 dry-run/preflight 生成当前 plan；非 `pass` 状态（含 `needs_approval` / `blocked` / `needs_input` / `error`）均不写。
- `--expected-plan-hash` 与当前 plan hash mismatch 时返回 `blocked`，不写。
- `--output` 必须位于 `drafts/runtime/` 下、为 `.json`、不覆盖已存在文件；写入后做 schema validate + inspect post-check，失败删除新文件回滚。
- 复用 `runtime_draft_export` 的 controlled-write helper：路径校验、secret/public scan、写入、post-check、rollback。
- 第一版不追加 run lifecycle events，不变更 `tasks/event.schema.json`。
- `plan_hash` 覆盖 task_id、request_id、capability、selected_adapter_id、operation、target 安全摘要、mode、route/preflight 关键字段、candidate envelope/event 指纹；不覆盖 timestamp、event_id、input payload、target 原文。

输出字段：

- `status` / `task_id` / `request_id` / `requested_capability` / `mode` = `commit`
- `plan_hash` / `expected_plan_hash` / `freeze_check`
- `dry_run_summary`：route/preflight/candidate_envelope_summary 安全子集
- `write_summary`：output、committed、rolled_back、post_validate、post_inspect、artifact_counts
- `artifact_ref`：type = `envelope_draft`、path、request_id、adapter_id、operation
- `findings` / `next_action`

## 资源与产物边界

- **Task**：commit 读取现有 task ledger 作为上下文；task 不存在或已终态时直接返回 `error` / `blocked`，不写产物。
- **Run**：仍无独立持久集合；一次 run 继续由 `(task_id, request_id, envelope_path)` 代理。
- **Approval**：commit 不处理 approval resolve；preflight `needs_approval` 时 commit 不写产物，必须走 `orchestration approval resolve` 后重新 preflight/run。
- **Artifact**：commit 产物是新的 envelope draft 文件，结构与 `runtime plan --draft-json` 兼容；当前仍为 envelope-scoped，未引入独立 Artifact storage。
- **Evidence**：commit 不生成真实 evidence（不执行 adapter）；evidence_candidate_refs 为候选空列表。
- **Report**：未新增 report 产物；如需查看状态，仍使用现有 `orchestration report generate` / `runtime report` 实时聚合。
- **Event**：第一版 commit 不追加 event ledger；B 侧 run lifecycle events 作为后续 immediate follow-up。

## Schema 变更

- 无。第一版 A-only 不追加 events，因此未变更 `tasks/event.schema.json`。

## 安全边界

- 不执行真实 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件（仅回滚自己刚刚创建的文件）。
- 不原地修改输入 envelope。
- 不引入服务、API、数据库、UI。
- 不回显完整 `input` payload、target 原文、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- commit 产物文件写入前做 secret scan / public scan，命中则 blocked 不写。

## 测试与验证

- `python -m pytest tests/test_orchestration_run_dry_run.py -q`：13 个测试全部通过。
- `python -m pytest tests/test_orchestration_run_commit.py -q`：11 个测试全部通过。
- `python -m pytest tests -q`：全量通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。
- `git diff --check`：无空白错误。
- GitHub Actions CI：在 Python 3.11 / 3.12 上 pytest + doctor + ledger smoke checks + public_scan 全部通过。

## 文档更新

- 新增本文档 `docs/archive/release-notes/59-release-notes-orchestration-run-controlled-execution.md`。
- 更新 `docs/00-index.md`：在中枢台后端主线与发布/阶段收口列表中加入 59。
- 更新 `docs/02-roadmap.md`：Stage 15.6/15.7/15.8 状态调整为 run dry-run / commit A-only 已落地，B lifecycle events 仍后续。
- 更新 `docs/10-cli-poc-usage.md`：把 `orchestration run --commit` 从草案标记为已存在命令，并补充示例。
- 更新 `docs/archive/53-minimal-orchestration-loop-cli-draft.md`：同步 run dry-run / run commit 状态。
- 更新 `docs/58-orchestration-run-controlled-execution-design.md`：标记 commit A-only 已落地，B 仍后续。
- 更新 `README.md` / `README.en.md`：同步 Stage 15.6/15.7/15.8 状态与已落地能力列表。
- 更新 `tasks/progress.md`：追加 2026-07-09 阶段收口记录。

## 已知限制与后续建议

1. **B 侧 run lifecycle events 仍未实现**：commit 第一版只沉淀 envelope draft，未追加 `run_planned` / `run_draft_exported` / `run_blocked` 等事件；后续如需状态回放，需先在 `tasks/event.schema.json` 新增 enum 值并补测试。
2. **`orchestration task submit --commit` 仍未实现**：task 提交仍使用现有 `runtime task create --commit`。
3. **retry / fallback 自动化仍留在草案**：需要更多运行时数据和 run 存储设计后再实现。
4. **Run / Approval / Artifact 仍为 envelope-scoped + event-backed**：没有独立 Run 集合资源；跨 envelope run 历史查询需等后续存储设计。
5. **真实 adapter execution、网络访问、消息发送、UI/服务/数据库均未开放**。

## 阶段结论

Stage 15.6/15.7/15.8 目标已达成：从 design gate 迈入了 run 侧第一版 controlled execution，实现了 dry-run preview + A-only commit，且仍然保持“guardrail 是长期内核，但不阻塞主线”的原则。下一步建议优先补 B 侧 run lifecycle events 的 event schema + controlled append 设计/实现，或先写 60 设计 gate 明确 run event 与 ledger 的交互边界。
