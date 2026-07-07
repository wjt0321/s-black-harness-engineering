# 2026-07-07 Controlled Write Regression Event Import 接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **43 — Controlled Write Regression 扩展：Event Import**。

最新功能提交：

```text
f2c8be0 Extend controlled write regression for event import
```

当前本地分支状态：

```text
HEAD = main = f2c8be0
origin/main = 883e165
```

说明：当前本地已完成 43 的功能提交，尚待本阶段 handoff 提交与后续 push（若你看到本文件时已经 push，请以 `git status -sb` / `git log --oneline --decorate -5` 为准）。

最新 tag 仍为：

```text
v0.10.0-runtime-task-create-commit
```

## 最近完成阶段

### Runtime Event Import Consistency Freeze 实现

- 提交：`ce69947 Add runtime event import consistency freeze`
- handoff：`883e165 Add event import consistency freeze handoff`
- 能力：`runtime event import --dry-run` 默认输出 freeze metadata；`runtime event import --commit` 可选 `--expected-plan-hash`。

### Controlled Write Regression Event Import 扩展

- 提交：`f2c8be0 Extend controlled write regression for event import`
- 新增：
  - `docs/43-controlled-write-regression-event-import.md`
- 修改：
  - `tests/test_controlled_write_regression.py`
  - `docs/36-controlled-write-regression.md`
  - `README.md`
  - `README.en.md`
  - `tasks/progress.md`

## 本阶段新增保护

`runtime event import --commit` 已纳入 controlled write regression：

- 在 `tmp_path` 临时项目根中运行，不修改真实仓库 ledger。
- 覆盖 `runtime event import --dry-run` 输出 `plan_hash`。
- 覆盖 `runtime event import --commit --expected-plan-hash <hash>` 成功追加连续 batch。
- 覆盖 stale `plan_hash` 时 commit 被 blocked，events ledger 字节不变。
- 覆盖 task ledger 不被 event import commit 修改。
- 覆盖 `task validate` / `task check-ledger` 在批量 import 后仍通过。
- 覆盖 `runtime report` 输出脱敏，不泄露 task title / event message。
- 断言真实仓库 `tasks/tasks.jsonl` 与 `tasks/events.jsonl` 字节不变。

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
  -> controlled write regression event import coverage
  -> task validate / task check-ledger
  -> runtime check-ledger
  -> runtime report
```

## 验证命令

本阶段已由主控实跑：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

预期：

```text
controlled write regression -> passed
focused event import tests -> passed
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
git diff --check -> PASS
```

## 安全边界

本阶段不新增功能能力，不新增真实写权限，只补回归测试与文档。

仍禁止：

- 执行真实 adapter。
- 访问网络（除 git push 这类明确授权的仓库操作外）。
- 发送消息。
- 读取 `.env` / credential / token / keyring。
- 自动修复 ledger。
- 公开输出完整 secret match / target / input / evidence / raw_ref / decision_ref / message / metadata values。

## 建议下一阶段

建议进入：

```text
44 — v0.11 Release Notes + Tag
```

建议内容：

- 汇总 event import dry-run / commit / consistency freeze / controlled write regression 扩展。
- 新增 `docs/44-release-notes-v0.11-runtime-event-import.md`。
- 更新 README / README.en 当前 tag 或 release docs 索引。
- 跑 full verification。
- 提交 release notes。
- 打 tag：`v0.11.0-runtime-event-import`。
- push commit + tag。
