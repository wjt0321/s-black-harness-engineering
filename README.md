# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

一个可审计的多 Agent 协作主控台。Kimi Code、Claude Code、OMP/Pi 和 QwenPaw Agent 是可替换的“插头”；项目提供统一“插座”、任务拆分、能力路由、交接、审阅、证据和操作边界，让用户最终能在一个看板里观察和控制它们协作。

最终形态是 GUI-first、本地优先的外部 Agent 控制面，而不是另一个聊天 Agent 或以 CLI/TUI 为主的工具。Harness 统一管理计划、状态、审批、交接、审阅、产物、审计和恢复；Claude、Kimi、OMP/Pi、QwenPaw 等外部 Agent 继续负责各自的模型、session 和工具执行。

## 当前状态

项目已完成并归档阶段 96；产品主线为聚合式 Agent 工作台（Agent Deck），已交付 P0 安全工作台、真实 Pi/OMP 试运行、任务草案/真实任务队列工作区，以及受控正式任务登记收件箱；现有 Harness 作为可信底层。当前具备：

- 统一 Agent socket registry、capability routing 与显式角色绑定；
- 可校验的多 Agent collaboration plan，包含 work item、依赖、handoff、artifact 和 review gate；
- 中文优先的 Control Panel、人工协作 fixture、工作项泳道和 handoff/artifact 时间线；
- 浏览器内存人工计划编辑器，以及结构、依赖、Agent 插座绑定和审阅要求校验；
- `editing -> validated -> operator_confirmed` 人工确认状态机；
- 用户主动复制或下载符合 collaboration plan v1 的候选 JSON；
- fixture-backed 协作运行状态、连续事件重放、工作项重试、审阅、交接、阻塞恢复与产物回收；
- checkpoint 操作资格、fixture 审批精确绑定和不可执行的幂等命令候选；
- 只聚合最新 attempt/review/handoff 的当前操作者待办、pending approval 集合与稳定 stale target 阻止原因；
- 中文 Control Panel 运行/操作资格/当前待办投影及固定禁用的操作者控件；
- 单 work item dispatch proposal、ACP readiness evidence 基础和完整审计边界；
- transport-neutral 的 External Agent adapter contract、25 项 failure matrix，以及有界的 GUI live read model fixture；
- `omp-acp` 首个只读实时状态读取器：固定原子快照、15 秒有效期、有界稳定读取、严格身份/生产者绑定、归一化证据与失败关闭界面映射；
- Pi/OMP 项目级进程内状态扩展、单写者租约、5 秒心跳、原子替换，以及中文控制面板“外部智能体 / 实时状态”区段；
- 一次性确认后的单工作项受控派发：只面向用户已打开、工具为空且空闲的 Pi/OMP，会回收有界结果并闭合审计；
- 固定真实宿主事件、不可变最终文本/JSON 产物、pending 固定恢复，以及人工“通过/要求修改”审阅和中文控制面板投影；
- 一次启动授权后的有限 `Pi → OMP → Pi` 或反向自动串行闭环，最终业务决定仍独立由人工确认；
- 前台中文 GUI 的已登记启动入口：不暴露链路 ID、任务 ID、协作计划或目标；中间自动串行完成后自动路由到最终“通过 / 要求修改”决定；
- 固定只读的已登记工作收件箱：从多张安全工作卡选择启动范围，不开放自由任务输入；正向与反向真实 Pi/OMP 链路均已完成。
- 受控 Agent Deck 任务登记：有界自然语言目标可经显式 `--commit` 写入既有任务账本并显示“等待主控 Agent 规划”；这不会启动任何 Agent 或执行链路。

Harness 仍不会启动、关闭或重启 Kimi、Claude、Pi 或 OMP。阶段 92 已于 2026-07-28 完成真实 GUI 验收：操作者只选择已登记工作卡、作一次启动确认与最终“通过 / 要求修改”决定；真实 `Pi → OMP → Pi` 和 `OMP → Pi → OMP` 自动串行均完成并以 `approved` 终态收束。活动工具非空、宿主忙碌、状态漂移、事件链无效、结果不安全或审阅绑定漂移时都会失败关闭。

当前有三项受限真实能力：fixed Git status、fixed Pi print，以及 Pi/OMP 单工作项派发（由阶段 89 有限 wrapper 和阶段 91 已登记 GUI 入口复用）。三者都需要显式提交、固定输入、machine-local lease 和执行审计；进程类操作继续使用 Windows Job Object 回收。GUI 不新增 operation 或通用命令；单工作项派发不开放任意命令或 Agent 工具；证据恢复和人工审阅不会自动调用 Agent。

## 安全边界

当前仍然不提供：

