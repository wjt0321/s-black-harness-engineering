# 2026-07-07 Runtime Event Import Dry-run 预备设计接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **Runtime Event Import Dry-run 预备设计** 阶段。

最新提交：

```text
f169f29 Document event import dry-run design
```

当前远端状态：

```text
main...origin/main
HEAD = origin/main = f169f29
```

最新 tag 仍为：

```text
v0.10.0-runtime-task-create-commit
```

本阶段只写设计，不实现 CLI，不新增写权限，不修改 Runtime 行为。

## 最近完成阶段

### v0.10 Runtime Task Create Commit

- 功能提交：`2dfb8d3 Add runtime task create commit`
- handoff 提交：`a1f8926 Add task create commit handoff`
- tag：`v0.10.0-runtime-task-create-commit`
- 能力：`runtime task create --commit` 只向 task ledger JSONL 末尾追加 exactly one JSON object；写后 validate/check-ledger；失败按 byte size 回滚；不自动写 event ledger。

### Runtime Task Create Smoke / Report Loop

- 提交：`0a35ea6 Add task create smoke report loop`
- 不打 tag。
- 新增端到端 smoke：task create dry-run -> commit -> event append dry-run -> commit -> task validate/check-ledger -> runtime report。
- 修复 `runtime report` 输出完整 task title 的脱敏问题，改为 `title_present=True/False`。

### Controlled Write Regression Guard

- 提交：`4fc75e8 Add controlled write regression guard`
- 不打 tag。
- 新增 `docs/36-controlled-write-regression.md`。
- 新增 `tests/test_controlled_write_regression.py`。
- CI 显式运行：`python -m pytest tests/test_controlled_write_regression.py -q`。

### Runtime Event Import Dry-run 预备设计

- 提交：`f169f29 Document event import dry-run design`
- 不打 tag。
- 新增 `docs/37-runtime-event-import-dry-run.md`。
- 更新 README / README.en / `docs/10-cli-poc-usage.md` / `tasks/progress.md`。

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
  -> task validate / task check-ledger
  -> runtime check-ledger
  -> runtime report
  -> controlled write regression test
```

## 关键设计：docs/37

`docs/37-runtime-event-import-dry-run.md` 定义未来 `runtime event import --dry-run`：

- 第一版只做 dry-run，不写 event ledger。
- 输入建议为 JSONL，每行一个 event object。
- 批量语义采用 all-or-nothing preflight，不允许部分成功。
- 输入顺序即模拟导入顺序，不自动按 timestamp 排序。
- 必须检测：
  - candidate events 内部重复 `event_id`
  - candidate 与现有 event ledger 重复 `event_id`
  - 引用不存在 task
  - 同一 task 状态迁移按输入顺序是否合法
  - schema invalid / invalid JSON / 非 object 行
  - secret/public scan blocked
- 输出只给安全摘要，不回显 message、metadata values、artifact payload、evidence description、target/input、raw_ref/decision_ref、secret match。
- 未来 commit 阶段必须另写设计，不从 dry-run 直接推导。

## 当前安全边界

仍禁止：

- 执行真实 adapter。
- 访问网络。
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

## 编程分工要求

当前项目分工：编程方面的实际代码编写默认调用 Kimi Code 完成；主控 Agent 负责需求边界、任务拆解、代码审查、验证、文档编写、提交/发布前检查与总结收口。

下一阶段如实现 `runtime event import --dry-run`，应先给 Kimi Code 清晰需求，然后由主控 Agent 审查关键代码和测试，不亲自承担主要代码编写。

## 恢复命令

```bash
cd /d <repo-checkout-root>
git status -sb
git log --oneline --decorate -8
git tag --points-at HEAD
python -m pytest tests/test_controlled_write_regression.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
main...origin/main
HEAD: f169f29 Document event import dry-run design
latest tag remains v0.10.0-runtime-task-create-commit
controlled write regression -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
```

## 建议下一阶段

建议进入：

```text
38 — Runtime Event Import Dry-run 实现
```

实现边界：

- 只实现 `--dry-run`。
- 不实现 `--commit`；显式传入 commit 应返回 not implemented 或先不暴露参数。
- 不写真实 event ledger。
- 不写 task ledger。
- 不写 envelope。
- 不新增真实写权限。
- 不进入 adapter execution。
- 复用 `docs/37` 中定义的 all-or-nothing / input order / duplicate detection / scan / temp ledger consistency / output redaction 规则。

建议实现文件：

```text
agent_runtime/runtime_event_import.py
agent_runtime/cli.py
tests/test_runtime_event_import_dry_run.py
docs/38-release-notes-runtime-event-import-dry-run.md
```

实现后不要立刻 push；先由主控 Agent 审查代码、focused tests、全量 pytest、doctor、public_scan、diff check、key scan。
