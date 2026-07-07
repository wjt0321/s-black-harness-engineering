# 2026-07-07 Runtime Event Import Consistency Freeze 实现接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **42 — Runtime Event Import Consistency Freeze 实现**。

最新功能提交：

```text
ce69947 Add runtime event import consistency freeze
```

当前本地分支状态：

```text
HEAD = main = ce69947
origin/main = cb7468b
```

说明：当前本地已完成 commit，尚待 push（若你看到本文件时已经 push，请以 `git status -sb` / `git log --oneline --decorate -5` 为准）。

最新 tag 仍为：

```text
v0.10.0-runtime-task-create-commit
```

## 最近完成阶段

### Runtime Event Import Commit 实现

- 提交：`9638f15 Add runtime event import commit`
- handoff：`cb7468b Add event import commit handoff`
- 能力：`runtime event import --commit` 已支持受控批量写入、post-check 与 rollback。

### Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`
- 目标：解决 dry-run / commit 之间 candidate 文件与目标 events ledger 的时间差风险。
- 核心设计：`candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count`、`plan_hash`，以及 commit 可选 `--expected-plan-hash`。

### Runtime Event Import Consistency Freeze 实现

- 提交：`ce69947 Add runtime event import consistency freeze`
- 新增：
  - `docs/41-runtime-event-import-consistency-freeze.md`
  - `docs/42-release-notes-runtime-event-import-consistency-freeze.md`
  - `tests/test_runtime_event_import_freeze.py`
- 修改：
  - `agent_runtime/runtime_event_import.py`
  - `agent_runtime/cli.py`
  - `docs/10-cli-poc-usage.md`
  - `README.md`
  - `README.en.md`
  - `tasks/progress.md`

## 本阶段新增能力

### dry-run 默认输出 freeze 信息

`runtime event import --dry-run` 现在会额外输出：

- `candidate_fingerprint`
- `events_ledger_fingerprint`
- `events_ledger_size_bytes`
- `events_ledger_line_count`
- `plan_hash`
- `freeze_mode=advisory`

### commit 可选绑定 dry-run plan

已支持：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --expected-plan-hash sha256:...
```

行为边界：

- 若未提供 `--expected-plan-hash`，现有 commit 行为保持不变。
- 若提供 `--expected-plan-hash`，commit 在 preflight 前先重算当前 plan hash。
- 若与传入 hash 不一致，则直接 `blocked`，不进入 preflight / append / post-check。
- freeze mismatch 只输出 hash / 相对路径 / size / line count 等安全摘要，不回显 candidate 原始 JSON 行与敏感字段。

## 核心实现点

### 1. Candidate fingerprint

基于：

- candidate 文件所有非空原始行
- 保持输入顺序
- 用 `\n` 拼接
- 做 `sha256`

语义：

- 输入顺序即导入顺序，因此 fingerprint 不做重排、不做 pretty-print。

### 2. Events ledger fingerprint

基于：

- 目标 events ledger 当前完整 UTF-8 字节
- 做 `sha256`

同时附带：

- `events_ledger_size_bytes`
- `events_ledger_line_count`

### 3. Plan hash

基于稳定 JSON object 计算，包含：

- `candidate_fingerprint`
- `events_ledger_fingerprint`
- `events_ledger_size_bytes`
- `events_ledger_line_count`
- `tasks_file` / `events_file` 相对路径
- `input_order_preserved=true`
- `all_or_nothing=true`

经过 canonical `json.dumps(..., sort_keys=True, separators=(",", ":"))` 后做 `sha256`。

### 4. Commit 顺序（加入 freeze 后）

当前顺序：

```text
resolve paths
  -> recompute freeze metadata
  -> compare expected_plan_hash (if provided)
  -> full preflight
  -> append block
  -> post-validate
  -> post-check-ledger
  -> rollback on failure
```

## 当前完整链路

```text
task ledger
  -> runtime task create --dry-run
  -> runtime task create --commit
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> runtime draft export --commit
  -> runtime event append --dry-run
  -> runtime event append --commit
  -> runtime event import --dry-run (+ freeze metadata)
  -> runtime event import --commit (+ optional expected plan hash)
  -> task validate / task check-ledger
  -> runtime check-ledger
  -> runtime report
  -> controlled write regression test
```

## 当前安全边界

仍禁止：

- 执行真实 adapter。
- 访问网络（除 git push 这类明确授权的仓库操作外）。
- 发送消息。
- 读取 `.env` / credential / token / keyring。
- 自动修复 ledger。
- 自动排序导入事件。
- 公开输出完整 secret match / target / input / evidence / raw_ref / decision_ref / message / metadata values。

当前允许的真实写入仅限：

- `runtime draft export --commit`
- `runtime event append --commit`
- `runtime task create --commit`
- `runtime event import --commit`

本阶段新增的一致性冻结只影响 dry-run / commit 的摘要与前置校验，不新增新的写权限。

## 验证命令

```bash
cd /d <repo-checkout-root>
python -m pytest tests/test_runtime_event_import_freeze.py -q
python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
focused freeze tests -> passed
focused import tests -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
```

## 当前已知限制

- 第一版只实现 `--expected-plan-hash`，未实现单独的 `--expected-events-ledger-fingerprint` 参数。
- 第一版不强制全局 always-on freeze；不提供 `--expected-plan-hash` 时 commit 行为保持原样。
- 第一版未强制冻结 tasks ledger。
- 第一版未实现 `--require-dry-run`。

## 建议下一阶段

建议进入：

```text
43 — Controlled Write Regression 扩展
```

优先把以下内容纳入统一回归：

- `runtime event import --commit` 成功路径
- `runtime event import --commit --expected-plan-hash` 一致性冻结路径
- rollback 后 ledger 未污染
- runtime report / ledger check 在引入批量 import 后保持输出脱敏

另一条路线也可选：

```text
43 — Runtime Event Import Freeze Strict Mode 设计
```

继续讨论：

- 是否引入 `--require-dry-run`
- 是否强制 tasks ledger freeze
- 是否默认总是要求 expected plan hash
