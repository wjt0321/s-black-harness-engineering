# 25 — Runtime Draft Export Commit 阶段收口说明

## 阶段定位

本阶段冻结最小 Controlled Write POC 的第二步：`runtime draft export --commit`。

这是本项目第一次允许 Runtime 在受控范围内写入项目文件，但写入边界被严格收窄：只允许把已通过全部预检的 adapter envelope draft 写入 `drafts/runtime/.../*.json` 的新文件。它仍然不执行 adapter、不访问网络、不发送消息、不写 task/event ledger。

## 新增能力

### `runtime draft export --commit`

从 stdin 写入：

```bash
python -m agent_runtime.cli runtime plan \
  --task-id task-20260703-001 \
  --adapter shell-local \
  --operation read_file \
  --target docs/06-adapter-layer.md \
  --draft-json | \
python -m agent_runtime.cli runtime draft export \
  --stdin \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --commit
```

从文件写入：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --commit
```

`--dry-run` 仍保留只读语义；`--dry-run` 与 `--commit` 互斥，且必须显式提供其中一个。

## 写入前检查

`--commit` 写入前复用 dry-run 全部检查：

- JSON 可解析。
- 支持 direct envelope 与 `runtime plan --draft-json` wrapper。
- envelope schema validation。
- envelope artifact consistency validation。
- output path guard：
  - 必须位于项目根目录内。
  - 必须使用 `.json` 后缀。
  - 不允许路径逃逸。
  - 不允许指向 credential / `.git` internals。
  - 目标文件必须不存在。
- commit 额外路径限制：
  - 输出路径必须位于 `drafts/runtime/.../*.json`。
- 内容扫描：
  - policy secret scan。
  - public scan rules。
- 输出脱敏：不回显完整 target、input payload、evidence description、raw_ref、decision_ref 或 secret match。

## 写入行为

成功写入时：

- 父目录可自动创建，但只能在 `drafts/runtime/...` 范围内。
- 写入格式稳定：`json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"`。
- 不支持 overwrite；目标存在即 blocked。
- 不写 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。

## 写入后检查与回滚

写入后立即重新检查：

- `runtime draft validate --file <output>`。
- `runtime draft inspect --file <output>`。

如果 post-check 失败：

- 尝试删除本命令刚创建的半写入 draft 文件。
- 删除成功后返回失败状态并说明已回滚。
- 删除失败则返回 error，提示人工清理。

## 输出示例

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-20260703-001/req-xxx.envelope.json
Committed: True
Validation: pass
Post validate: pass
Post inspect: pass
Artifact counts: adapter_request=1
Next: Draft committed; run runtime gate check before adapter execution.
```

## 实现文件

- `agent_runtime/runtime_draft_export.py` — 扩展 `export_draft(..., commit=False)` 与 commit 路径。
- `agent_runtime/cli.py` — `runtime draft export` 模式校验与输出渲染。
- `tests/test_runtime_draft_export_commit.py` — commit 模式测试覆盖。
- `docs/24-runtime-draft-export-commit.md` — commit 模式设计与用法。

## 验证结果

本阶段收口前验证：

```text
python -m pytest -> 232 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

推送前额外执行：

```text
key pattern scan -> OK key scan
```

## 当前限制

- 不支持 overwrite。
- 不支持写到 `drafts/runtime/` 以外。
- 不写 task/event ledger。
- 不执行 adapter。
- 不访问网络、不发送消息。
- 不删除任何非本命令刚创建的 draft 文件。

## 后续建议

下一阶段建议先不要进入 adapter execution，而是进入更低风险的 ledger 写入前置阶段：

```text
runtime event append --dry-run
```

建议先只实现 dry-run：读取候选 task event，校验 schema、状态流转、ledger consistency、runtime ledger audit 预期结果，并展示 append 摘要，但不写入 `tasks/events.jsonl`。
