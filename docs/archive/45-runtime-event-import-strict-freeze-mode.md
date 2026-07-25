# 45 — Runtime Event Import Strict Freeze Mode 设计

## 阶段定位

本文定义 `runtime event import` strict freeze mode 的后续设计边界。它建立在 v0.11 已完成的 Runtime Event Import 能力包之上：

- `runtime event import --dry-run`
- `runtime event import --commit`
- consistency freeze advisory mode（dry-run 输出 `plan_hash`，commit 可选 `--expected-plan-hash`）
- controlled write regression event import coverage

本阶段只写设计，不实现 CLI，不新增真实写权限，不修改 Runtime 行为。

## 当前状态

v0.11 已经提供最小可用的一致性冻结：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

会输出：

- `candidate_fingerprint`
- `events_ledger_fingerprint`
- `events_ledger_size_bytes`
- `events_ledger_line_count`
- `plan_hash`
- `freeze_mode=advisory`

commit 可选绑定该计划：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --expected-plan-hash sha256:...
```

如果 `--expected-plan-hash` mismatch，则直接 `blocked`，不进入 preflight / append / post-check。

## 要解决的问题

当前 freeze 是 advisory-first：

- dry-run 总是输出 freeze metadata。
- commit 不强制要求 `--expected-plan-hash`。
- 只有调用方显式提供 `--expected-plan-hash`，才进入 strict compare。

这保留了向后兼容性，但也意味着：

- 调用方仍可直接 `--commit`。
- 人类 review 与 commit 的强绑定依赖调用方自觉传 hash。
- 上层 workflow 难以表达“这次批量写入必须经过 dry-run 审阅”。

Strict freeze mode 要解决的是：

> 如何让调用方显式声明：本次 commit 必须绑定某次 dry-run 审阅结果，否则不允许写入。

## 设计目标

未来 strict freeze mode 应支持：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --require-dry-run \
  --expected-plan-hash sha256:...
```

语义：

- `--require-dry-run` 表示本次 commit 必须绑定 dry-run 计划。
- 如果提供 `--require-dry-run` 但缺少 `--expected-plan-hash`，直接 `error` 或 `blocked`。
- 如果提供 `--expected-plan-hash` 且 mismatch，直接 `blocked`。
- 如果 hash 一致，仍继续完整 preflight + append + post-check + rollback。

## 非目标

本阶段不应做：

- 不实现 `--require-dry-run`。
- 不改变现有 `--commit` 默认行为。
- 不强制所有 commit 必须提供 `--expected-plan-hash`。
- 不新增真实写入点。
- 不允许部分成功。
- 不自动排序 event。
- 不支持 JSON array 输入。
- 不执行 adapter。
- 不访问网络。
- 不发送消息。
- 不读取 `.env` / credential / token / keyring。

## CLI 参数设计

### `--expected-plan-hash`

已实现。

语义：

- 可单独使用。
- 若提供，则 commit 在 preflight 前重算 plan hash。
- mismatch 返回 `blocked`。

### `--require-dry-run`

建议新增。

语义：

- 只能与 `--commit` 一起使用。
- 不能与 `--dry-run` 一起使用。
- 要求同时提供 `--expected-plan-hash`。
- 缺少 `--expected-plan-hash` 时应返回 `error`，规则 id 建议为 `missing-expected-plan-hash`。

原因：

- 这是调用方的 workflow 约束，不是 ledger validation 问题。
- 缺参数属于命令使用错误，宜返回 `error`。

### 是否需要 `--freeze-mode strict`

暂不建议。

理由：

- `--require-dry-run` 更直观。
- `--freeze-mode strict` 需要定义和 advisory 的组合关系，增加 CLI 复杂度。
- 当前只有一个 strict 行为：必须绑定 plan hash。

## 状态与错误语义

### 缺少 expected hash

命令：

```bash
runtime event import --file candidate-events.jsonl --commit --require-dry-run
```

建议输出：

```text
ERROR
- missing-expected-plan-hash: --require-dry-run requires --expected-plan-hash.
Next: Rerun runtime event import --dry-run, review the plan_hash, then pass --expected-plan-hash.
```

### Hash mismatch

命令：

```bash
runtime event import --file candidate-events.jsonl --commit --require-dry-run --expected-plan-hash sha256:old
```

建议输出：

```text
BLOCKED
freeze_check=failed
- plan-hash-mismatch: current candidate or ledger context no longer matches the reviewed dry-run plan.
Next: Rerun runtime event import --dry-run and review the updated batch before commit.
```

### Hash match

继续执行：

```text
freeze_check=pass
preflight
append block
post-check
rollback on failure
```

## Tasks Ledger Fingerprint

### 是否纳入 strict mode

