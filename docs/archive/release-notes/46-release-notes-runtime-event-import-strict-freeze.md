# 46 — Release Notes: Runtime Event Import Strict Freeze Mode

## 阶段定位

本文档标记 `runtime event import` strict freeze mode 第一版实现完成。它在 `docs/45-runtime-event-import-strict-freeze-mode.md` 确定的设计基础上，新增了 `--require-dry-run` 参数，使调用方可以显式声明：本次 commit 必须绑定某次 dry-run 审阅结果。

## 已实现能力

- `runtime event import --commit` 新增可选参数 `--require-dry-run`。
- `--require-dry-run` 只能与 `--commit` 一起使用；与 `--dry-run` 同传或单独使用都会返回 `error`。
- 使用 `--require-dry-run` 时必须同时提供 `--expected-plan-hash`，否则返回 `error`（`rule_id=missing-expected-plan-hash`）。
- 提供 `--require-dry-run --expected-plan-hash <hash>` 时：
  - commit 先重算当前 plan hash。
  - hash 一致则继续走完整 preflight + append block + post-check + rollback。
  - hash 不一致直接 `blocked`（`rule_id=plan-hash-mismatch`），不进入 preflight / 写入阶段。
- 不提供 `--require-dry-run` 时，现有 commit 行为保持不变（仍可单独使用 `--expected-plan-hash`）。
- 第一版不强制 tasks ledger fingerprint，不新增单独 events ledger fingerprint 参数，不允许创建新 event ledger。
- 输出继续脱敏：不回显 candidate 原始 JSON 行、message、metadata values、artifacts payload、evidence description、target/input、raw_ref/decision_ref 或 secret match。

## 核心实现点

- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--require-dry-run` 参数。
  - 在 `_cmd_runtime_event_import` 中校验：
    - `--require-dry-run` 不能与 `--dry-run` 同时使用。
    - `--require-dry-run` 只能与 `--commit` 同时使用。
  - 将 `require_dry_run` 传给 `import_events_commit`。
- 修改 `agent_runtime/runtime_event_import.py`：
  - `import_events_commit` 新增 `require_dry_run: bool = False` 参数。
  - 函数开头检查 `require_dry_run and expected_plan_hash is None`，返回 `error`（`rule_id=missing-expected-plan-hash`）。
  - 后续 freeze check 逻辑复用现有 `--expected-plan-hash` 路径；`require_dry_run=True` 时 `freeze_check` 字段标记为 `pass` 或 `failed`。

## CLI 用法示例

Dry-run 生成 plan hash：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run \
  --json
```

Commit 强制绑定该 dry-run 审阅结果：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --require-dry-run \
  --expected-plan-hash sha256:... \
  --tasks-file tasks/tasks.jsonl \
  --events-file tasks/events.jsonl
```

缺少 `--expected-plan-hash` 时的人类输出示例：

```text
ERROR
- missing-expected-plan-hash: --require-dry-run requires --expected-plan-hash.
Next: Rerun runtime event import --dry-run, review the plan_hash, then pass --expected-plan-hash.
```

hash mismatch 时的人类输出示例：

```text
BLOCKED
freeze_check=failed
expected_plan_hash=sha256:...
current_plan_hash=sha256:...
- plan-hash-mismatch: current candidate or ledger context no longer matches the reviewed dry-run plan.
Next: Rerun runtime event import --dry-run and review the updated batch before commit.
```

## 安全边界

- 不执行 adapter、不访问网络、不发送消息。
- 不读取 `.env` / credential / token / keyring。
- 不删除文件；strict freeze mode 仍沿用 v0.11 边界，只允许向已存在的 event ledger 追加连续 JSONL block。
- 失败时按写入前 byte size 回滚，不允许部分成功。
- 不回显敏感内容；freeze 字段只暴露 hash、相对路径、size、line count 等安全元数据。

## 测试覆盖

新增 `tests/test_runtime_event_import_strict_freeze.py`，覆盖：

- `--require-dry-run` 缺少 `--expected-plan-hash` 返回 `error`。
- `--require-dry-run` 与 `--dry-run` 同传时报错。
- `--require-dry-run` 只能与 `--commit` 一起使用。
- `--require-dry-run --expected-plan-hash <correct>` 成功 commit。
- `--require-dry-run --expected-plan-hash <stale>` 被 blocked，且 events ledger 字节不变。
- stale hash 输出脱敏，不回显 candidate 原始 JSON 行或 message。
- 不传 `--require-dry-run` 但传 `--expected-plan-hash` 的现有行为保持不变。
- 不传任何 freeze 参数的现有 commit 行为保持不变。

更新 `tests/test_controlled_write_regression.py`：

- 新增 `test_controlled_write_regression_event_import_strict_freeze`。
- 在临时项目根中跑通：task create commit -> event append commit -> event import dry-run -> event import commit `--require-dry-run --expected-plan-hash <correct>` -> 候选文件被改动后 `--require-dry-run --expected-plan-hash <stale>` blocked -> post-commit validate/check-ledger -> runtime report。
- 断言 task ledger 不被 event import commit 修改，真实仓库 ledger 不被修改。

## 验证结果

- `python -m pytest tests/test_runtime_event_import_strict_freeze.py -q`：通过。
- `python -m pytest tests/test_controlled_write_regression.py -q`：通过。
- `python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py tests/test_runtime_event_import_strict_freeze.py -q`：通过。
- `python -m pytest -q`：通过。
- `python -m agent_runtime.cli doctor`：PASS。
- `python tools/public_scan.py`：OK public scan。

## 已知限制与后续建议

- 第一版 strict freeze mode 不冻结 tasks ledger；后续若需完整上下文冻结，可扩展 `tasks_ledger_fingerprint` 并提升 `schema_version`。
- 未实现 `--expected-events-ledger-fingerprint` 等细粒度参数；`plan_hash` 已打包 candidate fingerprint、events ledger fingerprint、size、line count、路径与事务语义。
- 本次实现不改变 advisory freeze 的默认行为，仅增加显式 strict 约束选项。
