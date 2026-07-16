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
2. `docs/93-codex-desktop-filtered-snapshot-display-host-integration-and-milestone-freeze.md`：Stage 39 host design gate 与 Stage 40/41 边界。
3. `docs/archive/92-filtered-snapshot-markdown-display-consumer-validation-gate.md`：Stage 36–38 与 v0.16.0 历史事实源。
4. `docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`：Stage 33–35 与 v0.15.0 历史事实源。
4. `docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`：Stage 30–32 与 v0.14.0 历史事实源。
5. `docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md`：Stage 29 stdin consumer。
6. `docs/87-filtered-envelope-snapshot-json-reader-implementation.md`：Stage 27 filtered v3 reader。
7. `tasks/handoff-2026-07-16.md`：Stage 39 收口事实与 Stage 40 条件实现边界。
8. `docs/88-filtered-snapshot-host-consumer-validation-gate.md`：Stage 28 consumer gate。
9. `docs/86-filtered-envelope-snapshot-read-design-gate.md`：Stage 26 filter contract。
10. `docs/84-envelope-scoped-snapshot-read-design-gate.md`：Stage 23/24 reader 边界。
11. `docs/83-codex-desktop-snapshot-json-reader-implementation.md`：Stage 22 reader。
12. `docs/79-read-only-host-consumer-validation-boundary.md`：Stage 18 consumer。
13. `docs/78-control-panel-host-integration-boundary.md`：Stage 17 handoff。
14. `docs/76-read-only-control-panel-mvp.md`：Stage 16 Control Panel。
15. `docs/75-cli-automation-contract-discovery.md`：CLI 自动化。
16. `docs/52-minimal-orchestration-loop.md`：Stage 14。
17. `docs/51-backend-first-api-boundary.md`：Stage 13。
18. `docs/02-roadmap.md`：完整路线图。
19. `docs/archive/release-notes/100-release-notes-stage39-filtered-snapshot-display-host-integration-gate.md`：Stage 39 验收。
20. `docs/archive/release-notes/99-release-notes-v0.16.0-filtered-snapshot-display-consumer.md`：v0.16.0 验收。
20. `docs/archive/release-notes/98-release-notes-stage37-filtered-snapshot-markdown-display-consumer.md`：Stage 37 验收。
21. `docs/archive/release-notes/97-release-notes-stage36-filtered-snapshot-markdown-display-consumer-validation-gate.md`：Stage 36 验收。
22. `docs/archive/release-notes/96-release-notes-v0.15.0-filtered-snapshot-display-integration.md`：v0.15.0 验收。
23. `docs/10-cli-poc-usage.md`：具体 CLI 参数。

不要先遍历整个 `docs/` 或 `tasks/progress.md`。

## 2. 项目定位与当前阶段

`s-black harness engineering`（Python 包名 `agent_runtime`）是一个轻量、可审计、可迁移的 Agent Runtime / Harness Orchestrator，逐步抽象规则门禁、任务账本、adapter envelope、能力路由和控制面 read model。

当前状态：**Stage 39 — Filtered Snapshot Markdown Display Consumer Host Integration Gate 已收口**；已冻结 fixed Stage 34 display → Stage 37 consumer 的 validation-before-release one-shot host contract。下一阶段为 **Stage 40 — Filtered Snapshot Markdown Display Consumer Host Integration Implementation（条件启动）**；通用 query、HTML/browser、live service、DB、auth、网络、文件 export 与 UI 写操作仍不开放。

