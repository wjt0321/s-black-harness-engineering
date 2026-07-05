# 2026-07-05 Draft Export Commit 接续上下文

> 本文件供压缩后恢复 `s-black harness engineering` 项目使用。当前项目根目录：仓库 checkout 根目录。GitHub 仓库：`https://github.com/wjt0321/s-black-harness-engineering`。

## 当前结论

`s-black harness engineering` 已完成并冻结 **Runtime Draft Export Commit** 阶段。

当前阶段 tag：

```text
v0.6.0-runtime-draft-export-commit
```

当前 HEAD：

```text
5761b42 Merge runtime draft export commit
```

当前本地与远端应保持一致：

```text
main...origin/main
```

本阶段是 Controlled Write POC 的第二步：允许 Runtime 在严格受控范围内写入项目内 draft 文件，但仅限 `drafts/runtime/.../*.json` 的新文件。

## 当前完整链路

当前链路为：

```text
task ledger
  -> runtime plan --draft-json
  -> runtime draft validate
  -> runtime draft inspect
  -> runtime draft export --dry-run
  -> runtime draft export --commit
  -> adapter validate / adapter inspect
  -> runtime gate check
  -> runtime check-ledger
  -> runtime report
```

`runtime draft export --commit` 的职责是：把已经通过全部预检的 envelope draft 落盘到受控 draft 路径，并在写入后立即重新 validate / inspect。

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
- `runtime gate check`
- `runtime check-ledger`
- `runtime report`

## 关键文档

- `docs/21-controlled-write-boundaries.md` — 受控写入边界设计。
- `docs/22-runtime-draft-export-dry-run.md` — runtime draft export dry-run 设计与用法。
- `docs/23-release-notes-runtime-draft-export-dry-run.md` — v0.5 release notes。
- `docs/24-runtime-draft-export-commit.md` — runtime draft export commit 设计与用法。
- `docs/25-release-notes-runtime-draft-export-commit.md` — v0.6 release notes。

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
HEAD: 5761b42 Merge runtime draft export commit
tag: v0.6.0-runtime-draft-export-commit
python -m pytest -> 232 passed
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
  --commit
```

预期：

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-smoke/req-smoke.envelope.json
Committed: True
Validation: pass
Post validate: pass
Post inspect: pass
Artifact counts: adapter_request=1
Next: Draft committed; run runtime gate check before adapter execution.
```

注意：该 smoke 会真实创建 `drafts/runtime/task-smoke/req-smoke.envelope.json`。若只是抽查不希望留下文件，应使用测试临时目录或执行后按清理规则处理。

## 最新验证结果

v0.6 阶段收口前验证：

```text
python -m pytest -> 232 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
key pattern scan -> OK key scan
```

## 安全边界

当前允许的写入只有：

- `runtime draft export --commit` 写入 `drafts/runtime/.../*.json` 的新文件。

仍禁止：

- 执行真实 adapter。
- 访问网络。
- 发送消息。
- 写 task/event ledger。
- overwrite 已存在 draft。
- 写 `drafts/runtime/` 以外路径。
- 读取 `.env`、`.env.local` 或 credential 文件。
- 删除任何非本命令刚创建的 draft 文件。
- 回显完整 secret match、target、input、evidence、raw_ref、decision_ref。

## 推送记录与注意事项

本轮功能 push 时 GitHub 直连超时，处理流程：

1. 先跑 `python -m pytest`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`。
2. 推送前对 `origin/main..HEAD` 做 key pattern scan。
3. 直连失败后，临时启用维护者工具工作区里的 V2Ray 启动脚本。
4. 在项目 checkout 根目录注入：

```bat
set HTTP_PROXY=http://127.0.0.1:10808&& set HTTPS_PROXY=http://127.0.0.1:10808&& git push
```

5. 推送完成后执行维护者工具工作区的关闭脚本，并确认系统代理恢复。

功能 push 完成后已关闭 V2Ray，系统代理已恢复。

## 下一阶段建议

下一阶段建议进入更低风险的 ledger 写入前置阶段：

```text
runtime event append --dry-run
```

建议仅做 dry-run：

- 读取候选 event JSON。
- 校验 `tasks/event.schema.json`。
- 检查 task_id 是否存在。
- 检查状态流转是否合法。
- 在临时内存 ledger 中模拟 append 后运行 ledger consistency。
- 如有 envelope，模拟 runtime ledger audit。
- 输出 append 摘要和 blockers。
- 不写 `tasks/events.jsonl`。

不要直接实现真实 event append，也不要进入 adapter execution。
