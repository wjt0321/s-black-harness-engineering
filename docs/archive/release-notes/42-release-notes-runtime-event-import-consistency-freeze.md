# 42 — Release Notes: Runtime Event Import Consistency Freeze

## 阶段定位

本文档标记 `runtime event import` 一致性冻结（consistency freeze）第一版实现完成。它在 `docs/41-runtime-event-import-consistency-freeze.md` 确定的设计基础上，为 dry-run 与 commit 之间增加了最小可用的“审阅上下文一致性”校验层。

## 已实现能力

- `runtime event import --dry-run` 默认附带一致性冻结元数据：
  - `plan_hash`
  - `candidate_fingerprint`
  - `events_ledger_fingerprint`
  - `events_ledger_size_bytes`
  - `events_ledger_line_count`
  - `freeze_mode`（固定为 `advisory`）
- `runtime event import --commit` 新增可选参数 `--expected-plan-hash <hash>`。
- 若 commit 提供了 `--expected-plan-hash`，则在 preflight 之前重算当前 plan hash 并严格比对；不一致直接返回 `blocked`。
- freeze mismatch 不替代 commit 内部 preflight；hash 一致时仍需继续走完整 preflight + append + post-check + rollback。
- 第一版不强制全局 always-on freeze；不提供 `--expected-plan-hash` 时，现有 commit 行为保持不变。
- 第一版不冻结 tasks ledger，不实现 `--require-dry-run`。
- hash / fingerprint 计算稳定、可重复，且不回显 message 等敏感字段。

## 核心实现点

- 修改 `agent_runtime/runtime_event_import.py`：
  - 新增 `_FreezeState` 与 freeze 计算辅助函数：`_sha256_hex`、`_compute_candidate_fingerprint`、`_compute_events_ledger_fingerprint`、`_compute_plan_hash`、`_compute_freeze_state`。
  - `candidate_fingerprint`：对 candidate 文件所有非空原始行按输入顺序用 `\n` 拼接后做 sha256。
  - `events_ledger_fingerprint`：对现有 events ledger 完整 UTF-8 字节做 sha256；文件不存在时 fingerprint 为 `null`。
  - `plan_hash`：对一个稳定的 JSON object 做 canonical `json.dumps(..., sort_keys=True, separators=(",", ":"))` 后再做 sha256。
  - 扩展 `EventImportDryRunResult` 与 `EventImportCommitResult`，承载 freeze 字段。
  - `import_events_dry_run` 在输出中暴露所有 freeze 字段。
  - `import_events_commit` 在 preflight 前先 resolve candidate 路径并计算 freeze；若提供 `--expected-plan-hash` 且不一致，立即返回 `blocked`。
- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--expected-plan-hash` 参数。
  - 渲染函数输出 dry-run freeze 字段与 commit freeze_check / expected_plan_hash / current_plan_hash。

## Plan Hash 输入

plan hash 基于以下稳定字段计算：

```json
{
  "schema_version": 1,
  "mode": "runtime-event-import",
  "candidate_fingerprint": "sha256:...",
  "tasks_file": "tasks/tasks.jsonl",
  "events_file": "tasks/events.jsonl",
  "events_ledger_fingerprint": "sha256:...",
  "events_ledger_size_bytes": 1234,
  "events_ledger_line_count": 12,
  "input_order_preserved": true,
  "all_or_nothing": true
}
```

## 输出摘要

dry-run 通过时的 JSON 示例：

```json
{
  "status": "pass",
  "source": "candidates.jsonl",
  "event_count": 3,
  "blank_line_count": 0,
  "task_count": 2,
  "event_type_counts": {"created": 1, "status_changed": 2},
  "candidate_event_ids_present": ["evt-20260707-002", "evt-20260707-003", "evt-20260707-004"],
  "would_import": true,
  "ledger_check": "pass",
  "freeze_mode": "advisory",
  "candidate_fingerprint": "sha256:...",
  "events_ledger_exists": true,
  "events_ledger_fingerprint": "sha256:...",
  "events_ledger_size_bytes": 1234,
  "events_ledger_line_count": 12,
  "plan_hash": "sha256:..."
}
```

freeze mismatch 时的 JSON 示例：

```json
{
  "status": "blocked",
  "source": "candidates.jsonl",
  "event_count": 0,
  "target_events_file": "tasks/events.jsonl",
  "committed": false,
  "appended_line_count": 0,
  "rolled_back": false,
  "freeze_check": "failed",
  "expected_plan_hash": "sha256:...",
  "current_plan_hash": "sha256:...",
  "findings": [
    {
      "rule_id": "plan-hash-mismatch",
      "severity": "block",
      "action": "deny",
      "message": "Current candidate or ledger context no longer matches the reviewed dry-run plan."
    }
  ],
  "next_action": "Rerun runtime event import --dry-run and review the updated batch before commit."
}
```

## 安全边界

- 输出不回显 candidate 原始 JSON 行、message、metadata values、artifacts payload、evidence description、target/input、raw_ref/decision_ref 或 secret match。
- freeze 字段只包含 hash、相对路径、size、line count 等安全元数据。
- 不访问网络、不执行 adapter、不发送消息、不读取 `.env`/credential、不改写 task ledger、不新增 envelope 写入。

## 测试覆盖

新增 `tests/test_runtime_event_import_freeze.py`，覆盖：

- dry-run 输出包含 freeze 字段。
- 同一输入重复 dry-run，`plan_hash` 稳定一致。
- candidate 文件改一行后 `plan_hash` 改变。
- events ledger 改变后 `events_ledger_fingerprint` 与 `plan_hash` 改变。
- commit 传正确 `--expected-plan-hash` 时通过。
- commit 在 dry-run 后 candidate 文件被改动时 blocked。
- commit 在 dry-run 后 events ledger 变化时 blocked。
- mismatch 输出脱敏，不回显 candidate 原始 JSON 行。
- 不提供 `--expected-plan-hash` 时，现有 commit 行为保持不变。
- JSON 输出包含 freeze 字段但不泄露敏感内容。

## 验证结果

- `python -m pytest tests/test_runtime_event_import_freeze.py -q`：通过。
- `python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q`：通过。
- `python -m pytest -q`：通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。

## 已知限制与后续建议

- 第一版不冻结 tasks ledger；后续若需完整上下文冻结，可扩展 `tasks_ledger_fingerprint`。
- 第一版不实现 `--require-dry-run`；上层工作流如需强制绑定 dry-run，可通过总是传入 `--expected-plan-hash` 实现。
- 未实现 `--expected-events-ledger-fingerprint` / `--expected-events-ledger-size-bytes`；`plan_hash` 已打包这些信息。
