# 2026-07-07 Runtime Event Import Dry-run 实现接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **38 — Runtime Event Import Dry-run 实现**。

最新功能提交：

```text
b7a3f49 Add runtime event import dry-run
```

当前本地分支状态：

```text
HEAD = main = b7a3f49
origin/main = 1d85cec
```

说明：当前本地已完成 commit，尚待 push（若你看到本文件时已经 push，请以 `git status -sb` / `git log --oneline --decorate -5` 为准）。

最新 tag 仍为：

```text
v0.10.0-runtime-task-create-commit
```

本阶段实现范围：只实现 `runtime event import --dry-run`，不实现 `--commit`，不新增真实写权限，不修改真实 event/task ledger。

## 最近完成阶段

### Runtime Event Import Dry-run 预备设计

- 提交：`f169f29 Document event import dry-run design`
- 新增 `docs/37-runtime-event-import-dry-run.md`
- 定义 all-or-nothing preflight、输入顺序、重复检测、scan 与脱敏边界。

### Runtime Event Import Dry-run 实现

- 提交：`b7a3f49 Add runtime event import dry-run`
- 新增：
  - `agent_runtime/runtime_event_import.py`
  - `tests/test_runtime_event_import_dry_run.py`
  - `docs/38-release-notes-runtime-event-import-dry-run.md`
- 修改：
  - `agent_runtime/cli.py`
  - `README.md`
  - `README.en.md`
  - `docs/10-cli-poc-usage.md`
  - `tasks/progress.md`

## 本阶段新增能力

已支持：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --dry-run
```

可选参数：

```bash
--tasks-file tasks/tasks.jsonl
--events-file tasks/events.jsonl
--json
```

实现特性：

- 只支持 JSONL 输入，每行一个 event object。
- 空行忽略，但统计 `blank_line_count`。
- 批量语义为 **all-or-nothing preflight**。
- 输入顺序即模拟顺序；不自动按 timestamp 排序。
- 检测：
  - invalid JSON
  - 非 object 行
  - schema invalid
  - candidate 内部重复 `event_id`
  - 与现有 event ledger 重复 `event_id`
  - unknown task
  - 非法状态迁移 / ledger consistency failure
  - secret scan blocked
  - public scan blocked
- 通过临时文件模拟：
  - `existing events ledger + candidate events in input order`
  - 然后运行等价 `task validate --schema event` 与 `task check-ledger`
- 临时文件检查后删除，不修改真实 ledger。
- 输出脱敏：不回显 message、metadata values、artifact payload、evidence description、target/input、raw_ref/decision_ref、secret match。

## 审查中发现并已修复的问题

主控 Agent 在审查时发现：

- `duplicate-event-id` / `unknown-task-id` 的行号映射原先存在潜在错位风险：若前面有空行、invalid JSON、非 object、schema invalid 等被过滤行，后续 finding 行号可能不稳定。

已修复为：

- 每个保留下来的 candidate 显式携带 source line number。
- duplicate-existing-id / unknown-task / ledger-failure 等 finding 从稳定映射取原始行号。
- 已补两条针对性测试：
  - `test_import_event_dry_run_duplicate_existing_id_line_number_after_filtered_lines`
  - `test_import_event_dry_run_unknown_task_line_number_after_filtered_lines`

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
- 删除文件。
- 读取 `.env` / credential / token / keyring。
- 批量写 event ledger。
- 自动修复 ledger。
- 公开输出完整 secret match / target / input / evidence / raw_ref / decision_ref / message / metadata values。

当前允许的真实写入仅限：

- `runtime draft export --commit`：写新 draft 文件到 `drafts/runtime/.../*.json`。
- `runtime event append --commit`：向 event ledger JSONL 追加单行。
- `runtime task create --commit`：向 task ledger JSONL 追加单行。

`runtime event import` 当前 **仅 dry-run**，不允许真实写入。

## 验证命令

```bash
cd /d <repo-checkout-root>
python -m pytest tests/test_runtime_event_import_dry_run.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
focused tests -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
```

## 建议下一阶段

建议进入：

```text
39 — Runtime Event Import Commit 设计
```

建议先写设计，不直接实现 commit。下一阶段至少要定义：

- 是否允许创建新 event ledger 文件。
- 写入前 byte size 记录。
- 失败按 byte size truncate 回滚。
- 批量写入中途 IO 失败的恢复策略。
- post-check 顺序。
- 是否要求 dry-run plan hash。
- 是否允许 candidate 文件在 dry-run 与 commit 之间变化。
- 是否继续坚持 all-or-nothing commit 事务语义。

实现 `--commit` 前，必须先补新设计文档，不要直接从 dry-run 推导。 
