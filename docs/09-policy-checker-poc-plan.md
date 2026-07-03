# 09 — Policy Checker POC 计划

## 这份文档解决什么问题

前面已经定义了 policy schema、task 状态、adapter 边界和 CLI 命令设计。

下一步可以开始考虑第一个最小可运行 POC：Policy Checker。

但这个 POC 必须先定清楚边界，避免一上来写成完整 Runtime，或者不小心执行外部动作。

这份文档定义第一版 policy checker 的实现范围、输入输出、测试样例和禁止事项。

## POC 目标

第一版 Policy Checker 只做三类只读检查：

1. `check text`：扫描文本或文件中的密钥模式。
2. `check path`：检查路径是否违反 path rules。
3. `check action`：根据 adapter、operation、target 生成 action descriptor，并判断是否需要阻断、授权或补检查。

第一版不执行 Adapter，不写任务账本，不发送消息，不删除文件。

## 非目标

第一版不做：

- 不启动后台服务。
- 不执行 shell 命令。
- 不调用 GitHub、飞书或浏览器。
- 不修改外部系统。
- 不自动修复文件。
- 不写真实 `tasks/tasks.jsonl` 或 `tasks/events.jsonl`。
- 不持久化用户授权。
- 不做复杂自然语言理解。

## 推荐实现位置

建议后续代码放在：

```text
agent_runtime/
  __init__.py
  cli.py
  policy.py
  loader.py
  result.py

tests/
  test_policy_text.py
  test_policy_path.py
  test_policy_action.py
```

第一版也可以先用单文件实现，但建议从一开始保持轻量模块化，避免后面拆分困难。

## 输入文件

POC 默认读取：

| 文件 | 用途 |
|:---|:---|
| `policies/policy.schema.json` | 校验 policy 文件结构 |
| `policies/*.sample.policy.json` | 默认 policy 来源 |
| `adapters/adapters.sample.json` | action 检查时读取 adapter 默认风险和能力 |
| `cli/commands.sample.json` | CLI 命令边界参考 |

后续可以增加：

- `policies/local.policy.json`
- `adapters/local.adapters.json`

但第一版不需要。

## 输出模型

建议所有检查统一返回：

```json
{
  "status": "blocked",
  "findings": [
    {
      "rule_id": "github-token",
      "severity": "block",
      "action": "deny",
      "message": "Potential GitHub token detected."
    }
  ],
  "next_action": "Redact the text before publishing."
}
```

## status 取值

| status | 含义 | 返回码 |
|:---|:---|:---:|
| `pass` | 检查通过 | 0 |
| `warn` | 有提醒但不阻断 | 0 |
| `blocked` | 硬阻断 | 2 |
| `needs_approval` | 需要用户授权 | 3 |
| `needs_input` | 需要更多输入 | 4 |
| `error` | checker 自身失败 | 1 |

## check text

### 命令

```bash
agent-runtime check text --file BODY.md
agent-runtime check text --stdin
agent-runtime check text --text "..."
```

### 行为

- 读取文本。
- 遍历 `secret_patterns`。
- 命中后返回 `blocked`。
- 不回显完整密钥。
- 可以返回 pattern id、行号、列号或摘要。

### 示例输出

```text
BLOCKED
- github-token: potential secret detected; redact before publishing.
```

JSON：

```json
{
  "status": "blocked",
  "findings": [
    {
      "rule_id": "github-token",
      "severity": "block",
      "action": "deny",
      "message": "Potential secret detected. Redact before publishing."
    }
  ],
  "next_action": "Redact matched content and run check again."
}
```

## check path

### 命令

```bash
agent-runtime check path ./target.md --write
agent-runtime check path ./target --delete
```

### 行为

- 规范化路径分隔符。
- 根据 `path_rules` 判断前缀、关键词、扩展名、只读规则。
- `--write` 或 `--delete` 遇到 readonly 规则时阻断。
- 只检查，不创建、不删除、不写入文件。

### 示例输出

```text
BLOCKED
- readonly-path: target path is read-only under current policy.
```

## check action

### 命令

```bash
agent-runtime check action --adapter github-cli --operation git_push --target origin/main
```

### 行为

- 从 adapter registry 找 adapter。
- 生成 action descriptor。
- 根据 adapter 的 `risk_level`、`requires_approval`、`preflight_checks` 判断是否需要授权或补检查。
- 根据 policy 的 command/publish 规则做进一步判断。
- 不执行 adapter。

