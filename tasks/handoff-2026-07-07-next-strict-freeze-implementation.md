# 2026-07-07 下一阶段接续上下文 — Strict Freeze Mode 实现

> 本文件供下次新窗口恢复 `D:\agent-runtime` / `s-black harness engineering` 使用。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前仓库状态

当前已完成今日收尾任务：

```text
45 — Runtime Event Import Strict Freeze Mode 设计
```

当前本地 / 远端状态在写入本 handoff 前为：

```text
main = origin/main = 89aaaea
HEAD = 89aaaea Document runtime event import strict freeze mode
最新 tag = v0.11.0-runtime-event-import（位于 a58d30b）
工作树干净
```

最新重要提交：

```text
89aaaea Document runtime event import strict freeze mode
a58d30b Add v0.11 runtime event import handoff
b54d3ad Add v0.11 runtime event import release notes
32cc27d Add controlled write regression event import handoff
f2c8be0 Extend controlled write regression for event import
```

## 今日已完成能力包

### 43 — Controlled Write Regression 扩展：Event Import

- 提交：`f2c8be0 Extend controlled write regression for event import`
- handoff：`32cc27d Add controlled write regression event import handoff`
- 已把 `runtime event import --commit` 与 `--expected-plan-hash` 纳入受控写入回归。
- 聚焦文件：
  - `tests/test_controlled_write_regression.py`
  - `docs/36-controlled-write-regression.md`
  - `docs/43-controlled-write-regression-event-import.md`

### 44 — v0.11 Runtime Event Import Release

- release notes：`b54d3ad Add v0.11 runtime event import release notes`
- handoff：`a58d30b Add v0.11 runtime event import handoff`
- tag：`v0.11.0-runtime-event-import`
- 汇总能力：
  - `runtime event import --dry-run`
  - `runtime event import --commit`
  - consistency freeze advisory mode
  - controlled write regression event import coverage

### 45 — Runtime Event Import Strict Freeze Mode 设计

- 提交：`89aaaea Document runtime event import strict freeze mode`
- 新增：
  - `docs/45-runtime-event-import-strict-freeze-mode.md`
  - `tasks/handoff-2026-07-07-strict-freeze-mode-design.md`
- 更新：
  - `README.md`
  - `README.en.md`
  - `tasks/progress.md`

## 45 设计结论

未来 strict freeze mode 建议新增：

```bash
python -m agent_runtime.cli runtime event import \
  --file candidate-events.jsonl \
  --commit \
  --require-dry-run \
  --expected-plan-hash sha256:...
```

关键边界：

- `--require-dry-run` 表示本次 commit 必须绑定某次 dry-run 审阅结果。
- `--require-dry-run` 只能与 `--commit` 组合。
- `--require-dry-run` 不能与 `--dry-run` 组合。
- `--require-dry-run` 必须同时提供 `--expected-plan-hash`。
- 缺少 expected hash 属于命令使用错误，建议返回 `error`，rule_id=`missing-expected-plan-hash`。
- hash mismatch 继续沿用现有 `plan-hash-mismatch` blocked 语义。
- 第一版 strict mode 不强制 tasks ledger fingerprint。
- 第一版不新增单独 events ledger fingerprint 参数。
- 第一版不允许创建新 event ledger。
- 实现 strict mode 后必须扩展 controlled write regression。

## 下一阶段建议

建议进入：

```text
46 — Runtime Event Import Strict Freeze Mode 实现
```

### 分工

- 编码继续交给 Kimi Code。
- 主控负责：需求边界、审查、验证、文档、提交、push 与最终收口。
- 用户明确偏好：连续推进，不要每一步都断点询问；只有需要授权、边界不明、风险升高或路线分叉时再打断。

### 建议给 Kimi 的实现任务

请让 Kimi 严格按 `docs/45-runtime-event-import-strict-freeze-mode.md` 实现：

- 在 `runtime event import` 上新增 `--require-dry-run` 参数。
- `--require-dry-run` 只能用于 `--commit`。
- `--require-dry-run` 与 `--dry-run` 同传时报错。
- `--require-dry-run` 缺少 `--expected-plan-hash` 返回 `error`，rule_id 建议为 `missing-expected-plan-hash`。
- `--require-dry-run --expected-plan-hash <correct>` 成功 commit。
- `--require-dry-run --expected-plan-hash <stale>` blocked，ledger 字节不变。
- 不传 `--require-dry-run` 但传 `--expected-plan-hash` 的现有行为保持不变。
- 不传任何 freeze 参数的现有 commit 行为保持不变。
- 不新增 tasks ledger fingerprint。
- 不新增单独 events ledger fingerprint 参数。
- 不允许创建新 event ledger。
- 输出继续脱敏。

### 建议改动文件

```text
agent_runtime/runtime_event_import.py
agent_runtime/cli.py
tests/test_runtime_event_import_strict_freeze.py
tests/test_controlled_write_regression.py
docs/46-release-notes-runtime-event-import-strict-freeze.md
docs/10-cli-poc-usage.md
README.md
README.en.md
tasks/progress.md
```

### 必须验证

```bash
python -m pytest tests/test_runtime_event_import_strict_freeze.py -q
python -m pytest tests/test_controlled_write_regression.py -q
python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q
python -m pytest -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
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

## push / 网络提示

今天多次 push 到 GitHub 时直连出现 `Recv failure: Connection was reset`，需要：

1. `python D:\Qwenclaw\s-black\tools\open_v2ray.py`
2. 显式注入：
   - `HTTP_PROXY=http://127.0.0.1:10808`
   - `HTTPS_PROXY=http://127.0.0.1:10808`
3. push 成功后必须关闭：
   - `D:\Qwenclaw\s-black\tools\close_v2ray.bat`

收尾前务必确认 V2Ray 已关闭、系统代理已恢复。