建议：第一版 strict mode 仍不强制 tasks ledger fingerprint。

理由：

- v0.11 plan hash 已包含 candidate 与 events ledger，这已经覆盖 event import 最关键的审阅上下文。
- commit 内部仍会重跑 preflight，task ledger 变化会在 unknown task / status consistency / ledger check 中被重新验证。
- 强制 tasks ledger freeze 会把 task snapshot 更新流程与 event import commit 过早耦合。

### 后续扩展

如果未来要冻结 tasks ledger，建议新增：

- `tasks_ledger_fingerprint`
- `tasks_ledger_size_bytes`
- `tasks_ledger_line_count`

并把这些字段纳入 `plan_hash` schema version 2。

注意：一旦 plan hash 输入结构改变，必须提升：

```text
schema_version: 2
```

避免 v1/v2 hash 语义混淆。

## 单独 events ledger fingerprint 参数

### 是否需要

可选，但不建议第一版 strict mode 同时加入。

已有 `plan_hash` 已打包：

- candidate fingerprint
- events ledger fingerprint
- events ledger size
- events ledger line count
- tasks/events relative paths
- all-or-nothing / input-order semantics

新增单独参数会带来组合问题：

- 如果 `--expected-plan-hash` 与 `--expected-events-ledger-fingerprint` 不一致，以谁为准？
- 是否允许只传 ledger fingerprint 不传 plan hash？

### 建议

第一版 strict mode 只接受：

```bash
--require-dry-run --expected-plan-hash <hash>
```

后续如果上层系统确实需要更细粒度调试，再考虑增加：

```bash
--expected-events-ledger-fingerprint <hash>
```

但它应只作为 diagnostic 辅助，不替代 `plan_hash`。

## 是否允许创建新 event ledger

严格冻结模式不应同时引入新 ledger 创建。

理由：

- v0.11 commit 明确第一版不允许目标 events ledger 不存在。
- 允许创建新 ledger 会引入失败时删除新文件的回滚语义。
- strict freeze 本身已是 workflow 约束增强，不应同时扩大写入面。

建议：

- strict freeze mode 仍沿用 v0.11 边界：events ledger 必须已存在。

## 输出脱敏

Strict freeze mode 输出不得回显：

- candidate 原始 JSON 行全文
- event `message`
- metadata values
- artifacts payload
- evidence description
- `target`
- `input`
- `raw_ref`
- `decision_ref`
- secret match

允许输出：

- `plan_hash`
- `expected_plan_hash`
- `current_plan_hash`
- `freeze_check`
- project-local relative file path
- byte size
- line count

## 与 controlled write regression 的关系

未来实现 strict mode 后，必须扩展 controlled write regression：

- `--require-dry-run` 缺少 `--expected-plan-hash` 返回 error，且 ledger 不变。
- `--require-dry-run --expected-plan-hash <correct>` 成功 commit。
- `--require-dry-run --expected-plan-hash <stale>` blocked，且 ledger 不变。
- 不带 `--require-dry-run` 的现有 commit 行为保持兼容。

## 建议测试清单（未来实现阶段）

必须覆盖：

- `--require-dry-run` 只能与 `--commit` 一起使用。
- `--require-dry-run` 与 `--dry-run` 同传时报错。
- `--require-dry-run` 缺少 `--expected-plan-hash` 返回 `error`。
- `--require-dry-run --expected-plan-hash <correct>` 成功 commit。
- `--require-dry-run --expected-plan-hash <stale>` blocked。
- stale hash blocked 时 events ledger 字节不变。
- stale hash 输出脱敏。
- 不传 `--require-dry-run` 但传 `--expected-plan-hash` 的现有行为保持不变。
- 不传任何 freeze 参数的现有 commit 行为保持不变。
- controlled write regression 覆盖 strict mode 成功与失败路径。

## 建议实现文件（未来）

```text
agent_runtime/runtime_event_import.py
agent_runtime/cli.py
tests/test_runtime_event_import_strict_freeze.py
tests/test_controlled_write_regression.py
docs/46-release-notes-runtime-event-import-strict-freeze.md
```

## 第一版实现建议结论

若进入下一实现阶段，建议最小实现：

- 新增 `--require-dry-run` 参数。
- 只允许 `--require-dry-run` 与 `--commit` 组合。
- `--require-dry-run` 必须要求 `--expected-plan-hash`。
- 缺少 expected hash 返回 `error`。
- hash mismatch 继续沿用现有 `plan-hash-mismatch` blocked。
- 不强制 tasks ledger freeze。
- 不新增单独 events ledger fingerprint 参数。
- 不允许创建新 event ledger。
- 更新 controlled write regression 覆盖 strict mode。
