# 2026-07-05 Draft Export Dry-run 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成并冻结 **Runtime Draft Export Dry-run** 阶段。

当前阶段 tag：

```text
v0.5.0-runtime-draft-export-dry-run
```

当前 HEAD：

```text
4339153 Merge runtime draft export dry-run
```

当前本地与远端应保持一致：

```text
main...origin/main
```

本阶段是 Controlled Write POC 的第一步，但仍然是只读：`runtime draft export --dry-run` 只做验证和摘要展示，不写文件、不创建目录、不覆盖文件。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> adapter validate / adapter inspect
  -> runtime gate check
  -> runtime check-ledger
  -> runtime report
```

`runtime draft export --dry-run` 的职责是：在真正导出 draft 前检查输入、输出路径和内容风险，并确认将来可写入的目标路径。

## 当前已实现能力

### 基础 POC 与规则模型

- policy / task / event / agent / adapter schema 与样例。
- 只读 CLI POC。
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
- `runtime gate check`
- `runtime check-ledger`
- `runtime report`

## 关键文档

- `docs/21-controlled-write-boundaries.md` — 受控写入边界设计。
- `docs/22-runtime-draft-export-dry-run.md` — runtime draft export dry-run 设计与用法。
- `docs/23-release-notes-runtime-draft-export-dry-run.md` — v0.5 阶段 release notes。

更早阶段文档：

- `docs/17-runtime-planning-bridge.md`
- `docs/18-release-notes-runtime-planning-bridge.md`
- `docs/19-runtime-report.md`
- `docs/20-release-notes-runtime-report.md`

## 常用恢复命令

```bash
git status -sb
git log -1 --oneline
git tag --points-at HEAD
python -m pytest
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

预期：

```text
main...origin/main
HEAD: 4339153 Merge runtime draft export dry-run
tag: v0.5.0-runtime-draft-export-dry-run
python -m pytest -> 221 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
```

## 当前 CLI 抽查命令

```bash
python -m agent_runtime.cli adapter plan \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --json | \
python -m agent_runtime.cli runtime draft export \
  --stdin \
  --output drafts/runtime/task-smoke/req-smoke.envelope.json \
  --dry-run
```

预期：

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-smoke/req-smoke.envelope.json
Would write: False
Validation: pass
Artifact counts: adapter_request=1
Next: Use --commit to persist the draft (not yet implemented).
```

并且目标文件不存在。

## 最新验证结果

v0.5 阶段收口前验证：

```text
python -m pytest -> 221 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

## 安全边界

当前仍保持只读：

- 不执行真实 adapter。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写 `tasks/tasks.jsonl`、`tasks/events.jsonl` 或 adapter envelope 文件。
- 不创建 draft 目录或 draft 文件。
- 不读取 `.env`、`.env.local` 或 credential 文件。
- 不回显完整 secret match。
- 不回显完整 `target`、`input`、`evidence`、`raw_ref`、`decision_ref`。

## 推送记录与注意事项

本轮功能 push 时 GitHub 直连超时，处理流程：

1. 先跑 `python -m pytest`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`。
2. 推送前对 commit diff 做 key pattern scan。
3. 直连失败后，临时启用维护者工具工作区里的 V2Ray 启动脚本。
4. 在项目 checkout 根目录注入：

```bat
set HTTP_PROXY=http://127.0.0.1:10808&& set HTTPS_PROXY=http://127.0.0.1:10808&& git push
```

5. 推送完成后执行维护者工具工作区的关闭脚本，并确认系统代理恢复。

功能 push 完成后已关闭 V2Ray，系统代理已恢复。

## 下一阶段建议

下一阶段可以考虑最小 `runtime draft export --commit`，但必须继续收窄：

- 仅允许新文件。
- 仅允许 `drafts/runtime/.../*.json`。
- 不支持 overwrite。
- 写入前复用 dry-run 全部检查。
- 写入后立即 `runtime draft validate` / `runtime draft inspect`。
- 写入失败时删除半写入文件。
- 仍不写 task/event ledger。

建议下一阶段先写/实现：

```text
docs/24-runtime-draft-export-commit.md
```

不要直接进入 event append 或 adapter execution。
