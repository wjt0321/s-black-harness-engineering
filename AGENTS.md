# AGENTS.md

本文件面向 AI 编码 Agent。阅读者应当被假设为**不了解本项目背景**，需要通过本文档快速理解项目结构、技术栈、构建测试方式、代码约定与安全边界。

项目主要文档以中文撰写，因此本文件也使用中文。

---

## 项目概述

**s-black harness engineering**（仓库内也称 `agent_runtime`）是一个轻量的 Agent Runtime / Harness Orchestrator 长期工程。目标是逐步把 Agent 调度、规则门禁、任务账本、工具适配器和完成验证流程，从单一宿主框架中抽象成一套小型、可审计、可迁移的运行层。

当前阶段：**只读 CLI POC 已可运行**（版本 `0.1.0`）。第一阶段只做文档、协议、schema、样例和边界设计，不接入真实执行链路，也不会替代 [QwenPaw](https://github.com/agentscope-ai/QwenPaw)。QwenPaw 被视为未来可接入的宿主/适配器之一。

### 当前已实现能力

- `doctor`：校验项目结构、JSON/JSONL 语法、schema 兼容性和公开发布风险文本扫描。
- `check text`：对文本/文件/stdin 做密钥模式扫描，命中后不回显完整匹配值。
- `check path`：对目标路径做只读、目录、扩展名等路径规则检查。
- `check action`：对 adapter + operation 做风险级别和 command rule 判断。
- `agents list` / `adapters list` / `policies list`：只读列表查询，支持过滤和 JSON 输出。

### 明确不做的（第一阶段）

- 不替代 QwenPaw，不做 UI 或桌面壳。
- 不启动长期后台服务，不接管定时任务。
- 不做模型代理或计费系统。
- 不在设计稳定前静默执行真实外部操作（不发消息、不删文件、不 push、不访问网络）。

---

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/` | Python 包，CLI 与核心检查逻辑 |
| `tests/` | pytest 测试 |
| `docs/` | 架构、路线图、协议说明（Markdown，中文为主） |
| `policies/` | Policy schema 与样例 policy |
| `agents/` | Agent registry schema 与样例注册表 |
| `adapters/` | Adapter schema 与样例注册表 |
| `tasks/` | Task / event schema、样例 JSONL、进度与交接记录 |
| `cli/` | CLI 命令边界样例数据 |
| `logs/` | 预留运行时日志目录（当前不写入） |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

### 关键源文件

- `agent_runtime/__init__.py`：包入口，定义 `__version__ = "0.1.0"`。
- `agent_runtime/__main__.py`：支持 `python -m agent_runtime`。
- `agent_runtime/cli.py`：argparse 命令行入口与所有子命令调度。
- `agent_runtime/doctor.py`：`doctor` 命令实现，校验结构、schema、JSONL 和公开扫描。
- `agent_runtime/loader.py`：数据文件加载工具，含安全读取白名单/黑名单。
- `agent_runtime/policy.py`：`check text` / `check path` / `check action` 的规则检查实现。
- `agent_runtime/result.py`：`Finding`、`CheckResult` 数据模型，输出格式化与退出码。

### 关键 Schema 与样例

- `policies/policy.schema.json`：policy JSON Schema。
- `policies/*.sample.policy.json`：样例 policy（s-black、wangcai、dabai）。
- `agents/agents.schema.json`：agent registry JSON Schema。
- `agents/agents.sample.json`：样例 agent 注册表。
- `adapters/adapter.schema.json`：adapter registry JSON Schema。
- `adapters/adapters.sample.json`：样例 adapter 注册表。
- `tasks/task.schema.json`、`tasks/event.schema.json`：任务与事件 JSON Schema。
- `tasks/*.jsonl`：任务与事件样例数据。

---

## 技术栈

- **语言**：Python 3.12+（已在 Python 3.14.0 环境验证）。
- **标准库**：`argparse`、`json`、`pathlib`、`re`、`sys`、`dataclasses` 等。
- **第三方依赖**：
  - `jsonschema`：`doctor` 中用于 schema 校验。
  - `pytest`：测试框架（开发依赖）。
- **无打包配置**：当前没有 `pyproject.toml`、`setup.py`、`requirements.txt`、`Pipfile` 或 `poetry.lock`。依赖需要由运行环境手动安装。
- **无构建步骤**：纯 Python，无需编译。

---

## 构建与运行

### 环境要求

- Python 3.12 或更高版本。
- 安装 `jsonschema`：

  ```bash
  pip install jsonschema pytest
  ```

### 运行 CLI

两种入口等价：

```bash
python -m agent_runtime.cli <command>
python -m agent_runtime <command>
```

常用命令：

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check text --file README.md
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli check action --adapter github-cli --operation git_push --target origin/main
python -m agent_runtime.cli agents list --capability planning
python -m agent_runtime.cli adapters list --kind github
python -m agent_runtime.cli policies list
```

全局参数：

| 参数 | 说明 |
|:---|:---|
| `--root <path>` | 项目根目录，默认当前目录 |
| `--policy <file>` | 显式指定 policy 文件 |
| `--json` | 输出 JSON |
| `--no-color` | 禁用彩色输出（预留） |
| `--quiet` | 保留给后续精简输出使用 |
| `--verbose` | 保留给后续诊断输出使用 |

### 退出码

| 码 | 含义 |
|:---:|:---|
| `0` | 通过或查询成功 |
| `1` | CLI 使用错误或内部错误 |
| `2` | policy 阻断 |
| `3` | 需要用户授权 |
| `4` | 需要更多输入 |
| `5` | 校验失败 |

---

## 测试

### 运行全部测试

```bash
python -m pytest tests -q
```

当前共有 23 个测试，覆盖：

- `tests/test_cli.py`：CLI 入口与主要命令行为。
- `tests/test_doctor.py`：`doctor` 校验通过/失败场景。
- `tests/test_policy_text.py`：密钥模式扫描、行号列号、不回显完整匹配。
- `tests/test_policy_path.py`：路径规则只读/目录/扩展名判断。

### 写测试的约定

- 使用 pytest。
- 测试中的 token/key 应当在内存中动态拼接（如 `"ghp_" + "X" * 36`），避免在源码里写入看起来像真实密钥的字符串。
- 断言检查状态码、输出中是否包含规则 id、以及敏感值是否**不**出现在输出中。
- 项目根目录常量：`ROOT = Path(__file__).resolve().parents[1]`。

---

## 代码风格与开发约定

### 语言与注释

- 项目文档、README、进度记录以**中文**为主。
- 代码内 docstring 和注释目前以英文为主，保持简洁。
- 新增文档建议优先中文，方便用户直接查看和判断。

### 导入顺序

当前源码遵循的相对一致的风格：

1. `from __future__ import annotations`
2. 标准库
3. 第三方库
4. 本项目相对导入

### 类型提示

- 使用 `from __future__ import annotations`。
- 函数签名使用类型提示，返回类型明确标注。
- 使用 `|` 联合类型（如 `Path | None`）。

### 路径处理

- 使用 `pathlib.Path`，不使用 `os.path`。
- 跨平台路径比较使用 `loader.normalize_path()` 转成正斜杠。

### 错误处理

- CLI 顶层 `main()` 捕获 `FileNotFoundError` 和通用异常，统一转成 `CheckResult(status="error", ...)` 并返回非零退出码。
- 安全检查失败用 `Finding` 表达，而不是抛异常。

### 不变的安全边界

第一版 CLI 必须保持只读：

- 不执行外部命令。
- 不访问网络。
- 不发送消息。
- 不删除文件。
- 不写真实 task ledger。
- 不读取 `.env`、`.env.local`、`.envrc`、`.secret`、`.key`、`.pem`、`.p12`、`.pfx` 等密钥文件。
- `check text` 命中密钥后，只输出规则 id、位置、提示，不回显完整匹配值。

修改代码时应保持上述边界；若需突破，必须有显式设计文档和用户授权机制。

---

## 安全考虑

### 文件读取白名单

`agent_runtime/loader.py` 定义了 `is_safe_to_read()`，明确拒绝常见密钥/环境文件。公开扫描（doctor 的 public scan）只遍历以下后缀：

`.json`、`.jsonl`、`.md`、`.txt`、`.py`、`.sample`、`""`（无后缀）、`.yml`、`.yaml`。

同时跳过 `.git`、`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`。

### Secret 输出控制

- `Finding` 只包含 `rule_id`、`severity`、`action`、`message`、`line`、`column`。
- 扫描结果中不保存也不输出匹配到的完整 secret。
- 测试明确断言完整 token 不出现在 `render_json()` 和 `render_human()` 中。

### 高风险动作映射

- `path_rules` 中的 `readonly` 会在写/删操作时触发阻断。
- `command_rules` 通过正则匹配危险命令（如 `git push`、`rm -rf`、代理修改、强杀进程）。
- `check_action` 对 `risk_level == "external"` 或 `requires_approval == true` 的 adapter 返回 `NEEDS_APPROVAL`。

---

## 设计文档索引

核心设计都落在 `docs/` 中，按编号顺序阅读最清晰：

1. `docs/01-vision-and-boundaries.md`：愿景与边界。
2. `docs/02-roadmap.md`：路线图。
3. `docs/03-policy-schema.md`：通用 Policy Schema。
4. `docs/04-task-state-model.md`：任务状态模型。
5. `docs/05-agent-registry.md`：Agent 注册表。
6. `docs/06-adapter-layer.md`：工具适配器层。
7. `docs/07-policy-task-bridge.md`：Policy 与 Task 状态衔接。
8. `docs/08-minimal-cli-design.md`：最小 CLI 设计。
9. `docs/09-policy-checker-poc-plan.md`：Policy Checker POC 计划。
10. `docs/10-cli-poc-usage.md`：CLI POC 使用说明。

进度与交接：

- `tasks/progress.md`：每日推进记录。
- `tasks/handoff-2026-07-02.md`、`tasks/handoff-2026-07-03.md`：会话交接上下文。

---

## 给 Agent 的实战提示

1. **先跑 doctor**：做任何改动后，先执行 `python -m agent_runtime.cli doctor`，确认结构、schema 和公开扫描都通过。
2. **再跑测试**：执行 `python -m pytest tests -q`，确保没有回归。
3. **不改只读边界**：除非任务明确要求并已有设计文档，否则不要让 CLI 执行外部命令、写 ledger、删文件或访问网络。
4. **敏感信息不进源码**：不要在代码、测试、样例 JSON 中硬编码真实密钥；测试用动态拼接的假 token。
5. **保持 schema 与实现同步**：修改 `policies/`、`agents/`、`adapters/`、`tasks/` 下的 schema 或样例后，检查对应 Python 代码是否需要调整。
6. **文档优先中文**：新增 README、docs、notes、handoff 等文档时优先使用中文。
7. **小步可审查**：每次变更保持聚焦，方便 Orchestrator 做安全与质量验收。
