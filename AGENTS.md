# AGENTS.md

本文件面向 AI 编码 Agent。阅读者应当被假设为**不了解本项目背景**，需要通过本文档快速理解项目结构、技术栈、构建测试方式、代码约定与安全边界。

项目主要文档以中文撰写，因此本文件也使用中文。

---

## 项目概述

**s-black harness engineering**（仓库内也称 `agent_runtime`）是一个轻量的 Agent Runtime / Harness Orchestrator 长期工程。目标是逐步把 Agent 调度、规则门禁、任务账本、工具适配器和完成验证流程，从单一宿主框架中抽象成一套小型、可审计、可迁移的运行层，并进一步演进为面向多 Agent、多工具、多渠道的**中枢运行台（Orchestration Hub / Control Plane）**。

当前阶段：**Runtime 受控写入内核 + 中枢台编排基础已成型**。最新稳定基线为 `v0.12.0-orchestration-foundation`（冻结 commit `38b4b69`），当前活跃阶段为 **Stage 15.99 — Run Lineage / Recovery Read Model 第一版**。当前实现仍只做文档、协议、schema、样例、检查链路与受控写入，**不接入真实执行链路**，也不会替代 [QwenPaw](https://github.com/agentscope-ai/QwenPaw)。QwenPaw 被视为未来可接入的宿主/适配器之一。

### 当前已实现能力

#### 基础检查与恢复
- `doctor`：校验项目结构、JSON/JSONL 语法、schema 兼容性和公开发布风险文本扫描。
- `docs context`：输出紧凑的项目上下文恢复摘要（里程碑、当前阶段、推荐阅读、下一步入口），优先消费 `docs/000-stage-digest.md`。
- `check text`：对文本/文件/stdin 做密钥模式扫描，命中后不回显完整匹配值。
- `check path`：对目标路径做只读、目录、扩展名等路径规则检查。
- `check action`：对 adapter + operation 做风险级别、command rule、publish rule 和 completion rule 判断。

#### Adapter Execution Envelope
- `adapter plan`：将 `check action` 的 preflight 结果包装成 adapter execution envelope 草案（包含 `adapter_request`、`approval_record`、`execution_event`），不执行真实适配器。
- `adapter validate` / `adapter inspect` / `adapter approval check` / `adapter response check` / `adapter gate check`：校验与聚合 adapter execution envelope 的只读状态。

#### Task Ledger 与 Runtime
- `task status` / `task events`：只读查询任务快照与事件流。
- `task validate`：对 task/event JSONL 逐行做 schema 校验。
- `task check-ledger`：检查 task 与 event ledger 之间的跨记录一致性。
- `runtime plan`：为指定 task 生成 adapter action 的只读草案摘要；`--draft-json` 输出完整但脱敏的 envelope 机器草案，已按 `adapters/execution-envelope.schema.json` 校验，不落盘。
- `runtime draft validate` / `runtime draft inspect`：只读校验和摘要展示 runtime plan envelope draft，支持项目内 JSON 文件或 stdin。
- `runtime draft export --dry-run` / `--commit`：dry-run 模拟导出 envelope 草案；`--commit` 将校验通过的草案写入 `drafts/runtime/.../*.json`（只允许新文件、禁止覆盖、写入失败自动回滚）。
- `runtime event append --dry-run` / `--commit`：dry-run 模拟追加单条 event；`--commit` 在 event ledger JSONL 末尾追加一行，追加后做 schema / ledger / runtime audit 校验，失败则按原始 byte size 回滚。
- `runtime event import --dry-run` / `--commit`：对批量候选 event 做只读预检或受控追加；`--commit` 把整批 event 作为一个连续 JSONL block 追加到现有 event ledger 尾部，失败按原始 byte size 回滚；支持 `--expected-plan-hash` 一致性冻结（advisory 模式）与 `--require-dry-run` strict freeze 模式。
- `runtime task create --dry-run` / `--commit`：dry-run 只读模拟创建新 task snapshot；`--commit` 只向 task ledger JSONL 追加一行，写后做 schema / ledger 校验，失败则按原始 byte size 回滚，不自动写 event ledger。
- `runtime gate check`：只读聚合 task ledger 与 adapter gate，输出是否可继续推进及建议 event draft（不落盘）。
- `runtime check-ledger`：只读审计 task/event ledger 与 adapter envelope 的跨系统一致性。
- `runtime report`：只读聚合 task 快照、事件流摘要、envelope 摘要、runtime gate 与 runtime ledger audit，输出统一报告。

#### 列表查询
- `agents list` / `adapters list` / `policies list`：只读列表查询，支持过滤、policy profile 选择和 JSON 输出。

#### Orchestration Hub（中枢台）
- `orchestration overview`：只读中枢台总览摘要，输出任务、run、审批、产物等聚合信息。
- `orchestration route preview`：只读能力路由预览，输出 capability -> adapter/operation 映射与风险降级建议。
- `orchestration preflight`：只读聚合 routing + guardrail preflight handoff 检查。
- `orchestration task submit --dry-run` / `--commit`：通过 orchestration 命名空间提交新 task；`--commit` 向 task ledger 追加 task 并可选追加 `created` event（A+B 受控写入，失败回滚）。
- `orchestration task list` / `orchestration task get`：只读任务列表与任务详情（含事件时间线）。
- `orchestration approval list` / `orchestration approval get`：只读 envelope 范围内的审批列表与详情。
- `orchestration approval resolve --commit`：受控追加一条 `approval_resolved` event 记录审批决议（只记录 decision，不执行原请求）。
- `orchestration artifact list` / `orchestration artifact get`：只读 envelope 范围内产物列表与详情。
- `orchestration report generate`：只读生成 orchestration 聚合报告。
- `orchestration run --dry-run` / `--commit`：中枢台 run 的只读 plan preview 或受控沉淀（A：envelope draft export + B：`run_planned` / `run_draft_exported` run lifecycle events append）；支持 `--expected-plan-hash` 冻结与 `--require-dry-run` strict freeze；不执行真实 adapter。
- `orchestration run list` / `orchestration run inspect`：只读 run 列表与 run 详情，支持 lineage 标识（retry / fallback）。

### 明确不做的（当前阶段）

- 不替代 QwenPaw，不做 UI 或桌面壳。
- 不启动长期后台服务，不接管定时任务。
- 不做模型代理或计费系统。
- 不静默执行真实外部操作（不发消息、不删文件、不 push、不访问网络、不执行真实 adapter）。
- 受控写操作仅限本项目内的 envelope draft 导出、event ledger 追加/批量导入、task ledger 追加、approval resolution event 追加与 run lifecycle event 追加，且需要显式 `--commit` 与严格校验/回滚。

---

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/` | Python 包，CLI 与核心检查逻辑 |
| `tests/` | pytest 测试 |
| `docs/` | 架构、路线图、协议说明、阶段文档（中文为主） |
| `policies/` | Policy schema 与样例 policy |
| `agents/` | Agent registry schema 与样例注册表 |
| `adapters/` | Adapter schema、execution envelope schema 与样例注册表 |
| `tasks/` | Task / event schema、样例 JSONL、进度与交接记录 |
| `cli/` | CLI 命令边界样例数据 |
| `tools/` | 公开扫描等独立只读工具脚本 |
| `drafts/` | 受控写入产物目录（运行时生成，按 task 分组） |
| `logs/` | 预留运行时日志目录（当前不写入） |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

### 关键源文件

#### 入口层
- `agent_runtime/__init__.py`：包入口，定义包版本。
- `agent_runtime/__main__.py`：支持 `python -m agent_runtime`。
- `agent_runtime/cli.py`：argparse 命令行入口与所有子命令调度。

#### 基础检查与支撑
- `agent_runtime/doctor.py`：`doctor` 命令实现，校验结构、schema、JSONL 和公开扫描。
- `agent_runtime/loader.py`：数据文件加载工具，含安全读取白名单/黑名单、policy 发现与加载、路径归一化。
- `agent_runtime/policy.py`：`check text` / `check path` / `check action` 的规则检查实现。
- `agent_runtime/policy_profile.py`：根据 `--agent` / `--assignee` 或 agent registry 的 `policy_profile` 字段自动选择 policy profile。
- `agent_runtime/result.py`：`Finding`、`CheckResult` 数据模型，输出格式化与退出码。

#### Task / Ledger
- `agent_runtime/tasks.py`：只读 task ledger 查询（快照、事件流、渲染）。
- `agent_runtime/task_validation.py`：task/event JSONL 写入前 schema 校验。
- `agent_runtime/ledger_consistency.py`：task 与 event JSONL 之间的跨记录一致性检查。

#### Adapter / Runtime
- `agent_runtime/adapter_plan.py`：生成 adapter execution envelope 草案。
- `agent_runtime/adapter_validation.py`：校验 adapter execution envelope JSON 文件。
- `agent_runtime/adapter_approval.py` / `adapter_response.py` / `adapter_gate.py`：只读检查 adapter approval、response 与 gate 状态。
- `agent_runtime/runtime_plan.py`：为指定 task 生成 adapter action 的只读草案摘要（含可选 approval/event 草案与完整 envelope draft）。
- `agent_runtime/runtime_draft.py`：只读校验与摘要 runtime plan envelope draft。
- `agent_runtime/runtime_draft_export.py`：envelope draft 的 dry-run 导出与受控 `--commit` 写入。
- `agent_runtime/runtime_event_append.py`：单条 event 的 dry-run 模拟与受控 `--commit` 追加。
- `agent_runtime/runtime_event_import.py`：批量 event 的 dry-run 模拟、受控 `--commit` 追加与一致性冻结。
- `agent_runtime/runtime_task_create.py`：新 task 的 `--dry-run` 模拟与受控 `--commit` 追加。
- `agent_runtime/runtime_gate.py`：只读聚合 task ledger 与 adapter envelope gate。
- `agent_runtime/runtime_ledger.py`：只读审计 task/event ledger 与 adapter envelope 的跨系统一致性。
- `agent_runtime/runtime_report.py`：只读聚合 task、event、envelope、gate、ledger audit 的统一报告。

#### Orchestration Hub（中枢台）
- `agent_runtime/docs_context.py`：项目文档上下文恢复摘要。
- `agent_runtime/orchestration_overview.py`：中枢台总览。
- `agent_runtime/orchestration_tasks.py`：orchestration 视角的任务列表/详情查询。
- `agent_runtime/orchestration_task_submit.py`：orchestration task 提交（dry-run / commit）。
- `agent_runtime/orchestration_route.py`：capability 路由预览。
- `agent_runtime/orchestration_preflight.py`：routing + guardrail preflight handoff。
- `agent_runtime/orchestration_approval.py` / `orchestration_approval_resolve.py`：审批列表/详情与审批决议 event 追加。
- `agent_runtime/orchestration_artifact.py`：产物列表/详情。
- `agent_runtime/orchestration_report.py`：orchestration 聚合报告生成。
- `agent_runtime/orchestration_run.py` / `orchestration_run_dry_run.py` / `orchestration_run_commit.py`：run dry-run preview 与 run commit 受控写入（A+B）。

#### 工具
- `tools/public_scan.py`：仓库公开发布风险文本扫描，只读、不回显完整命中值。

### 关键 Schema 与样例

- `policies/policy.schema.json`：policy JSON Schema。
- `policies/*.sample.policy.json`：样例 policy（s-black、wangcai、dabai）。
- `agents/agents.schema.json`：agent registry JSON Schema。
- `agents/agents.sample.json`：样例 agent 注册表。
- `adapters/adapter.schema.json`：adapter registry JSON Schema。
- `adapters/adapters.sample.json`：样例 adapter 注册表。
- `adapters/execution-envelope.schema.json`：adapter execution envelope artifact 集合 JSON Schema。
- `adapters/execution-envelope.examples.json`：envelope 样例。
- `tasks/task.schema.json`、`tasks/event.schema.json`：任务与事件 JSON Schema（event schema 已包含 `run_planned`、`run_draft_exported`、`run_blocked` 等 run lifecycle event types）。
- `tasks/*.jsonl`：任务与事件样例数据。

---

## 技术栈

- **语言**：Python 3.11+（已在 Python 3.11 与 3.12 环境验证）。
- **标准库**：`argparse`、`json`、`pathlib`、`re`、`sys`、`dataclasses`、`uuid`、`datetime`、`tempfile`、`hashlib` 等。
- **第三方依赖**：
  - `jsonschema>=4.0`：`doctor`、task/event schema 校验、adapter envelope 校验中使用。
  - `pytest>=8.0`：测试框架（开发依赖）。
- **构建配置**：`pyproject.toml`（setuptools 后端），定义包元数据、依赖、console script 与 pytest 默认参数。
- **无编译步骤**：纯 Python，无需编译。

---

## 构建与运行

### 环境要求

- Python 3.11 或更高版本。
- 推荐以可编辑模式安装包与开发依赖：

  ```bash
  pip install -e .[dev]
  ```

### 运行 CLI

三种入口等价：

```bash
python -m agent_runtime.cli <command>
python -m agent_runtime <command>
agent-runtime <command>
```

常用命令：

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli docs context
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check text --file README.md
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli check action --adapter github-cli --operation git_push --target origin/main
python -m agent_runtime.cli adapter plan --adapter github-cli --operation git_push --target origin/main
python -m agent_runtime.cli adapter validate --file adapters/execution-envelope.examples.json
python -m agent_runtime.cli adapter gate check --file adapters/execution-envelope.examples.json --request-id req-20260703-002
python -m agent_runtime.cli runtime plan --task-id task-20260703-001 --adapter github-cli --operation git_push --target origin/main
python -m agent_runtime.cli runtime plan --task-id task-20260703-001 --adapter github-cli --operation git_push --target origin/main --draft-json
python -m agent_runtime.cli runtime draft validate --file <envelope.json>
python -m agent_runtime.cli runtime draft inspect --file <envelope.json>
python -m agent_runtime.cli runtime draft export --output drafts/runtime/task-001/req-001.envelope.json --file <envelope.json> --dry-run
python -m agent_runtime.cli runtime draft export --output drafts/runtime/task-001/req-001.envelope.json --file <envelope.json> --commit
python -m agent_runtime.cli runtime event append --file <event.json> --dry-run
python -m agent_runtime.cli runtime event append --file <event.json> --commit
python -m agent_runtime.cli runtime event import --file <events.jsonl> --dry-run
python -m agent_runtime.cli runtime event import --file <events.jsonl> --commit
python -m agent_runtime.cli runtime event import --file <events.jsonl> --commit --expected-plan-hash sha256:...
python -m agent_runtime.cli runtime event import --file <events.jsonl> --commit --require-dry-run
python -m agent_runtime.cli runtime task create --file <task.json> --dry-run
python -m agent_runtime.cli runtime task create --file <task.json> --commit
python -m agent_runtime.cli runtime gate check --task-id task-20260703-001 --request-id req-20260703-002 --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli runtime check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli runtime report --task-id task-20260703-001 --request-id req-20260703-002 --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli task status task-20260703-001
python -m agent_runtime.cli task events task-20260703-001
python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task
python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl
python -m agent_runtime.cli agents list --capability planning
python -m agent_runtime.cli adapters list --kind github
python -m agent_runtime.cli policies list

# Orchestration Hub
python -m agent_runtime.cli orchestration overview
python -m agent_runtime.cli orchestration route preview --capability git_push
python -m agent_runtime.cli orchestration preflight --capability git_push --task-id task-20260703-001
python -m agent_runtime.cli orchestration task submit --file <task.json> --dry-run
python -m agent_runtime.cli orchestration task submit --file <task.json> --commit
python -m agent_runtime.cli orchestration task list
python -m agent_runtime.cli orchestration task get --task-id task-20260703-001
python -m agent_runtime.cli orchestration approval list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration approval get --envelope adapters/execution-envelope.examples.json --approval-id appr-20260703-001
python -m agent_runtime.cli orchestration approval resolve --approval-id appr-... --decision granted --by reviewer --commit
python -m agent_runtime.cli orchestration artifact list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration report generate --task-id task-20260703-001 --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration run --task-id task-20260703-001 --request-id req-20260709-001 --capability git_push --dry-run
python -m agent_runtime.cli orchestration run --task-id task-20260703-001 --request-id req-20260709-001 --capability git_push --commit
python -m agent_runtime.cli orchestration run --task-id task-20260703-001 --request-id req-20260709-001 --capability git_push --commit --expected-plan-hash sha256:...
python -m agent_runtime.cli orchestration run list --envelope adapters/execution-envelope.examples.json
python -m agent_runtime.cli orchestration run inspect --task-id task-20260703-001 --request-id req-20260703-002 --envelope adapters/execution-envelope.examples.json
```

全局参数：

| 参数 | 说明 |
|:---|:---|
| `--root <path>` | 项目根目录，默认当前目录 |
| `--policy <file>` | 显式指定 policy 文件，优先级最高 |
| `--policy-profile <name>` | 选择 policy profile：`s-black`、`wangcai`、`dabai` 或 `all` |
| `--agent <id>` / `--assignee <id>` | 按 agent registry 的 `policy_profile` 自动选择 policy profile |
| `--json` | 输出 JSON |
| `--no-color` | 禁用彩色输出（预留） |
| `--quiet` | 保留给后续精简输出使用 |
| `--verbose` | 保留给后续诊断输出使用 |

Policy profile 解析优先级：`--policy` > `--policy-profile` > `--agent` / `--assignee` > 默认 `all`。

### 退出码

| 码 | 含义 |
|:---:|:---|
| `0` | 通过或查询成功（含 `warn`） |
| `1` | CLI 使用错误或内部错误 |
| `2` | policy 阻断 / 路径阻断 |
| `3` | 需要用户授权 |
| `4` | 需要更多输入 |
| `5` | 校验失败 |

---

## 测试

### 运行全部测试

```bash
python -m pytest tests -q
```

当前测试覆盖：

- `tests/test_cli.py`：CLI 入口与主要命令行为。
- `tests/test_doctor.py`：`doctor` 校验通过/失败场景。
- `tests/test_policy_text.py`：密钥模式扫描、行号列号、不回显完整匹配。
- `tests/test_policy_path.py`：路径规则只读/目录/扩展名判断。
- `tests/test_policy_profile.py`：agent 到 policy profile 的自动映射。
- `tests/test_tasks.py`：task ledger 查询与渲染。
- `tests/test_task_validation.py`：task/event JSONL schema 校验。
- `tests/test_ledger_consistency.py`：task 与 event ledger 跨记录一致性。
- `tests/test_adapter_plan.py`：adapter execution envelope 草案生成。
- `tests/test_adapter_validate.py` / `test_adapter_inspect.py`：adapter execution envelope schema 校验与摘要。
- `tests/test_adapter_approval.py` / `test_adapter_response.py` / `test_adapter_gate.py`：adapter envelope 检查链路。
- `tests/test_runtime_gate.py`：runtime gate 只读聚合、输出脱敏与不写 ledger。
- `tests/test_runtime_ledger.py`：runtime ledger audit 跨系统一致性、输出脱敏与不写 ledger。
- `tests/test_runtime_plan.py`：runtime plan 摘要输出、`--draft-json` envelope 草案 schema 校验、终态/缺失 task 不输出 draft、脱敏与不写 ledger。
- `tests/test_runtime_draft.py`：runtime draft validate / inspect。
- `tests/test_runtime_draft_export.py` / `test_runtime_draft_export_commit.py`：dry-run 与 commit 导出、路径安全、禁止覆盖、自动回滚。
- `tests/test_runtime_event_append_dry_run.py` / `test_runtime_event_append_commit.py` / `test_runtime_event_append_report_loop.py`：event dry-run / commit、样本 ledger 保护、回滚、与 report 联动。
- `tests/test_runtime_event_import_dry_run.py` / `test_runtime_event_import_commit.py` / `test_runtime_event_import_freeze.py` / `test_runtime_event_import_strict_freeze.py`：批量 event import dry-run / commit、一致性冻结、strict freeze、回滚。
- `tests/test_runtime_task_create_dry_run.py` / `test_runtime_task_create_commit.py` / `test_runtime_task_create_smoke_loop.py`：task create dry-run / commit、ledger 一致性与 smoke loop。
- `tests/test_runtime_report.py`：runtime report 聚合与脱敏。
- `tests/test_public_scan.py`：仓库公开发布风险扫描。
- `tests/test_docs_context.py`：docs context 摘要与恢复入口。
- `tests/test_orchestration_overview.py` / `test_orchestration_route_preview.py` / `test_orchestration_preflight.py`：中枢台总览、路由预览与 preflight handoff。
- `tests/test_orchestration_task_submit.py` / `test_orchestration_task_list.py` / `test_orchestration_task_get.py`：orchestration task 提交与 read-model。
- `tests/test_orchestration_approval.py` / `test_orchestration_approval_resolve.py`：orchestration 审批列表/详情与审批决议受控写入。
- `tests/test_orchestration_artifact.py`：orchestration 产物 read-model。
- `tests/test_orchestration_report.py`：orchestration 报告生成。
- `tests/test_orchestration_run_dry_run.py` / `test_orchestration_run_commit.py` / `test_orchestration_run_inspect.py` / `test_orchestration_run_list.py`：run dry-run、commit、inspect、list 与 lineage。
- `tests/test_controlled_write_regression.py`：受控写命令（draft export、event append、event import、task create、orchestration task submit、orchestration run commit 等）的完整回归链路。

### 写测试的约定

- 使用 pytest。
- 测试中的 token/key 应当在内存中动态拼接（如 `"ghp_" + "X" * 36`），避免在源码里写入看起来像真实密钥的字符串。
- 断言检查状态码、输出中是否包含规则 id、以及敏感值是否**不**出现在输出中。
- 项目根目录常量：`ROOT = Path(__file__).resolve().parents[1]`。
- 受控写测试应使用临时目录或项目内 `drafts/` 等隔离路径，并在测试后清理；对 `runtime event append --commit` / `runtime event import --commit` / `runtime task create --commit` / `orchestration task submit --commit` / `orchestration run --commit` 的测试优先在临时 JSONL 或副本上执行。

---

## 持续集成与部署

项目使用 GitHub Actions 做持续集成，配置位于 `.github/workflows/ci.yml`。

在 `push` 或 `pull_request` 到 `main` 分支时，CI 会在 Python 3.11 与 3.12 上执行：

1. `pip install -e .[dev]`：可编辑安装包与开发依赖。
2. `python -m pytest`：运行全部测试。
3. `python -m agent_runtime.cli doctor`：运行 doctor 校验。
4. ledger CLI smoke checks：
   - `python -m agent_runtime.cli task validate --record-file tasks/tasks.jsonl --schema task`
   - `python -m agent_runtime.cli task validate --record-file tasks/events.jsonl --schema event`
   - `python -m agent_runtime.cli task check-ledger --tasks-file tasks/tasks.jsonl --events-file tasks/events.jsonl`
5. `python -m pytest tests/test_controlled_write_regression.py -q`：运行受控写回归测试。
6. `python tools/public_scan.py`：公开扫描。

当前阶段无生产部署流程；CLI 以本地可编辑安装方式运行。

---

## 代码组织与模块划分

CLI 采用分层设计：

1. **入口层**：`agent_runtime/cli.py` 负责 argparse 子命令解析、`main()` 异常兜底和结果输出调度。
2. **命令实现层**：
   - `doctor.py`：项目结构与 schema 校验。
   - `policy.py`：text / path / action 规则检查。
   - `adapter_plan.py` / `adapter_validation.py`：adapter execution envelope 草案与校验。
   - `tasks.py` / `task_validation.py` / `ledger_consistency.py`：task ledger 查询、写入前校验与一致性检查。
   - `runtime_*.py`：runtime gate、ledger audit、plan、draft、draft export、event append、event import、task create、report 等运行时检查与受控写模块。
   - `orchestration_*.py`：中枢台总览、任务提交/列表/详情、路由预览、preflight handoff、审批列表/详情/决议、产物列表/详情、报告生成、run dry-run/commit/list/inspect 等编排层模块。
3. **支撑层**：
   - `loader.py`：统一的数据加载、安全读取、policy 发现、路径归一化。
   - `policy_profile.py`：agent -> policy profile 解析。
   - `result.py`：统一的 `Finding`、`CheckResult` 模型与退出码映射。

各模块之间通过 `CheckResult` / `Finding` 传递结果，CLI 顶层统一调用 `emit()` 输出。核心检查链路保持只读；写操作集中在 `runtime_draft_export.py`（写新 draft JSON）、`runtime_event_append.py`（追加 event ledger 单行）、`runtime_event_import.py`（批量追加 event ledger）、`runtime_task_create.py`（追加 task ledger 单行）、`orchestration_task_submit.py`（task + created event 追加）、`orchestration_approval_resolve.py`（追加 approval_resolved event）与 `orchestration_run_commit.py`（A+B envelope draft export + run lifecycle events 追加），均有显式 `--commit` 开关、前置校验与失败回滚。

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
- 校验失败用 `CheckResult(status="validation_failed", ...)` 表达，对应退出码 `5`。
- 安全检查失败用 `Finding` 表达，而不是抛异常。
- 受控写操作失败优先回滚已写入内容，再返回 `error` 或 `validation_failed`。

### 不变的安全边界

- 不执行外部命令。
- 不访问网络。
- 不发送消息。
- 不删除文件（受控写模块仅回滚自己刚刚写入/追加的内容，不删除用户已有文件）。
- 不重写真实 task ledger；`runtime task create --commit` / `orchestration task submit --commit` 只允许向 task ledger JSONL 末尾追加一行，并在写后检查失败时回滚自己刚刚追加的内容。
- 不读取 `.env`、`.env.local`、`.envrc`、`.secret`、`.key`、`.pem`、`.p12`、`.pfx` 等密钥文件。
- `check text` 命中密钥后，只输出规则 id、位置、提示，不回显完整匹配值。

修改代码时应保持上述边界；若需突破，必须有显式设计文档和用户授权机制。

---

## 安全考虑

### 文件读取白名单

`agent_runtime/loader.py` 定义了 `is_safe_to_read()`，明确拒绝常见密钥/环境文件。公开扫描（doctor 的 public scan）只遍历以下后缀：

`.json`、`.jsonl`、`.md`、`.txt`、`.py`、`.sample`、`""`（无后缀）、`.yml`、`.yaml`。

同时跳过 `.git`、`__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`。

`tools/public_scan.py` additionally skips `node_modules`、`.venv`、`.tox`、`build`、`dist`，并扫描 `.toml`、`.cfg`、`.ini` 等配置文件。

### Secret 输出控制

- `Finding` 只包含 `rule_id`、`severity`、`action`、`message`、`line`、`column`。
- 扫描结果中不保存也不输出匹配到的完整 secret。
- 测试明确断言完整 token 不出现在 `render_json()` 和 `render_human()` 中。

### 高风险动作映射

- `path_rules` 中的 `readonly` 会在写/删操作时触发阻断。
- `command_rules` 通过正则匹配危险命令（如 `git push`、`rm -rf`、代理修改、强杀进程）。
- `publish_rules` 在外发类 operation（`gh_issue`、`gh_pr`、`git_push`、`lark_message`）前要求 secret scan、目标确认、用户授权等检查。
- `completion_rules` 在完成类 operation（`finish`、`mark_finished` 等）前要求 `required_evidence`。
- `check_action` 对 `risk_level == "external"` 或 `requires_approval == true` 的 adapter 返回 `NEEDS_APPROVAL`。

### Adapter Execution Envelope 安全

- `adapter plan` 只生成草案，不执行真实 adapter、不写 ledger、不访问网络。
- `adapter validate` 只校验 envelope JSON 结构，不回显 artifact 完整内容。
- envelope 中的 `approval_record` 与 `execution_event` 仅在 preflight 为 `needs_approval` 时生成，状态初始为 `pending`。

### 受控写边界（Controlled Write POC）

- `runtime draft export --commit` 仅写入新文件到 `drafts/runtime/.../*.json`；输出路径必须在项目根目录内、必须位于 `drafts/runtime/` 下、必须是 `.json`、不能覆盖已存在文件；写入前对内容进行 secret scan 与 public scan；写入后重新校验与 inspect，失败则删除文件回滚。
- `runtime event append --commit` 只追加单行到 event ledger JSONL；目标文件必须是安全 JSONL、必须已存在且以换行结尾、不能是样本 ledger（`tasks/examples.jsonl`、`tasks/events.examples.jsonl`）；追加后做 schema / ledger / runtime audit 校验，失败则按原始 byte size truncate 回滚。
- `runtime event import --commit` 只把整批 candidate event 作为连续 block 追加到已存在的 event ledger JSONL；目标文件安全规则与 event append 一致；追加后做 schema / ledger / runtime audit 校验，失败则按原始 byte size truncate 回滚；dry-run 输出 `plan_hash` 等一致性冻结元数据，commit 可选 `--expected-plan-hash` 在 preflight 前做计划哈希比对（advisory 模式），可选 `--require-dry-run` 进入 strict freeze 模式。
- `runtime task create --commit` 只追加单行到 task ledger JSONL；目标文件必须是安全 JSONL、父目录必须已存在、现有非空文件必须以换行结尾、不能是样本 ledger 或 git/credential 路径；追加后做 schema / ledger 校验，失败则按原始 byte size truncate 回滚；不会自动追加 event ledger。
- `orchestration task submit --commit` 在 A+B 模式下同时追加 task snapshot 与 `created` event；任一失败即按 byte size 回滚两个 ledger 的变更。
- `orchestration approval resolve --commit` 只追加一条 `approval_resolved` event 记录审批决议，不执行原请求。
- `orchestration run --commit` 采用 A+B 组合产物策略：先生成 envelope draft 文件（A），再追加 `run_planned` + `run_draft_exported` run lifecycle events（B）；all-or-nothing 回滚：若 A 失败不写 B，若 B 失败删除 A 并回滚 event ledger；支持 `--expected-plan-hash` 与 `--require-dry-run` freeze guard；commit 仍不执行真实 adapter。

---

## 设计文档索引

> **智能体新会话先读 `docs/000-stage-digest.md`，再按需下钻。**
> 文档维护规则见 `docs/MAINTENANCE.md`。

活跃文档详见 `docs/00-index.md`，核心入口：

| 入口 | 文件 |
|:---|:---|
| 最小上下文恢复 | `docs/000-stage-digest.md` |
| 文档导航地图 | `docs/00-index.md` |
| 愿景与边界 | `docs/01-vision-and-boundaries.md` |
| 路线图 | `docs/02-roadmap.md` |
| CLI 用法 | `docs/10-cli-poc-usage.md` |
| 受控写入边界 | `docs/21-controlled-write-boundaries.md` |
| 中枢台愿景 | `docs/47-orchestration-hub-vision.md` |
| Adapter Runtime Interface | `docs/48-adapter-runtime-interface.md` |
| Capability Routing Model | `docs/49-capability-routing-model.md` |
| Control Plane State Model | `docs/50-control-plane-state-model.md` |
| Backend-first API Boundary | `docs/51-backend-first-api-boundary.md` |
| 最小编排闭环 | `docs/52-minimal-orchestration-loop.md` |
| Orchestration 受控写入边界 | `docs/56-orchestration-controlled-write-boundary.md` |
| Run 受控执行设计 | `docs/58-orchestration-run-controlled-execution-design.md` |
| Run 生命周期事件设计 | `docs/60-orchestration-run-lifecycle-events-design.md` |
| Task Submit 受控写入设计 | `docs/62-orchestration-task-submit-controlled-write-design.md` |
| Retry / Fallback 设计 | `docs/66-orchestration-run-retry-fallback-design.md` |
| 版本治理 | `docs/64-versioning-governance.md` |
| 文档维护规则 | `docs/MAINTENANCE.md` |

历史阶段交付物已归档至 `docs/archive/`（release-notes / dry-runs / smoke-regression）。

进度与交接：

- `tasks/progress.md`：每日推进记录。
- `tasks/handoff-2026-07-02.md` 至 `tasks/handoff-2026-07-10-stage-digest-priority.md`：会话交接上下文。

架构决策：

- `decisions/0001-project-location.md`：项目独立位置决策。

---

## 给 Agent 的实战提示

1. **先跑 doctor**：做任何改动后，先执行 `python -m agent_runtime.cli doctor`，确认结构、schema 和公开扫描都通过。
2. **再跑测试**：执行 `python -m pytest tests -q`，确保没有回归。
3. **跑受控写回归**：执行 `python -m pytest tests/test_controlled_write_regression.py -q`，覆盖 draft export、event append、event import、task create、orchestration task submit、orchestration run commit 的写边界。
4. **跑公开扫描**：执行 `python tools/public_scan.py`，确保没有发布风险。
5. **不改只读边界**：除非任务明确要求并已有设计文档，否则不要让 CLI 执行外部命令、访问网络、发送消息或删除文件。
6. **受控写需显式 `--commit`**：`runtime draft export`、`runtime event append`、`runtime event import`、`runtime task create`、`orchestration task submit`、`orchestration approval resolve`、`orchestration run` 默认 dry-run；只有加 `--commit` 才会写文件，且写前会校验、写后会再次校验并回滚。
7. **敏感信息不进源码**：不要在代码、测试、样例 JSON 中硬编码真实密钥；测试用动态拼接的假 token。
8. **保持 schema 与实现同步**：修改 `policies/`、`agents/`、`adapters/`、`tasks/` 下的 schema 或样例后，检查对应 Python 代码是否需要调整。
9. **文档优先中文**：新增 README、docs、notes、handoff 等文档时优先使用中文。
10. **小步可审查**：每次变更保持聚焦，方便 Orchestrator 做安全与质量验收。
