# 22 — Runtime Draft Export Dry-run

## 目标

`runtime draft export --dry-run` 是 Controlled Write POC 的第一步：把已经通过校验的 runtime plan envelope draft 模拟导出到项目内受控路径，**不落盘**。

它用于在真正持久化 draft 之前，确认：

1. 输入 envelope 通过 schema + consistency 校验。
2. 输出路径位于项目根目录内、后缀为 `.json`、不指向 credential/git internals。
3. 默认禁止覆盖已存在的目标文件。
4. 导出内容通过 policy secret scan 与 public scan，命中则阻断且不回显完整匹配值。

## CLI 用法

### 从 stdin 导出（配合 `runtime plan --draft-json`）

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

### 从文件导出

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --dry-run
```

### JSON 输出

```bash
python -m agent_runtime.cli runtime draft export \
  --file draft.json \
  --output drafts/runtime/task-20260703-001/req-xxx.envelope.json \
  --dry-run \
  --json
```

## 人类输出示例

```text
PASS
Source: <stdin>
Output: drafts/runtime/task-20260703-001/req-xxx.envelope.json
Would write: false
Validation: pass
Artifact counts: adapter_request=1, approval_record=0, execution_event=0, adapter_response=0
Next: Use --commit to persist the draft (not yet implemented).
```

## JSON 输出示例

```json
{
  "status": "pass",
  "source": "<stdin>",
  "output": "drafts/runtime/task-20260703-001/req-xxx.envelope.json",
  "would_write": false,
  "validation": "pass",
  "artifact_counts": {
    "adapter_request": 1,
    "approval_record": 0,
    "execution_event": 0,
    "adapter_response": 0
  },
  "next_action": "Use --commit to persist the draft (not yet implemented)."
}
```

JSON 输出不回显完整 `target`、`input` payload、`evidence` description、`raw_ref`、`decision_ref` 或 secret match。

## 输出路径守卫

`--output` 必须满足以下全部条件，否则返回 `blocked`（返回码 `2`）：

1. 解析后必须位于项目根目录内。
2. 必须以 `.json` 结尾（大小写不敏感）。
3. 不能包含 `..` 或路径逃逸。
4. 不能指向 `.env`、credential、密钥类文件。
5. 不能指向 `.git/` 等 git internals。
6. 目标文件已存在时必须被阻断（即使 `--dry-run` 也不允许覆盖）。

相关 `rule_id`：

- `output-path-outside-root`
- `output-path-escapes-root`
- `output-path-not-json`
- `output-path-unsafe`
- `output-path-points-to-git-internal`
- `output-file-exists`

## 内容扫描

导出前会对序列化后的 envelope JSON 文本执行两类扫描：

1. **Secret scan**：复用项目 policy 的 `secret_patterns`（`agent_runtime.policy.check_text`）。
2. **Public scan**：复用 `tools/public_scan.py` 的发布风险规则（GitHub token、OpenAI-style key、Windows 绝对路径、Unix home 路径等）。

命中时只输出规则 id 与行号，不回显完整匹配值。

## 错误状态映射

| 场景 | 状态 | 返回码 |
|:---|:---|:---:|
| 输入 JSON 非法 | `validation_failed` | 5 |
| 输入非 direct envelope / wrapper | `validation_failed` | 5 |
| envelope schema 失败 | `validation_failed` | 5 |
| envelope consistency 失败 | `validation_failed` | 5 |
| 输出路径根外 / 逃逸 | `blocked` | 2 |
| 输出后缀非 `.json` | `blocked` | 2 |
| 输出指向 credential/git | `blocked` | 2 |
| 输出文件已存在 | `blocked` | 2 |
| 内容命中 secret/public scan | `blocked` | 2 |
| 未提供 `--dry-run` | `error` | 1 |

## 行为约束

- 只读：`--dry-run` 是唯一支持的模式，`--commit` 未实现。
- 不写文件、不覆盖文件、不创建空目录（即使 dry-run 通过也不创建目标文件）。
- 不执行 adapter、不访问网络、不发送消息、不删除文件。
- 不读取 `.env`/credential 文件。
- 输出不回显完整 `target` / `input` / `raw_ref` / `decision_ref` / evidence description / secret match。

## 实现位置

- `agent_runtime/runtime_draft_export.py`：核心 dry-run 逻辑。
- `agent_runtime/cli.py`：`runtime draft export` 子命令注册与输出渲染。
- `tests/test_runtime_draft_export.py`：测试覆盖。
