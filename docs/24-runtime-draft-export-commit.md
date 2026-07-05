# 24 — Runtime Draft Export Commit

## 目标

在 `runtime draft export --dry-run` 基础上，增加 `--commit` 模式：将已通过全部预检的 envelope draft 持久化到 `drafts/runtime/.../*.json`，并在写入后立即重新验证与摘要。

## 边界

- **不修改 `AGENTS.md`**。
- 不执行 adapter、不访问网络、不发送消息。
- 不删除文件，**除了**本命令半写入的新 draft 文件在失败后回滚删除。
- 不读取 `.env`/credential/密钥文件。
- **只写入新文件**：目标文件已存在即 blocked，不支持 overwrite。
- **只允许**输出到 `drafts/runtime/.../*.json`，且必须在项目根目录内。
- 不写 task/event ledger。
- 写入前复用 dry-run 全部检查：JSON 解析、direct envelope / wrapper 识别、envelope schema、consistency、路径守卫、secret/public scan、目标不存在。
- 写入后重新 `runtime draft validate` 与 `runtime draft inspect`；失败时删除半写入文件并返回 error/blocked。
- 输出不回显完整 `target` / `input` payload / `evidence` description / `raw_ref` / `decision_ref` / secret match。

## CLI 用法

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

从文件导出：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --commit
```

JSON 输出：

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --commit \
  --json
```

## 模式规则

- `--dry-run` 与 `--commit` 互斥，必须显式提供其中一个。
- 都不提供时返回 `error`。
- 同时提供时返回 `error`。

## Commit 成功输出

### 人类输出

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-20260703-001/req-xxx.envelope.json
Committed: true
Validation: pass
Post validate: pass
Post inspect: pass
Artifact counts: adapter_request=1
Next: Draft committed; run runtime gate check before adapter execution.
```

### JSON 输出

```json
{
  "status": "pass",
  "source": "<stdin>",
  "output": "drafts/runtime/task-20260703-001/req-xxx.envelope.json",
  "committed": true,
  "validation": "pass",
  "post_validate": "pass",
  "post_inspect": "pass",
  "artifact_counts": {
    "adapter_request": 1
  },
  "next_action": "Draft committed; run runtime gate check before adapter execution."
}
```

## 写入与回滚

- 序列化格式：`json.dumps(envelope, ensure_ascii=False, indent=2) + "\n"`。
- 父目录在 commit 时自动创建（`drafts/runtime/...` 范围内）。
- 写入前再次检查目标不存在（并发安全兜底）。
- 写入后立即重新 `runtime draft validate` 与 `runtime draft inspect`。
- 如果 post-write 检查失败：
  - 尝试 `unlink()` 删除半写入文件。
  - 删除成功：返回失败状态，提示已回滚。
  - 删除失败：返回 `error`，提示人工清理。

## 路径守卫

除 dry-run 已有的守卫（根目录内、`.json`、不逃逸、非 credential/git internal、不存在）外，commit 模式额外要求：

- 相对路径必须以 `drafts/runtime/` 开头（大小写不敏感）。
- 失败 rule-id：`output-path-not-in-drafts-runtime`。

Dry-run 模式不限制输出路径必须在 `drafts/runtime/` 下。

## 内容扫描

写入前对序列化后的 envelope JSON 文本执行：

1. Secret scan：复用 `agent_runtime.policy.check_text`。
2. Public scan：复用 `tools/public_scan.py` 规则。

命中时返回 `blocked`，不回显完整匹配值，且不写入文件。

## 错误状态映射

| 场景 | 状态 | 返回码 |
|:---|:---|:---:|
| 未提供 `--dry-run`/`--commit` | `error` | 1 |
| 同时提供二者 | `error` | 1 |
| 输出不在 `drafts/runtime/` 下 | `blocked` | 2 |
| 输出文件已存在 | `blocked` | 2 |
| secret/public scan 命中 | `blocked` | 2 |
| 写入失败 | `error` | 1 |
| post-write 校验失败并回滚 | `validation_failed`/`error` | 5/1 |
| 回滚删除失败 | `error` | 1 |

## 与 Dry-run 的关系

- `--dry-run` 保持只读，不写文件，不限定 `drafts/runtime/`。
- `--commit` 在 dry-run 全部检查通过后执行写入与二次校验。

## 实现位置

- `agent_runtime/runtime_draft_export.py`：`export_draft(..., commit=False)` 与 commit 路径。
- `agent_runtime/cli.py`：`runtime draft export` 子命令与模式校验。
- `tests/test_runtime_draft_export_commit.py`：测试覆盖。
