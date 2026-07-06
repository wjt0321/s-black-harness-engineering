# 2026-07-06 Runtime Event Append Commit 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成 **Runtime Event Append Commit** 功能提交，准备冻结为：

```text
v0.8.0-runtime-event-append-commit
```

功能提交：

```text
08ea4fd Add runtime event append commit
```

本阶段是 Controlled Write POC 的第四步：允许 Runtime 在严格受控范围内向 event ledger 追加一个事件，但仅限 append exactly one JSON object as the last line of an event ledger JSONL file。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> runtime draft export --commit
  -> runtime event append --dry-run
  -> runtime event append --commit
  -> adapter validate / adapter inspect
  -> runtime gate check
  -> runtime check-ledger
  -> runtime report
```

## 当前已实现能力

### 基础 POC 与规则模型

- policy / task / event / agent / adapter schema 与样例。
- CLI POC。
- `doctor` 项目结构与样例校验。
- `check text` / `check path` / `check action`。
- agent -> policy profile registry 映射。
- public scan 产品化并纳入 CI。

### Task Ledger

- `task status`
- `task events`
- `task validate`
- `task check-ledger`

### Adapter Envelope

- `adapter plan`
- `adapter validate`
- `adapter inspect`
- `adapter approval check`
- `adapter response check`
- `adapter gate check`

### Runtime Bridge

- `runtime plan`
- `runtime plan --draft-json`
- `runtime draft validate`
- `runtime draft inspect`
- `runtime draft export --dry-run`
- `runtime draft export --commit`
- `runtime event append --dry-run`
- `runtime event append --commit`
- `runtime gate check`
- `runtime check-ledger`
- `runtime report`

## 关键文档

- `docs/21-controlled-write-boundaries.md` - 受控写入边界设计。
- `docs/26-runtime-event-append-dry-run.md` - runtime event append dry-run 设计与用法。
- `docs/27-release-notes-runtime-event-append-dry-run.md` - v0.7 release notes。
- `docs/28-runtime-event-append-commit.md` - runtime event append commit 设计与用法。
- `docs/29-release-notes-runtime-event-append-commit.md` - v0.8 release notes。

## 常用恢复命令

```bash
git status -sb
git log -1 --oneline
git tag --points-at HEAD
python -m pytest
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期在冻结提交后：

```text
main...origin/main
latest tag: v0.8.0-runtime-event-append-commit
python -m pytest -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

## 当前 CLI 抽查命令

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --dry-run
```

```bash
python -m agent_runtime.cli runtime event append \
  --file candidate-event.json \
  --commit
```

注意：commit 会真实追加一行到 event ledger。抽查时应使用测试临时目录或人工准备 disposable ledger，避免污染仓库样例 ledger。

## 最新验证结果

功能提交后验证：

```text
python -m pytest -q -> passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task -> PASS
python -m agent_runtime.cli task validate --record-file tasks/events.jsonl --schema event -> PASS
python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl -> PASS
key pattern scan -> OK key scan
```

## 安全边界

当前允许的写入只有：

- `runtime draft export --commit` 写入 `drafts/runtime/.../*.json` 的新文件。
- `runtime event append --commit` 追加一个 JSON object 到 event ledger JSONL 最后一行。

仍禁止：

- 执行真实 adapter。
- 访问网络。
- 发送消息。
- 写 adapter envelope。
- 修改 task snapshot ledger。
- 覆盖、删除、重排或重写历史 event。
- 批量 import。
- 自动修复 ledger。
- 写 sample ledger。
- 隐式创建 event ledger 父目录。
- 读取 `.env`、`.env.local` 或 credential 文件。
- 回显完整 secret match、target、input、evidence、raw_ref、decision_ref。

## 后续建议

下一阶段建议继续保持只读/低风险路线，不直接进入 adapter execution。可选方向：

- `runtime report` 对 append 后状态的 smoke 文档。
- task 创建 dry-run。
- 批量 event import dry-run。
- ledger compaction dry-run。