### 示例 descriptor

```json
{
  "adapter_id": "github-cli",
  "operation": "git_push",
  "target": "origin/main",
  "risk_level": "external",
  "requires_approval": true
}
```

### 示例输出

```text
NEEDS_APPROVAL
- github-cli: this external operation requires explicit user approval.
Next: ask for approval for this task, this target, this operation.
```

## policy 加载策略

第一版加载顺序：

1. 如果传入 `--policy <file>`，只加载指定 policy。
2. 否则加载 `policies/*.sample.policy.json`。
3. 多个 policy 同时命中时，取最高严重级别。
4. `block` 优先于 `warn`，`warn` 优先于 `info`。

后续可增加 profile 选择：

```bash
agent-runtime check text --policy policies/s-black.sample.policy.json --file BODY.md
```

## 匹配规则

### 文本规则

- 使用 Python `re`。
- 默认大小写敏感，由 regex 自己决定。
- 不打印完整 match。

### 路径规则

- Windows 和 Unix 路径统一转为 `/`。
- 既支持相对路径，也支持绝对路径。
- public sample 中不应依赖某个固定本机路径。

### Action 规则

第一版只做简单字段判断，不做复杂命令解析。

例如：

- adapter 是 `github-cli` 且 operation 包含 `push` -> needs approval。
- adapter 是 `lark-cli` 且 operation 包含 `send` -> needs approval。
- adapter 是 `shell-local` 且 operation 是 `write_file` -> 检查 path rules。

## 测试样例

### text pass

输入：

```text
hello world
```

期望：

```json
{ "status": "pass" }
```

### text blocked

输入：

```text
ghp_TEST_PLACEHOLDER_DO_NOT_USE
```

期望：

- 文档样例本身不应命中真实密钥正则
- 单元测试可以在内存中动态构造命中样例，但不得把真实格式 token 写入仓库文件
- status = `blocked`
- finding rule_id = `github-token`
- 输出不得包含完整输入值

### path pass

输入：

```text
./docs/06-adapter-layer.md --read
```

期望：

```json
{ "status": "pass" }
```

### path blocked

输入：

```text
./received/raw.png --write
```

期望：

- status = `blocked`
- reason 与 readonly/path rule 相关

### action needs approval

输入：

```text
--adapter github-cli --operation git_push --target origin/main
```

期望：

- status = `needs_approval`
- next_action 要求用户授权

## 安全要求

第一版实现必须满足：

- 不读取 `.env`、`.env.local`、agent 私有配置或任何凭据文件。
- 不输出完整密钥 match。
- 不执行外部命令。
- 不访问网络。
- 不写入 policy、agent、adapter、task 文件。
- 不删除文件。
- 不修改 Git 远端。

## 验收标准

POC 完成后，至少要能跑：

```bash
agent-runtime doctor
agent-runtime check text --text "hello"
agent-runtime check text --text "ghp_TEST_PLACEHOLDER_DO_NOT_USE"
agent-runtime check path ./docs/06-adapter-layer.md --read
agent-runtime adapters list
agent-runtime agents list
agent-runtime policies list
```

并满足：

- JSON / JSONL 样例仍可校验。
- public scan 通过。
- 单元测试通过。
- Git 工作树只包含预期文件。
- README 不需要因为 POC 增加过多实现细节。

## 委派给 Kimi Code 的任务边界

进入实现时，可以委派 Kimi Code 编写 POC。

建议任务说明：

```text
在 s-black harness engineering 中实现最小只读 CLI POC。
范围：doctor、check text、check path、agents list、adapters list、policies list。
禁止：执行外部命令、访问网络、写入真实 task ledger、删除文件、读取 .env 或任何密钥文件。
要求：保留 schema 校验、JSON 输出、测试样例，并确保 public scan 通过。
```

Orchestrator 验收重点：

- 代码是否真的只读。
- 是否可能泄露完整 secret match。
- 路径规则是否跨平台可用。
- 错误返回码是否符合 `docs/08-minimal-cli-design.md`。
- 是否新增了不必要依赖。

## 第一版落地范围

本阶段只交付计划文档：

- `docs/09-policy-checker-poc-plan.md`

下一步才考虑代码实现。
