# AGENTS.md

本文件是 AI 编码 Agent 的**最小工作说明**。不要把它当完整项目文档；需要细节时按文末的权威入口下钻。

项目文档以中文为主，新增文档优先使用中文。

## 1. 新会话快速恢复

进入仓库后依次执行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

然后按顺序阅读：

1. `docs/000-stage-digest.md`：当前阶段、基线、下一步。
2. `docs/77-read-only-control-plane-milestone-freeze.md`：`v0.13.0` 里程碑冻结事实源。
3. `tasks/handoff-2026-07-14.md`：Stage 16 / v0.13.0 收口与下一轮恢复上下文。
4. `docs/76-read-only-control-panel-mvp.md`：Stage 16 静态只读 Control Panel 设计事实源。
5. `docs/75-cli-automation-contract-discovery.md`：已收口 CLI 自动化事实源。
6. `docs/52-minimal-orchestration-loop.md`：Stage 14 收口设计事实源。
7. `docs/51-backend-first-api-boundary.md`：Stage 13 已冻结的资源/操作边界。
8. `docs/02-roadmap.md`：需要更完整路线图时再读。
9. `docs/archive/release-notes/80-release-notes-v0.13.0-read-only-control-plane.md`：v0.13.0 里程碑验收事实。
10. `docs/archive/release-notes/79-release-notes-stage16-read-only-control-panel.md`：Stage 16 MVP 验收事实。
11. `docs/archive/release-notes/78-release-notes-cli-automation-consumer.md`：CLI 自动化消费者验收事实。
12. `docs/10-cli-poc-usage.md`：需要具体 CLI 参数时再查。

不要先遍历整个 `docs/` 或 `tasks/progress.md`。

## 2. 项目定位与当前阶段

`s-black harness engineering`（Python 包名 `agent_runtime`）是一个轻量、可审计、可迁移的 Agent Runtime / Harness Orchestrator，逐步抽象规则门禁、任务账本、adapter envelope、能力路由和控制面 read model。

当前状态：**Stage 16 — Read-only Control Panel MVP 已收口**；Stage 13–16 已统一冻结为 `v0.13.0-read-only-control-plane`。本地静态控制面已复用现有 read models 落地，后续 live service、DB、auth、网络与 UI 写操作仍不自动启动。

- 冻结基线：`v0.13.0-read-only-control-plane`；上一基线为 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`。
- 当前已具备：source-backed adapter registry、约束路由与 decision trace、routing/read-loop snapshot、受控 run planning、retry/fallback lineage 写入与读取、recovery lineage aggregation、CLI automation contract/profile/workflow，以及 `orchestration control-panel snapshot/render` 的确定性 snapshot 与自包含静态 HTML。
- Stage 12 已完成：routing/read-loop snapshot 与 recovery lineage read model 已冻结并通过验收。
- Stage 13 已完成：真实 CLI/read models 的 stable/preview/unavailable 边界已对账，并由契约测试冻结命令 surface 与关键 flag。
- 收口事实源：`docs/52-minimal-orchestration-loop.md`。Stage 14 已完成最小、可回放、可审计的本地编排闭环。

项目**不替代 QwenPaw**；QwenPaw 只是未来可能接入的宿主/adapter 之一。

## 3. 不可突破的边界

除非用户明确授权且已有设计文档，否则项目代码不得：

- 执行真实外部 adapter 或外部命令。
- 访问网络、发送消息或启动长期后台服务。
- 读取 `.env`、credential、token、keyring、`.key`、`.pem`、`.p12`、`.pfx` 等敏感文件。
- 静默扩大写入范围，覆盖用户已有文件，或重写真实 ledger。
- 引入 UI、service、DB、模型代理或计费系统。

Secret 扫描命中后只输出规则 id、位置和提示，不能回显完整匹配值。

Snapshot 是 ephemeral read model：不持久化、不伪造持久 Run/Event/Report；`--snapshot` 和 `--routing-snapshot-id` 只用于 dry-run preview。

### 受控写入

现有写操作必须显式使用 `--commit`，并保持“写前校验、写后校验、失败回滚”：

- envelope draft：只创建新文件，禁止覆盖。
- event/task ledger：只允许尾部追加，失败按原始 byte size 回滚。
- task submit：task + `created` event 为 A+B 原子写入。
- approval resolve：只记录 decision，不执行原请求。
- run commit：envelope draft + lifecycle events 为 A+B；仍不执行真实 adapter。

实现集中在 `runtime_*`、`orchestration_task_submit.py`、`orchestration_approval_resolve.py`、`orchestration_run_commit.py`。修改这些模块时必须运行受控写回归测试。

## 4. 技术栈与常用命令

- Python 3.11+，纯 Python，无编译步骤。
- 运行依赖：`jsonschema>=4.0`。
- 开发依赖：`pytest>=8.0`。
- 构建配置：`pyproject.toml`（setuptools）。

安装：

```bash
pip install -e .[dev]
```

CLI 三种入口等价：

```bash
python -m agent_runtime.cli <command>
python -m agent_runtime <command>
agent-runtime <command>
```

完整参数和示例只维护在 `docs/10-cli-poc-usage.md`，不要复制到本文件。

## 5. 提交前验证

任何代码或 schema 变更至少运行：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
```

