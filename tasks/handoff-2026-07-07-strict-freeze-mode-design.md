# 2026-07-07 Runtime Event Import Strict Freeze Mode 设计接续上下文

> 本文件供新会话恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **45 — Runtime Event Import Strict Freeze Mode 设计**。

本阶段只写设计与文档维护，不实现 CLI，不新增真实写权限，不修改 Runtime 行为。

最新 tag：

```text
v0.11.0-runtime-event-import
```

## 最近完成阶段

### 43 — Controlled Write Regression 扩展：Event Import

- 功能提交：`f2c8be0 Extend controlled write regression for event import`
- handoff 提交：`32cc27d Add controlled write regression event import handoff`
- 新增 `docs/43-controlled-write-regression-event-import.md`
- 把 `runtime event import --commit` 与 `--expected-plan-hash` 纳入受控写入回归。

### 44 — v0.11 Runtime Event Import Release

- release notes 提交：`b54d3ad Add v0.11 runtime event import release notes`
- handoff 提交：`a58d30b Add v0.11 runtime event import handoff`
- tag：`v0.11.0-runtime-event-import`
- v0.11 汇总 event import dry-run、commit、consistency freeze 与 controlled write regression 扩展。

### 45 — Runtime Event Import Strict Freeze Mode 设计

- 新增 `docs/45-runtime-event-import-strict-freeze-mode.md`
- 更新：
  - `README.md`
  - `README.en.md`
  - `tasks/progress.md`

## 45 设计核心

未来 strict freeze mode 建议新增：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --require-dry-run \
  --expected-plan-hash sha256:...
```

设计结论：

- `--require-dry-run` 表示本次 commit 必须绑定某次 dry-run 审阅结果。
- `--require-dry-run` 只能与 `--commit` 组合。
- `--require-dry-run` 不能与 `--dry-run` 组合。
- `--require-dry-run` 必须同时提供 `--expected-plan-hash`。
- 缺少 expected hash 属于命令使用错误，建议返回 `error`，rule_id=`missing-expected-plan-hash`。
- hash mismatch 继续沿用现有 `plan-hash-mismatch` blocked 语义。
- 第一版 strict mode 不强制 tasks ledger fingerprint。
- 第一版不新增单独 events ledger fingerprint 参数。
- 第一版不允许创建新 event ledger。
- 未来实现 strict mode 后，controlled write regression 必须覆盖成功、缺 hash、stale hash 与兼容路径。

## 验证命令

本阶段主控已实跑：

```bash
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

预期：

```text
pytest -> passed
doctor -> PASS
public_scan -> OK public scan
git diff --check -> PASS
```

## 当前安全边界

仍禁止：

- 执行真实 adapter。
- 访问网络（除 git push / tag push 这类明确授权的仓库操作外）。
- 发送消息。
- 读取 `.env` / credential / token / keyring。
- 自动修复 ledger。
- 自动排序导入事件。
- 公开输出完整 secret match / target / input / evidence / raw_ref / decision_ref / message / metadata values。

45 本身不新增任何真实写入能力。

## 建议下一阶段

如果后续继续，可进入：

```text
46 — Runtime Event Import Strict Freeze Mode 实现
```

实现建议：

- 代码交给 Kimi Code。
- 小黑负责需求边界、审查、验证、文档、提交与收口。
- 必须补 `tests/test_runtime_event_import_strict_freeze.py` 与 controlled write regression strict mode 覆盖。
