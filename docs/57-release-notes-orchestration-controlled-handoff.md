# 57 — Release Notes：Orchestration Controlled Handoff 第一版

## 阶段定位

本阶段是 Stage 15.5「Orchestration 受控写入边界」的实现收口。

在 `docs/56-orchestration-controlled-write-boundary.md` 把 dry-run / commit 语义、capability routing handoff、approval resolve 安全边界定清楚之后，本阶段实际落地了第一批 handoff / controlled-write 命令：

- `orchestration route preview`：只读 capability routing preview。
- `orchestration preflight`：只读 routing + guardrail 聚合 handoff。
- `orchestration approval resolve`：第一条 orchestration 命名空间下的受控写入命令，采用 event-ledger append 方案记录审批决议。

这三个命令把 52 定义的“中枢台最小编排闭环”中“预览路由 → 门禁预检 → 审批决议”这一段跑了起来，但仍然不执行真实 adapter、不访问网络、不引入服务/数据库/UI。

## 已实现的命令

### 1. `orchestration route preview`（只读）

输入 task intent（`requested_capability` + 可选 `--task-id` / `--adapter` / `--mode`），输出安全 routing decision：

- `selected_adapter_id`
- `capability`
- `operation`（仅在 adapter `input_schema` 要求时推导，否则为 `null`）
- `requested_mode` / `selected_mode`
- `risk_level`
- `requires_approval` / `requires_dry_run`
- `fallback_candidates`
- `routing_reason`
- `constraints`
- `next_action`

边界：

- 不写 ledger、不写 envelope、不执行 adapter、不访问网络。
- `--adapter` 显式指定但不支持该 capability 时返回 `blocked` 并给出 fallback candidates。
- 请求 `--mode commit` 时，若 adapter 为 external / destructive / privileged 或 `requires_approval`，`selected_mode` 会被强制降级为 `dry-run`；route preview 本身仍只读。
- 输出脱敏，不打印完整 adapter metadata 或 input payload。

### 2. `orchestration preflight`（只读）

先调用 `orchestration route preview` 得到 routing decision；若 routing 不通过，直接返回其状态并不继续 guardrail。否则用现有 `policy.check_action` 做 guardrail preflight，输出聚合结果：

- `status`
- `requested_capability` / `task_id`
- `requested_mode` / `selected_mode` / `effective_mode`
- `route` 安全摘要
- `guardrail` 安全摘要
- `requires_approval` / `requires_dry_run`
- `constraints` / `findings`
- `next_action`

边界：

- 不写 ledger、不写 envelope、不执行 adapter、不访问网络。
- `--operation` / `--target` 缺失时，若 adapter `input_schema` 要求则返回 `needs_input`，不猜测。
- `--mode commit` 时，若 routing 或 guardrail 任一要求 dry-run / approval，则 `effective_mode` 强制为 `dry-run`；preflight 本身仍只读。
- 输出不回显完整 `input` payload、target 原文、secret 或 raw adapter metadata。

### 3. `orchestration approval resolve`（受控写入）

当前 orchestration 命名空间中唯一会写 ledger 的命令。它只记录审批决议，不直接执行原请求，不修改输入 envelope。

命令形态：

```bash
python -m agent_runtime.cli orchestration approval resolve \
  --approval-id appr-20260703-001 \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --decision granted \
  --reason "reviewed, safe to proceed" \
  --envelope drafts/runtime/task-20260703-001/req-20260703-001.envelope.json \
  --events-file tasks/events.jsonl \
  --dry-run

python -m agent_runtime.cli orchestration approval resolve \
  ... \
  --commit
```

关键语义：

