# 10 — CLI POC 使用说明

## 当前状态

`s-black harness engineering` 现在已经有第一版最小只读 CLI POC。

它不是完整 Runtime，也不会执行外部动作。当前 CLI 只用于读取本仓库内的 schema、sample、JSONL 和文档，做结构校验、规则检查和列表查询。

## 运行方式

在仓库根目录运行：

```bash
python -m agent_runtime.cli <command>
```

也可以使用：

```bash
python -m agent_runtime <command>
```

## 快速自检

```bash
python -m agent_runtime.cli doctor
```

期望输出：

```text
PASS
Next: All checks passed.
```

`doctor` 会检查：

- 必要目录是否存在。
- 必要文件是否存在。
- JSON schema 是否为合法 JSON。
- sample JSON 是否能通过对应 schema。
- JSONL 样例是否逐行合法。
- 仓库文本文件是否命中公开发布风险扫描。

## 文本密钥扫描

```bash
python -m agent_runtime.cli check text --text hello
```

期望输出：

```text
PASS
```

从文件读取：

```bash
python -m agent_runtime.cli check text --file README.md
```

从 stdin 读取：

```bash
echo hello | python -m agent_runtime.cli check text --stdin
```

JSON 输出：

```bash
python -m agent_runtime.cli check text --text hello --json
```

注意：如果命中密钥模式，CLI 只输出规则 id、行号、列号和提示，不回显完整匹配值。

## 路径检查

```bash
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
```

写入检查：

```bash
python -m agent_runtime.cli check path ./some-target.md --write
```

删除检查：

```bash
python -m agent_runtime.cli check path ./some-target.md --delete
```

当前路径检查只做 policy 规则判断，不会创建、修改或删除任何文件。

## Action 检查

检查 GitHub push 这类外部动作：

```bash
python -m agent_runtime.cli check action --adapter github-cli --operation git_push --target origin/main
```

期望输出类似：

```text
NEEDS_APPROVAL
- github-cli-approval: github-cli: this external operation requires explicit user approval.
Next: Ask for approval for this task, this target, this operation.
```

低风险只读动作示例：

```bash
python -m agent_runtime.cli check action --adapter shell-local --operation read_file --target docs/README.md
```

期望输出：

```text
PASS
```

## Registry 查询

列出 Agent：

```bash
python -m agent_runtime.cli agents list
```

按 capability 过滤：

```bash
python -m agent_runtime.cli agents list --capability light_coding
```

列出 Adapter：

```bash
python -m agent_runtime.cli adapters list
```

按 kind 过滤：

```bash
python -m agent_runtime.cli adapters list --kind github
```

按 risk 过滤：

```bash
python -m agent_runtime.cli adapters list --risk external
```

列出 Policy：

```bash
python -m agent_runtime.cli policies list
```

## 全局参数

| 参数 | 说明 |
|:---|:---|
| `--root <path>` | 指定项目根目录，默认当前目录 |
| `--policy <file>` | 指定单个 policy 文件 |
| `--json` | 输出 JSON |
| `--no-color` | 禁用彩色输出 |
| `--quiet` | 保留给后续精简输出使用 |
| `--verbose` | 保留给后续诊断输出使用 |

## 返回码

| 返回码 | 含义 |
|:---|:---|
| `0` | 通过或查询成功 |
| `1` | CLI 使用错误或内部错误 |
| `2` | policy 阻断 |
| `3` | 需要用户授权 |
| `4` | 需要更多输入 |
| `5` | 校验失败 |

## 当前安全边界

第一版 CLI 保持只读：

- 不执行外部命令。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写真实 task ledger。
- 不读取 `.env`、`.env.local` 或密钥文件。
- 不回显完整 secret match。

## 当前限制

- `check action` 还是基础版，只做 adapter 风险、授权和部分 command rule 判断。
- 还没有真实 `tasks/tasks.jsonl` 和 `tasks/events.jsonl` 写入能力。
- 还没有后台服务。
- 还没有插件系统或真实 adapter 执行。
- 还没有打包发布为全局命令。

## 阶段性结论

到这一版为止，项目已经从纯文档推进到一个可运行、可测试、可审查的只读 POC。

这可以作为后续 Runtime 实现的第一块稳定地基：先验证规则、schema、registry 和 CLI 边界，再逐步扩展真实执行能力。
