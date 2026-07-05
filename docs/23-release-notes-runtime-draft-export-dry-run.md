# 23 — Runtime Draft Export Dry-run 阶段收口说明

## 阶段定位

本阶段冻结最小 Controlled Write POC 的第一步：`runtime draft export --dry-run`。

它不是正式写入功能，而是写入前检查门：读取 runtime plan envelope draft，完成 schema / consistency / path / secret / public-risk 检查，并展示如果未来执行导出将写到哪里，但本阶段绝不落盘。

当前仍保持只读：不执行 adapter，不访问网络，不发送消息，不删除文件，不写真实 task ledger / event ledger / adapter envelope，不读取 `.env` / credential。

## 新增能力

### `runtime draft export --dry-run`

从 stdin 读取：

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
  --dry-run
```

从文件读取：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --dry-run
```

支持全局 `--json` 输出。

## 检查内容

`runtime draft export --dry-run` 会执行：

- 输入 JSON 解析。
- 支持 direct envelope 与 `runtime plan --draft-json` wrapper。
- envelope schema validation。
- envelope artifact consistency validation。
- output path guard：
  - 必须位于项目根目录内。
  - 必须使用 `.json` 后缀。
  - 不允许路径逃逸。
  - 不允许指向 credential / `.git` internals。
  - 目标文件已存在时 blocked。
- 内容扫描：
  - policy secret scan。
  - public scan rules。
- 输出脱敏：不回显完整 target、input payload、evidence description、raw_ref、decision_ref 或 secret match。

## 输出示例

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-smoke/req-smoke.envelope.json
Would write: False
Validation: pass
Artifact counts: adapter_request=1
Next: Use --commit to persist the draft (not yet implemented).
```

其中 `Would write: False` 是本阶段核心约束：即使所有检查通过，也不创建目标文件、不创建目录、不覆盖文件。

## 实现文件

- `agent_runtime/runtime_draft_export.py` — dry-run export 核心逻辑。
- `agent_runtime/cli.py` — 注册 `runtime draft export` 子命令与输出渲染。
- `tests/test_runtime_draft_export.py` — 测试覆盖。
- `docs/22-runtime-draft-export-dry-run.md` — 命令设计与用法说明。

## 验证结果

本阶段收口前验证：

```text
python -m pytest -> 221 passed
python -m agent_runtime.cli doctor -> PASS
python tools/public_scan.py -> OK public scan
git diff --check -> PASS
```

推送前额外执行：

```text
key pattern scan -> OK key scan
```

Smoke test：

```text
runtime draft export --dry-run -> PASS
OK no file written
```

## 当前限制

- 仅支持 `--dry-run`。
- 不支持 `--commit`。
- 不支持 overwrite。
- 不写文件、不创建目录。
- `--file` 输入必须是项目根目录内安全 `.json` 文件；项目外临时文件会被拒绝。
- 真实 draft export、event append、adapter execution 仍需要后续阶段单独实现和验证。

## 后续建议

下一阶段可以开始设计并实现最小 `runtime draft export --commit`，但建议继续小步推进：

- 仅允许新文件。
- 仅允许 `drafts/runtime/.../*.json`。
- 不支持 overwrite。
- 写入前重复 dry-run 全部检查。
- 写入后立即重新 validate / inspect。
- 失败时删除半写入文件。
- 仍不写 task/event ledger。

建议下一阶段文档：

```text
docs/24-runtime-draft-export-commit.md
```