- 通用 shell 或任意 adapter execution；
- POSIX 真实执行；
- 网络适配器、长期服务、数据库或自动后台任务；
- Pi read/write/edit/bash 工具授权；
- 静默读取 `.env`、token、keyring 或其他凭据文件；
- 未经设计和授权的其他真实操作；
- 由 Harness 启动、关闭或重启外部智能体；
- 未经一次性确认的派发、多个工作项、自动重试、并行派发或自治循环；
- 任意项目文件产物回收、自动审阅、自动修改后重试或自动跨 Agent 转发。

## 快速开始

```bash
pip install -e .[dev]
python -m agent_runtime.cli doctor
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli --help
```

常用验证：

```bash
python -m pytest tests -q
python tools/public_scan.py
python -m agent_runtime.cli doctor
git diff --check
```

当前 CLI 恢复、登记和验证入口见 [`docs/10-cli-poc-usage.md`](docs/10-cli-poc-usage.md)；历史完整命令册已归档。

## 文档入口

- [`docs/000-stage-digest.md`](docs/000-stage-digest.md)：当前状态和恢复顺序。
- [`tasks/handoff-2026-07-29-stage97.md`](tasks/handoff-2026-07-29-stage97.md)：下一阶段的唯一恢复包、设计问题与停止线。
- [`docs/archive/147-documentation-consolidation-2026-07-29.md`](docs/archive/147-documentation-consolidation-2026-07-29.md)：文档收敛、归档和上下文治理记录。
- [`docs/archive/146-stage96-controlled-mission-intake.md`](docs/archive/146-stage96-controlled-mission-intake.md)：受控正式任务登记、规划收件箱和安全看板投影的验收事实源。
- [`docs/archive/145-stage95-agent-deck-mission-workspace.md`](docs/archive/145-stage95-agent-deck-mission-workspace.md)：任务草案、协作建议与真实安全任务队列的验收事实源。
- [`docs/archive/144-stage94-agent-deck-pilot-acceptance.md`](docs/archive/144-stage94-agent-deck-pilot-acceptance.md)：Agent Deck P0、真实 Pi/OMP 试运行与最终人工通过的验收事实源。
- [`docs/130-gui-first-external-agent-control-plane-target.md`](docs/130-gui-first-external-agent-control-plane-target.md)：GUI-first 外部 Agent 控制面长期目标、MVP 边界和反偏航检查表。
- [`docs/archive/140-stage91-gui-structured-approval-inbox.md`](docs/archive/140-stage91-gui-structured-approval-inbox.md)：阶段 91 归档事实源，记录无内部标识符输入的 GUI 启动、真实自动串行与最终决定验收。
- [`docs/archive/139-stage90-live-chinese-control-panel-read-model.md`](docs/archive/139-stage90-live-chinese-control-panel-read-model.md)：阶段 90 归档事实源，记录实时中文控制面读取模型与 GUI 验收。
- [`docs/archive/137-stage88-external-agent-evidence-and-human-review.md`](docs/archive/137-stage88-external-agent-evidence-and-human-review.md)：阶段 88 归档事实源，记录真实事件、不可变产物、固定恢复与人工审阅。
- [`docs/archive/136-stage87-single-work-item-controlled-execution.md`](docs/archive/136-stage87-single-work-item-controlled-execution.md)：阶段 87 归档事实源，记录 Pi/OMP 单工作项受控执行与真实验收。
- [`docs/archive/135-stage86-pi-omp-live-status-integration.md`](docs/archive/135-stage86-pi-omp-live-status-integration.md)：阶段 86 归档事实源，记录 Pi/OMP 真实只读状态接入。
- [`docs/00-index.md`](docs/00-index.md)：按主题导航。
- [`docs/02-roadmap.md`](docs/02-roadmap.md)：已完成能力包与下一候选。
- [`docs/111-pi-controlled-dry-run-print-implementation.md`](docs/111-pi-controlled-dry-run-print-implementation.md)：当前最新真实执行事实源。
- [`docs/113-pi-runtime-binding-implementation.md`](docs/113-pi-runtime-binding-implementation.md)：当前 binding-only review evidence 事实源；不代表 runner migration 或执行授权。
- [`docs/archive/`](docs/archive/)：完整历史设计、计划、smoke 与 release notes。

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/` | Python 包、CLI 和控制面逻辑 |
| `tests/` | pytest 测试 |
| `docs/` | 当前架构、规范与使用入口 |
| `docs/archive/` | 已完成阶段和历史快照 |
| `adapters/` / `agents/` / `policies/` | 示例注册表与规则 |
| `tasks/` | 示例 ledger、handoff 与推进记录 |
| `integrations/` | 宿主集成示例 |

版本和阶段治理见 [`docs/64-versioning-governance.md`](docs/64-versioning-governance.md)。