- 必须显式 `--dry-run | --commit` 二选一，不允许静默 commit。
- `--decision` 只允许 `granted` / `denied` / `expired`。
- `--reason` 必填，长度限制 1-500 字符。
- 会校验 `approval_id` 存在于 envelope，且传入的 `task_id` / `request_id` 与 approval scope / request 一致；不一致返回 `blocked` 且不写。
- `--dry-run` 只生成 `approval_resolved` event preview，不写 ledger。
- `--commit` 复用 `runtime event append --commit` 的受控写入机制，向 event ledger 追加一条 `approval_resolved` event；写后做 schema / ledger / runtime audit 校验，失败按原始 byte size 回滚。
- event metadata 只保留 `approval_id`、`request_id`、`decision`、`reason_hash`、`reason_length`、`envelope_path`；不保留完整 reason，不保存 `decision_ref`。
- `granted` 后仍必须重新发起新的 `orchestration preflight` / `orchestration run`，不能复用旧 preflight 直接 commit。
- `denied` / `expired` 生成拒绝/过期 event，原 `approval_record` 保持 pending，decision 作为新记录追加。

## Schema 变更

- `tasks/event.schema.json` 的 `event_type` enum 中新增 `"approval_resolved"`。

## 资源与产物边界

- **Task / Event**：`approval resolve --commit` 向现有 event ledger 追加单行，仍走现有 controlled-write 路径。
- **Run / Approval / Artifact**：没有引入独立持久集合；approval resolve 读取 envelope 中的 `approval_record`，把 decision 以 event 形式写入 ledger。
- **Report**：未新增 report 产物；如需查看审批后状态，仍使用现有 `orchestration report generate` / `runtime report` 实时聚合。

## 安全边界

- 不执行真实 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不修改输入 envelope。
- 不引入服务、API、数据库、UI。
- 不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- reason 只以 hash / length 形式进入 event metadata；CLI 输出不暴露 reason 原文。

## 测试与验证

- `python -m pytest tests/test_orchestration_route_preview.py -q`：通过。
- `python -m pytest tests/test_orchestration_preflight.py -q`：通过。
- `python -m pytest tests/test_orchestration_approval_resolve.py -q`：13 个测试全部通过。
- `python -m pytest tests -q`：全量通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。
- `git diff --check`：无空白错误。
- GitHub Actions CI：在 Python 3.11 / 3.12 上 pytest + doctor + ledger smoke checks + public_scan 全部通过。

## 文档更新

- 新增本文档 `docs/57-release-notes-orchestration-controlled-handoff.md`。
- 更新 `docs/00-index.md`：在中枢台后端主线与发布/阶段收口列表中加入 57。
- 更新 `docs/02-roadmap.md`：Stage 15.5 状态从「design gate」调整为「第一批 controlled handoff / approval resolve 已落地」。
- 更新 `docs/10-cli-poc-usage.md`：把三个命令从草案标记为已存在命令，并补充示例。
- 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：同步 route preview / preflight / approval resolve 状态。
- 更新 `docs/56-orchestration-controlled-write-boundary.md`：标记三个命令已落地，更新产物形态与下一步。
- 更新 `README.md` / `README.en.md`：同步 Stage 15.5 状态与已落地能力列表。
- 更新 `tasks/progress.md`：追加 2026-07-09 阶段收口记录。

## 已知限制与后续建议

1. **`orchestration run --commit` 仍未实现**：run 侧受控写入需要先在 draft/export 产物形态、freeze guard、event/artifact/evidence 沉淀规则上达成一致。
2. **`orchestration task submit --commit` 仍未实现**：task 提交仍使用现有 `runtime task create --commit`。
3. **retry / fallback 自动化仍留在草案**：需要更多运行时数据和 run 存储设计后再实现。
4. **Approval 仍为 envelope-scoped + event-backed**：没有独立 Approval 集合资源；跨 envelope 审批历史查询需等后续存储设计。
5. **真实 adapter execution、网络访问、消息发送、UI/服务/数据库均未开放**。

## 阶段结论

Stage 15.5 目标已达成：从 read-model CLI 迈入了第一批 controlled handoff / controlled-write 命令，且仍然保持“guardrail 是长期内核，但不阻塞主线”的原则。下一步建议先明确 `orchestration run --dry-run/--commit` 的 draft/export 产物形态和 freeze guard，再进入 run 侧实现。