涉及受控写入时额外运行：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

涉及文档时运行：

```bash
bash .githooks/pre-commit
```

Windows 可使用 Git for Windows 的 `bash.exe`。提交前还应运行 `git diff --check`。

不要在测试未通过时声称完成，也不要用局部测试替代全量回归。

## 6. 仓库地图

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/` | Python 包、CLI 和核心逻辑 |
| `tests/` | pytest 测试 |
| `docs/` | 活跃架构、设计和使用文档 |
| `docs/archive/` | release notes、dry-run、smoke/regression 历史记录 |
| `policies/` | policy schema 与样例 |
| `agents/` | agent registry schema 与样例 |
| `adapters/` | adapter registry、execution envelope schema 与样例 |
| `automation/` | Automation Profile schema 与 source-backed 样例 registry |
| `tasks/` | task/event schema、JSONL ledger、progress 与 handoff |
| `drafts/` | 受控生成的 runtime draft |
| `tools/` | 独立只读工具，如 `public_scan.py` |
| `decisions/` | 架构决策记录 |

关键入口：

- `agent_runtime/cli.py`：argparse 与命令调度。
- `agent_runtime/loader.py`：安全读取、路径归一化、数据加载。
- `agent_runtime/result.py`：`Finding` / `CheckResult` 与退出码。
- `agent_runtime/orchestration_run.py`：run list/inspect read model。
- `agent_runtime/orchestration_control_panel.py`：Stage 16 确定性 snapshot 与自包含静态 HTML renderer。
- `agent_runtime/orchestration_recovery.py`：recovery lineage aggregation。
- `agent_runtime/orchestration_workflow.py`：Automation Profile 到未执行 CLI 候选步骤的确定性投影。
- `agent_runtime/orchestration_workflow_check.py`：reviewed plan id 与当前 projection 的只读 drift validation。
- `agent_runtime/orchestration_run_dry_run.py` / `orchestration_run_commit.py`：run preview 与受控写入。
- `tasks/task.schema.json` / `tasks/event.schema.json`：ledger schema。
- `adapters/adapters.sample.json`：adapter/capability/risk 的 source of truth。

其余模块按功能命名，先搜索现有实现，不要创建重复管线。

## 7. 代码约定

- 使用 `from __future__ import annotations`。
- 导入顺序：future → 标准库 → 第三方 → 本项目相对导入。
- 函数签名使用类型提示，优先 `Path` 和 `|` 联合类型。
- 路径使用 `pathlib.Path`；跨平台比较使用 `loader.normalize_path()`。
- 核心结果通过 `CheckResult` / `Finding` 或明确 dataclass 表达，CLI 顶层统一输出。
- 校验失败优先返回结构化状态，不用异常表达正常门禁结果。
- 写操作失败必须先回滚本次写入，再返回错误。
- read model 必须确定性、脱敏、无副作用；不要依赖随机数或当前时间生成内容寻址结果。
- 默认输出兼容是硬约束；新字段或新视图优先使用显式 flag。

## 8. 测试约定

- 使用 pytest；项目根目录常量通常为：

  ```python
  ROOT = Path(__file__).resolve().parents[1]
  ```

- 测试 token/key 在运行时动态拼接，源码中不要出现看似真实的完整 secret。
- 断言不仅检查状态码，还要检查 rule id、结构化字段和敏感值**未出现**。
- 受控写测试使用临时目录或 ledger 副本，不直接修改仓库样例 ledger。
- 新行为遵循 TDD：先写失败测试并确认失败原因正确，再写最小实现。
- recovery lineage 相关改动至少覆盖 normal、retry、fallback、branch、missing/cross-task parent、cycle、duplicate conflict、determinism、no-write，以及 inspect/report 跨入口契约一致性。

CI 在 Python 3.11/3.12 上运行全量测试、doctor、ledger smoke checks、受控写回归和 public scan。

## 9. 文档维护

文档规则见 `docs/MAINTENANCE.md`。核心要求：

- `docs/000-stage-digest.md` 是新会话第一入口，阶段切换或重大进展时更新。
- 新活跃文档使用当前最大编号 +1，并加入 `docs/00-index.md`。
- release notes、dry-run、smoke/regression 完成后进入 `docs/archive/`。
- 能写入现有权威设计文档时，不新增重复文档。
- `tasks/progress.md` 保存历史流水；最新下一步以 stage digest 和最新 handoff 为准。

## 10. Agent 工作原则

1. 先恢复上下文，再改代码。
2. 先复用现有模块和 schema，再考虑新增抽象。
3. 保持小步、可审查、可回滚。
4. 不越过安全边界来“让测试通过”。
5. 完成前提供全量验证证据。
6. 未经明确要求，不 push、不创建 tag、不执行真实外部操作。
