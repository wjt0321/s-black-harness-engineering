# 阶段 97 恢复包：受限主控 Agent 结构化规划提议

> 状态：下一阶段设计入口；尚未授权实施。
> 基线：阶段 96 已完成并推送，提交 `2f88f8d`；当前分支以 `main` 为准。
> 最近事实源：`docs/archive/146-stage96-controlled-mission-intake.md`。

## 先读什么

1. `docs/000-stage-digest.md`；
2. `docs/00-index.md`；
3. `docs/130-gui-first-external-agent-control-plane-target.md`；
4. `docs/archive/146-stage96-controlled-mission-intake.md`；
5. `docs/archive/138-stage89-bounded-planner-executor-review-design.md`；
6. 本文件。

然后运行：

```powershell
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
git status --short --branch
```

## 当前已完成状态

- Agent Deck 前端已提供项目、团队、协作、结果、浏览器草案和真实任务队列的安全展示；
- `agent-deck mission submit --dry-run|--commit --goal <text>` 已可将有界目标安全写入既有 task + created event 事务；
- 登记任务固定标记为 `source=agent-deck`、`created_by=agent-deck-user`、`status=planned`、`current_step=等待主控 Agent 规划`；
- 该登记**不启动** Pi、OMP、主控 Agent、宿主或协作链路；React 也没有写入/派发桥接；
- Pi/OMP 既有 `Pi → OMP → Pi` 链路、证据、审阅和最终人工决定仍保持为唯一真实协作执行路径。

## 阶段 97 的目标

让一项已登记、等待规划的任务得到一份 **结构化、可验证、可审阅的主控规划提议**，并在用户确认后才可能映射到既有受控链路。

这个阶段的完成条件不是“自动干活”，而是回答清楚：主控 Agent 提出了什么计划、依据哪个登记任务、为何可进入人工确认、失败时如何停止。

## 必须先冻结的设计问题

1. **资格**：哪些任务有资格请求规划；如何防止重复规划、过期规划或已完成任务重新进入入口。
2. **输入**：Planner 只可读取任务的哪些已扫描字段；禁止将账本摘要、证据、路径或任意原文直接拼入提示。
3. **Agent 与运行**：使用哪个已接入 adapter；必须无工具、无 shell、无任意 argv/cwd/env；不得把 Pi print 的原始输出直接当控制面事实。
4. **输出**：固定 JSON schema、字段白名单、字节/行数上限、敏感信息扫描、角色/依赖/验收项校验和安全摘要。
5. **存储与审计**：规划提议应如何不可变保存、绑定任务/输入摘要/attempt、允许何种恢复，以及如何避免覆盖既有提议。
6. **确认门**：用户如何看到计划摘要、选择确认或拒绝；确认后怎样精确映射到既有 collaboration plan 与 Pi/OMP 受控链路。
7. **失败关闭**：无效 JSON、secret scan、状态漂移、未闭合审计、证据写入失败、确认摘要漂移或主机不可用时都必须停止，且不自动重试。
8. **前端边界**：网页只展示安全 read model 和受限确认信息；本阶段不得顺带引入通用 IPC、服务、任意命令或直接派发。

## 必须复用

- `agent_runtime/agent_deck_mission_intake.py`：登记任务身份、固定来源与输入边界；
- `agent_runtime/agent_deck_projection.py`：安全 read model；
- `agent_runtime/orchestration_collaboration.py` 与 `adapters/collaboration-plan.schema.json`：结构化协作计划；
- `agent_runtime/orchestration_pi_print_execution.py`：固定 Pi 运行约束；
- `agent_runtime/orchestration_single_work_item_execution.py`：单工作项、lease 和审计；
- `agent_runtime/external_agent_evidence_store.py` 与 `agent_runtime/orchestration_external_agent_review.py`：不可变证据、恢复和人工决定。

## 明确禁止

- 不要从浏览器草案直接运行 Agent；
- 不要新增通用 shell、任意 argv/cwd/env、网络 adapter、常驻服务、数据库或自由 IPC；
- 不要启动、关闭或重启宿主，不要开启 Agent 工具；
- 不要自动批准、自动执行、自动重试、并行派发、运行中取消或自治循环；
- 不要伪造 Codex、Claude、Kimi 的状态或能力；
- 不要读取或回显凭据、`.env`、keyring、私钥或未扫描原文。

## 设计验收门

在写实现前至少形成一份归档设计，明确：对象 schema、每一次写入、审计生命周期、read model、确认交互、失败矩阵、单元/集成/真实验收策略和回滚/恢复语义。设计得到授权后才进入实现。
