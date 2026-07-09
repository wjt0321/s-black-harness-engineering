# 61 — Release Notes：Orchestration Run Lifecycle Events

## 阶段定位

本阶段是 Stage 15.9「Orchestration Run Lifecycle Events」的实现收口。

在 `docs/60-orchestration-run-lifecycle-events-design.md` 定义 B 侧 event schema、controlled append、freeze/post-check 与 A+B all-or-nothing 关系之后，本阶段把 `orchestration run --commit` 从 A-only envelope draft export 升级为 A+B controlled write：

- A：写入 adapter execution envelope draft 文件。
- B：向 event ledger 追加 `run_planned` 与 `run_draft_exported` lifecycle events。

本阶段仍不执行真实 adapter、不访问网络、不发送消息、不引入 UI / service / database / 独立 Run storage。

## 已实现能力

### 1. `orchestration run --commit` A+B

命令形态：

```bash
python -m agent_runtime.cli orchestration run \
  --task-id task-20260703-001 \
  --request-id req-20260703-001 \
  --capability read_file \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --commit \
  --expected-plan-hash sha256:... \
  --output drafts/runtime/task-20260703-001/req-20260703-001.envelope.json \
  --events-file tasks/events.jsonl
```

关键语义：

- `--commit` 必须提供 `--output`、`--expected-plan-hash` 与 `--events-file`；缺失返回 `needs_input`，不写 A/B。
- commit 前重新执行 dry-run / preflight；非 `pass` 状态不写 A/B。
- 当前 `plan_hash` 与 `--expected-plan-hash` 不一致时返回 `blocked`，不写 A/B。
- A 写入 envelope draft 后执行 schema validate + inspect post-check。
- B 追加 `run_planned` + `run_draft_exported` 到指定 events ledger。
- B 写入后检查实际落盘 ledger：event schema validation、task/event ledger consistency、runtime ledger audit。
- B 失败时回滚 A（删除刚写入 draft）并回滚 B（按原始 byte size truncate；若 ledger 是本次创建则删除）。

### 2. Run lifecycle event schema

`tasks/event.schema.json` 的 `event_type` enum 新增：

- `run_planned`
- `run_draft_exported`
- `run_blocked`

第一版成功路径只写入 `run_planned` 与 `run_draft_exported`。`run_blocked` 作为 schema 预留，不在当前 commit 失败 / blocked 路径写入。

### 3. 安全输出与 metadata 边界

lifecycle event metadata 仅保留安全摘要字段：

- `request_id`
- `adapter_id`
- `capability`
- `operation`
- `mode`
- `plan_hash`
- `freeze_check`
- `approval_status`
- `envelope_path`（仅 exported event）
- `artifact_type`（仅 exported event）

输出和 event payload 不回显完整 input payload、target 原文、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions、approval reason 原文或 secret match。

## CLI 与文档更新

- `agent_runtime/cli.py`：`orchestration run` 增加 `--events-file`，human / JSON 输出展示 events_file、appended event count 与 event refs。
- `agent_runtime/orchestration_run_commit.py`：实现 A+B commit、event batch 生成、schema/security scan、post-check 与 A/B rollback。
- `tasks/event.schema.json`：新增 run lifecycle event types。
- `docs/10-cli-poc-usage.md`：更新 run commit 示例与边界说明，加入 `--events-file`。
- `docs/53-minimal-orchestration-loop-cli-draft.md`：把 run commit 状态从 A-only 更新为 A+B。
- `docs/58-orchestration-run-controlled-execution-design.md`：标记 A+B 已落地。
- `docs/60-orchestration-run-lifecycle-events-design.md`：标记 B 侧实现已落地。
- `tasks/progress.md`：追加 Stage 15.9 实现账本。

## 测试与验证

新增和更新测试覆盖：

- missing `--events-file` 返回 `needs_input`，不写 A/B。
- matching hash 成功写入 envelope draft 并追加 2 条 lifecycle events。
- event 顺序与 metadata 脱敏。
- B 侧失败时同时回滚 draft 与 events ledger。
- post-check 使用实际落盘 events ledger，而不是临时模拟追加文件。
- CLI JSON / human 输出包含 event refs 与 events_file。
- schema enum 接受 `approval_resolved`、`run_planned`、`run_draft_exported`、`run_blocked`。

本阶段验证：

- `python -m pytest tests -q`：全量通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。
- `git diff --check`：无空白错误。
- CLI smoke：`orchestration run --dry-run` 生成 `plan_hash` 后，`orchestration run --commit --events-file ...` 成功写入 draft，并追加 `run_planned` + `run_draft_exported` 两条 events。

## 已知限制与后续建议

1. **不执行真实 adapter**：本阶段只沉淀 envelope draft 和 lifecycle events，不调用外部系统。
2. **`run_blocked` 暂不写入**：schema 已预留，但当前 blocked / needs_approval / hash mismatch 路径仍保持不写 A/B。
3. **Run 仍无独立持久集合**：一次 run 继续由 `(task_id, request_id, envelope_path)` + lifecycle events 代理。
4. **read model 尚未消费 lifecycle events**：`task events` 可自然显示 lifecycle events；`orchestration run list/inspect` 后续可选择纳入 event trail，但当前不强制。
5. **retry / fallback 与 `orchestration task submit --commit` 仍未实现**。

## 阶段结论

Stage 15.9 已完成：`orchestration run --commit` 从 A-only controlled write 升级为 A+B controlled write，run 侧最小闭环现在同时具备可审阅 plan freeze、envelope draft 产物和 event ledger 生命周期痕迹。

下一步可选择继续增强 run read model 对 lifecycle events 的消费，或进入下一批 orchestration 写入设计（例如 task submit commit、retry / fallback），但真实 adapter execution 仍应继续保持关闭。
