# AGENTS.md

本文件是仓库内编码 Agent 的最小操作契约。项目文档以中文为主；不要把历史阶段流水继续堆回本文件。

## 快速恢复

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

依次阅读：

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. 当前任务直接相关的 1-2 份事实源
4. `tasks/handoff-2026-07-29-stage97.md`（仅需恢复下一阶段设计细节时）

不要先遍历整个 `docs/`、`docs/archive/` 或 `tasks/progress.md`。

## 当前能力与边界

项目是 Python 3.11+、中文图形界面优先目标的本地多智能体 Harness / Control Plane。长期产品目标事实源为 `docs/130-gui-first-external-agent-control-plane-target.md`；当前已验收事实源为 `docs/archive/146-stage96-controlled-mission-intake.md`，前序产品事实源为 `docs/archive/145-stage95-agent-deck-mission-workspace.md` 与 `docs/archive/144-stage94-agent-deck-pilot-acceptance.md`。Pi/OMP 已完成只读状态、单工作项受控执行、真实事件/结果产物、人工审阅、有限串行链路和 GUI 启动/最终决定验收；Agent Deck 已完成安全工作台、浏览器草案、真实任务队列与受控任务登记。

允许的真实执行仅有：

- Windows fixed Git status：固定 `git status --short --branch`；
- Windows fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`；
- single work item dispatch：一次性确认后，只向用户已打开、工具为空且会话空闲的 `pi-local` 或 `omp-local` 派发一个固定工作项；阶段 89 wrapper 只能在一次稳定启动确认下，按固定拓扑串行调用三次既有派发；每轮仍需即时状态、租约、审计和输出校验，失败立即停止，最终人工决定独立确认。

阶段 91/92 的 GUI 只能以两种精确结构化信封复用阶段 89 已有链路启动和最终决定。阶段 94–96 的 Agent Deck 前端继续只消费安全 read model；浏览器草案不写入，`agent-deck mission submit` 只经 CLI 显式 `--commit` 复用既有 task + created-event 事务登记任务，且不启动 Agent。阶段 97 仅是待设计的受限主控规划提议；不得新增真实 operation、通用命令入口或前端派发。

三者都必须显式 `--commit`，并保持 lease、固定输入、审计和输出约束。进程类操作继续使用 Windows 进程树回收；单工作项派发不得启动宿主、接受任意 argv/cwd/env、开放 Agent 工具、自动重试或并行。成功结果可归档为 `.runtime/` 内不可变证据并接受一次人工“通过/要求修改”审阅；证据恢复不得重新调用 Agent，审阅不得自动触发执行。除非用户另行授权且先完成独立设计，禁止新增其他 operation、通用 shell、POSIX fallback、网络 adapter、长期服务或数据库。

MUST：

- 不读取或回显 `.env`、token、keyring、私钥等凭据；
- secret scan 只释放规则 id 和安全提示；
- 写前校验、写后校验、失败回滚；
- 保持 path containment、bounded input/output 和 fail-closed；
- 真实执行必须先写 started audit，结束后写唯一 terminal audit；
- 修改共享执行边界时运行全量测试和对应回归。

NEVER：

- 用任意 argv/cwd/env override 绕过 fixed operation；
- 把 preview/read model 解释为执行权限；
- 覆盖已有 ledger 或放宽 reserved audit event writer；
- 静默扩大网络、文件写入或宿主权限；
- 删除历史文档；已完成内容用 `git mv` 归档。

## 开发约定

- 优先标准库和现有 helper；最小 diff，不做无关重构。
- 所有 CLI 入口必须支持确定性 JSON 输出和稳定 failure code。
- MUST：用户实际看见、点击或操作的 UI/UX 默认使用简体中文。专业术语、协议名、Agent 名称或 Socket ID 无法合理翻译时，可以保留原文，但必须紧邻中文名称或中文解释；后台服务、代码、协议、日志和机器接口可默认使用英文，不要求为不可见内部实现强制中文化。
- 新增非平凡逻辑必须有 pytest。
- 修改受控写入或执行链时，先读对应模块和测试，保持现有事务与审计语义。
- `.runtime/` 是机器本地、gitignored 运行态，不得提交凭据或 smoke 原文。

常用入口：

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/cli.py` | CLI 入口 |
| `agent_runtime/orchestration_contract.py` | 对外能力清单 |
| `agent_runtime/orchestration_external_agent_live_status.py` | 固定外部 Agent snapshot 只读 reader |
| `agent_runtime/execution_*` | lease、trust、audit 与执行基础设施 |
| `agent_runtime/orchestration_*_execution.py` | 固定 operation 编排 |
| `agent_runtime/external_agent_evidence_store.py` | 不可变证据、pending 恢复和审阅记录存储 |
| `agent_runtime/orchestration_external_agent_evidence.py` | 真实证据读取与固定恢复 |
| `agent_runtime/orchestration_external_agent_review.py` | 人工审阅预览与一次性提交 |
| `tests/` | 行为与边界契约 |
| `docs/10-cli-poc-usage.md` | CLI 参考 |
| `docs/21-controlled-write-boundaries.md` | 写入边界 |
| `docs/130-gui-first-external-agent-control-plane-target.md` | 长期产品目标、MVP 边界与反偏航检查 |
| `docs/111-pi-controlled-dry-run-print-implementation.md` | 固定 Pi print 执行事实源 |
| `docs/archive/135-stage86-pi-omp-live-status-integration.md` | Pi/OMP 只读状态接入归档事实源 |
| `docs/archive/136-stage87-single-work-item-controlled-execution.md` | Pi/OMP 单工作项受控执行归档事实源 |
| `docs/archive/146-stage96-controlled-mission-intake.md` | 受控正式任务登记、等待主控规划收件箱与安全投影事实源 |
| `docs/archive/145-stage95-agent-deck-mission-workspace.md` | 浏览器草案、协作建议与真实安全任务队列事实源 |
| `docs/archive/144-stage94-agent-deck-pilot-acceptance.md` | Agent Deck P0 与真实 Pi/OMP 试运行验收事实源 |
| `docs/archive/138-stage89-bounded-planner-executor-review-design.md` | 有限 Pi/OMP 串行协作链路事实源 |

## 验证契约

代码或 schema 变更至少运行：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

受控写入变更额外运行：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

文档变更检查索引、相对链接和 `docs/` 活跃文档数；Git Bash 可运行：

```bash
bash .githooks/pre-commit
```

测试、smoke 或外部发布未实际成功时，不得声称完成。commit/push 需要用户本次明确授权。

## 文档治理

- `README*`：面向使用者，只保留当前状态、边界、快速开始和入口。
- `AGENTS.md`：只保留操作契约，不记录逐 Stage 历史。
- `docs/000-stage-digest.md`：单屏恢复当前断点。
- `docs/00-index.md`：按主题导航，不逐文件写摘要。
- `docs/02-roadmap.md`：只列能力包和下一候选。
- 已完成设计、实施计划、smoke 与旧长版入口归档到 `docs/archive/`；完整历史仍可由 Git 与 archive 追溯。
