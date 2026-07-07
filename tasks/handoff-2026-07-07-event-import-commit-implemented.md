# 2026-07-07 Runtime Event Import Commit 实现接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **40 — Runtime Event Import Commit 实现**。

最新功能提交：

```text
9638f15 Add runtime event import commit
```

当前本地分支状态：

```text
HEAD = main = 9638f15
origin/main = 7d17d0b
```

说明：当前本地已完成 commit，尚待 push（若你看到本文件时已经 push，请以 `git status -sb` / `git log --oneline --decorate -5` 为准）。

最新 tag 仍为：

```text
v0.10.0-runtime-task-create-commit
```

## 最近完成阶段

### Runtime Event Import Dry-run 实现

- 提交：`b7a3f49 Add runtime event import dry-run`
- handoff：`7d17d0b Add event import dry-run handoff`
- 能力：`runtime event import --dry-run` 已可做批量 event 只读预检。

### Runtime Event Import Commit 设计

- 本地设计阶段新增：`docs/39-runtime-event-import-commit-design.md`
- 核心设计：all-or-nothing、commit 内部重跑 preflight、第一版不允许目标 events ledger 不存在、写后 validate/check-ledger、失败按 byte size truncate 回滚。

### Runtime Event Import Commit 实现

- 提交：`9638f15 Add runtime event import commit`
- 新增：
  - `docs/39-runtime-event-import-commit-design.md`
  - `docs/40-release-notes-runtime-event-import-commit.md`
  - `tests/test_runtime_event_import_commit.py`
- 修改：
  - `agent_runtime/runtime_event_import.py`
  - `agent_runtime/cli.py`
  - `docs/10-cli-poc-usage.md`
  - `README.md`
  - `README.en.md`
  - `tasks/progress.md`
  - `tests/test_runtime_event_import_dry_run.py`

## 本阶段新增能力

已支持：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit
```

仍支持：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

行为边界：

- `--dry-run` 与 `--commit` 互斥。
- 两者都不传时报错。
- commit 内部必须重跑完整 preflight，不信任之前 dry-run 结果。
- 只支持 `--file` JSONL 输入；不支持 JSON array。
- 第一版要求目标 `events_file` 必须已存在。
- 非空 events ledger 末尾必须已有换行符，否则 blocked。
- 只允许向现有 ledger 尾部追加连续 JSONL block。
- 写后必须跑等价：
  - `task validate --schema event`
  - `task check-ledger`
- 任一失败按写前 `original_size_bytes` 做 truncate 回滚。
- 不允许部分成功。
- 不自动排序。
- 不写 task ledger。
- 不写 envelope。
- 输出继续脱敏，不回显 message、metadata values、artifacts payload、evidence description、target/input、raw_ref/decision_ref、secret match。

## 关键实现点

### 1. Dry-run / Commit 共用 preflight

`agent_runtime/runtime_event_import.py` 已抽出公共 `_run_preflight`：

- dry-run 与 commit 复用同一批 candidate 读取、schema/scan/duplicate/unknown-task/ledger-consistency 逻辑。
- commit 通过额外参数要求 `events_file` 必须已存在。

### 2. Commit 顺序固定

当前实现顺序：

```text
preflight
  -> target guard
  -> trailing newline check
  -> append block
  -> post-validate
  -> post-check-ledger
  -> rollback on failure
```

### 3. Rollback 语义

- 写前记录 `original_size_bytes`。
- append 或 post-check 任一失败：`truncate(original_size_bytes)`。
- 第一版不允许创建新 ledger，因此无需删除文件回滚。
- 若 rollback 本身失败，结果中会带 `rollback_error`。

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
  -> runtime event import --dry-run
  -> runtime event import --commit
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

- `runtime draft export --commit`：写新 draft 文件到 `drafts/runtime/.../*.json`。
- `runtime event append --commit`：向 event ledger JSONL 追加单行。
- `runtime task create --commit`：向 task ledger JSONL 追加单行。
- `runtime event import --commit`：向**已存在** event ledger JSONL 尾部追加一整批连续 block；失败时按 byte size 回滚。

## 验证命令

```bash
cd /d <repo-checkout-root>
python -m pytest tests/test_runtime_event_import_commit.py -q
python -m pytest tests/test_runtime_event_import_dry_run.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
focused commit tests -> passed
focused dry-run tests -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
```

## 当前已知限制

- 第一版未实现 `--expected-plan-hash`。
- 第一版未实现 ledger fingerprint 冻结。
- 第一版不允许目标 events ledger 不存在。
- 第一版不支持 JSON array 输入。
- 第一版不支持部分成功。

## 建议下一阶段

建议进入：

```text
41 — Runtime Event Import Consistency Freeze 设计
```

优先解决：

- dry-run / commit 之间 candidate 文件被改动的检测。
- dry-run / commit 之间目标 ledger 发生变化的检测。
- `plan_hash` / `events_ledger_fingerprint` / `events_ledger_size_bytes` 的最小实现方案。
- 是否需要 `--require-dry-run` 或 `--expected-plan-hash`。

如果暂不做一致性冻结，也可以转去补：

```text
41 — Controlled Write Regression 扩展
```

把 `runtime event import --commit` 纳入受控写入回归测试总链路。 