- 冻结基线：`v0.16.0-filtered-snapshot-display-consumer`（本地 tag，未 push）；上一基线为 `v0.15.0-filtered-snapshot-display-integration` / `b1fa0b3`（已推送）。
- 当前已具备：source-backed adapter registry、约束路由与 decision trace、routing/read-loop snapshot、受控 run planning、retry/fallback lineage 写入与读取、recovery lineage aggregation、CLI automation contract/profile/workflow，以及 `orchestration control-panel snapshot/render/handoff` 的确定性 representation、版本化 stdio descriptor 与独立 reference consumer validation。
- Stage 12 已完成：routing/read-loop snapshot 与 recovery lineage read model 已冻结并通过验收。
- Stage 13 已完成：真实 CLI/read models 的 stable/preview/unavailable 边界已对账，并由契约测试冻结命令 surface 与关键 flag。
- 收口事实源：`docs/52-minimal-orchestration-loop.md`。Stage 14 已完成最小、可回放、可审计的本地编排闭环。
- Stage 18 事实源：`docs/79-read-only-host-consumer-validation-boundary.md` 与 `docs/archive/release-notes/82-release-notes-stage18-read-only-host-consumer-validation.md`。
- Stage 19 事实源：`docs/archive/80-codex-desktop-read-only-adapter-design-gate.md`；design gate 已冻结。
- Stage 20 历史事实源：`docs/archive/81-codex-desktop-read-only-adapter-implementation.md`；adapter 已收口。
- Stage 21 事实源：`docs/archive/82-read-only-representation-read-design-gate.md`；validation-only 已冻结，不得把 `ready` 解释为 representation read 或 execution 权限。
- Stage 22 事实源：`docs/83-codex-desktop-snapshot-json-reader-implementation.md`；无 envelope v1 保持兼容。
- Stage 23/24 事实源：`docs/84-envelope-scoped-snapshot-read-design-gate.md`；只接受 allowlist 内 project-relative envelope，不执行 descriptor argv，不接受 HTML/URL/任意路径。
- Stage 25 事实源：`docs/85-envelope-scoped-consumer-filter-design-gate.md`；冻结无 filter 单-envelope v2 与一次性内存展示边界，不开放 query/persistence/export。
- Stage 26 事实源：`docs/86-filtered-envelope-snapshot-read-design-gate.md`；v3 仅允许 task/request exact filter，filter 在 base snapshot 完整验证后作用于安全 summaries。
- Stage 27 事实源：`docs/87-filtered-envelope-snapshot-json-reader-implementation.md`；filtered v3 已按 TDD 实现并收口，无 filter v2 与无 envelope v1 保持兼容。
- Stage 28 事实源：`docs/88-filtered-snapshot-host-consumer-validation-gate.md`；只冻结 future consumer contract 与前置 reader 契约测试，不实现 consumer。
- Stage 29 事实源：`docs/89-codex-desktop-filtered-snapshot-consumer-implementation.md`；专用 consumer 已按 TDD 实现并收口，不修改 Stage 18 consumer 或 Stage 27 reader。
- Stage 30–32 事实源：`docs/archive/90-codex-desktop-filtered-snapshot-host-integration-and-milestone-freeze.md`；one-shot host 与已推送 v0.14.0 里程碑已冻结。
- Stage 33–35 事实源：`docs/archive/91-codex-desktop-filtered-snapshot-markdown-display-integration-and-milestone-freeze.md`；Markdown display 与已推送 v0.15.0 已冻结。
- Stage 36 事实源：`docs/92-filtered-snapshot-markdown-display-consumer-validation-gate.md`；只冻结 consumer contract，Stage 37 必须先 RED tests。

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
| `tools/` | 独立只读工具，如 `public_scan.py`、Stage 18 reference consumer 与 Stage 20 host adapter |
| `decisions/` | 架构决策记录 |

关键入口：

- `agent_runtime/cli.py`：argparse 与命令调度。
- `agent_runtime/loader.py`：安全读取、路径归一化、数据加载。
- `agent_runtime/result.py`：`Finding` / `CheckResult` 与退出码。
- `agent_runtime/orchestration_run.py`：run list/inspect read model。
- `agent_runtime/orchestration_control_panel.py`：Stage 16/17 确定性 snapshot、自包含静态 HTML renderer 与 stdio host handoff descriptor。
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
