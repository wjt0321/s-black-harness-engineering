# 02 — 路线图

## 路线图说明

`s-black harness engineering` 是一个长期项目。

它的最终目标不是单做“规则门禁”，而是建设一个面向多 Agent、多工具、多渠道的**中枢运行台（Orchestration Hub / Control Plane）**。当前已经做出来的 policy、ledger、controlled write、freeze、verification 等能力，属于这个中枢台的**安全与审计内核**。

因此后续路线图分为两条并行主线：

- **主线 A：安全与审计内核**
- **主线 B：中枢台接入与编排**

两条主线并行推进，但优先级上仍遵循：先把底层边界和状态模型打稳，再逐步放开接入、编排和未来 UI 可操作性。

---

## Stage 0 — 项目骨架（已完成）

目标：建立稳定的项目根目录、基础说明文件和长期推进账本。

已交付：

- `README.md`
- `README.en.md`
- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `tasks/progress.md`
- `decisions/0001-project-location.md`

结果：仓库骨架、文档入口和长期推进方式建立完成。

---

## Stage 1 — 通用规则模型（已完成）

目标：把 Orchestrator、Media Agent、Memory Agent 的 harness 经验，抽象成可复用的规则格式。

已完成内容：

- `policy schema`
- 路径归属、secret scan、危险命令、只读区、外发前检查等规则类型
- Orchestrator / Media Agent / Memory Agent 样例 policy
- 硬门禁与提醒项分层

结果：中枢台的规则表达层已形成第一版基础。

---

## Stage 2 — 任务账本（已完成）

目标：定义任务如何被提交、执行、阻塞、恢复和完成。

已完成内容：

- 任务状态模型：`planned`、`running`、`blocked`、`finished`、`failed`
- `task schema` / `event schema`
- JSONL 样例 ledger
- ledger 校验与一致性检查基础

结果：中枢台的最小 task / event 状态沉淀模型已具备。

---

## Stage 3 — Agent 注册表（已完成）

目标：在 Runtime 外部清楚记录有哪些 Agent、各自能力和边界。

已完成内容：

- agent registry schema
- sample registry
- capability / workspace / boundary / policy profile 等字段
- Agent 间委派与验收关系基础表达

结果：中枢台具备了最小 Agent 元数据层。

---

## Stage 4 — 工具适配器层（已完成第一轮设计）

目标：不再把工具能力绑死在某一个宿主框架里，而是抽象成 adapter。

已完成内容：

- adapter schema
- adapter sample registry
- adapter execution envelope 设计
- runtime gate / report / inspect / validate 等围绕 adapter 的只读链路

当前结论：

- 这一阶段已经有足够多的设计积木
- 但“统一接入中枢台”的总叙事还需要继续补强

---

## Stage 5 — 最小 Runtime CLI（已完成）

目标：做出第一个能跑的命令行入口。

已完成内容：

- `doctor`
- `check text`
- `check path`
- `check action`
- `agents list`
- `adapters list`
- `policies list`
- `task status`
- `task events`
- `task validate`
- `task check-ledger`

结果：仓库已经从纯文档阶段进入可运行的最小 Runtime CLI 阶段。

---

## Stage 6 — Runtime 只读检查链路（已完成）

目标：把 runtime 相关检查链路串起来，但仍保持只读。

已完成内容：

- `runtime plan`
- `runtime draft validate`
- `runtime draft inspect`
- `runtime gate check`
- `runtime report`
- adapter envelope plan / validate / inspect / approval / response / gate check

结果：中枢台的只读 runtime 主线已经跑通。

---

## Stage 7 — 受控写入基础（已完成）

目标：允许最小、可审计、可回滚的项目内写入，而不是一步到位放开执行能力。

已完成内容：

- `runtime draft export --dry-run / --commit`
- `runtime event append --dry-run / --commit`
- `runtime task create --dry-run / --commit`
- controlled write boundaries
- controlled write regression

结果：中枢台已经具备最小受控写入能力，但仍未接入真实外部执行。

---

## Stage 8 — Runtime Event Import 能力包（已完成 v0.11）

目标：把批量候选 event 安全导入现有 event ledger。

已完成内容：

- `runtime event import --dry-run`
- `runtime event import --commit`
- `--expected-plan-hash` consistency freeze
- `--require-dry-run` strict freeze mode
- event import controlled write regression coverage
- `v0.11.0-runtime-event-import`

结果：受控写入链路已经从单条 append 扩展到批量 import，并补上审阅上下文一致性约束。

---

# 下一阶段：从“门禁内核”走向“中枢台后端”

到当前为止，项目最大的风险不是底层能力不足，而是项目叙事容易被误解成“只是在做门禁”。

因此下一阶段不应继续盲目深挖局部门禁细节，而应开始补齐**中枢运行台后端主线**。

---

## Stage 9 — 中枢台定位校正与总蓝图（当前阶段）

目标：明确项目不是单纯 guardrail 工具，而是一个中枢运行台；guardrail 只是其安全与审计内核。

本阶段要做的事：

- 补一份中枢台总蓝图文档
- 明确“接入层 / 编排层 / 状态层 / 门禁内核 / 观察层”五层结构
- 在 README 中加入全景图和新定位说明
- 调整路线图，把后续工作拆成“安全内核”和“中枢台后端”双主线

主要交付物：

- `docs/47-orchestration-hub-vision.md`
- `README.md` / `README.en.md` 定位修正
- `docs/02-roadmap.md` 细化

---

## Stage 10 — Adapter Runtime Interface（下一步高优先级）

目标：定义中枢台如何统一接入 Agent、工具和外部系统，而不是每个工具各写一套调用方式。

要做的事：

- 定义 adapter 分类：agent / tool / service
- 定义统一 adapter metadata
- 定义统一 request / response / artifact / evidence / error 模型
- 定义 approval roundtrip、timeout、cancel、background 等语义
- 对现有 QwenPaw / Kimi / Claude / OMP / Shell / GitHub / Lark / WebBridge 做能力映射草案

主要交付物：

- `docs/48-adapter-runtime-interface.md`
- 后续可能补 adapter capability registry 设计稿

---

## Stage 11 — Capability Routing Model（下一步高优先级）

目标：让上层任务调度优先面向 capability，而不是硬编码具体工具名。

要做的事：

- 设计 capability 命名方式
- 设计 routing 输入 / 输出模型
- 设计 capability match / constraint filter / preference rank 三层路由过程
- 明确 fallback 机制
- 明确 routing 与 guardrail 的边界

主要交付物：

- `docs/49-capability-routing-model.md`

---

## Stage 12 — Control Plane State Model（下一步高优先级）

目标：把未来 CLI、UI、自动化共同依赖的状态对象讲清楚。

要做的事：

- 定义 task / event / run / approval / artifact / evidence / report 等对象关系
- 明确哪些是顶层对象，哪些是附属对象
- 明确这些对象如何支撑审计、回放、观察和 future UI

主要交付物：

- `docs/50-control-plane-state-model.md`

---

## Stage 13 — Backend-first API Boundary（后续优先级高）

目标：虽然现在不急着做 UI，但后端必须先按未来可被 UI 调用的方式设计。

要做的事：

- 定义未来 UI / CLI / automation 共同依赖的 API 边界
- 先做资源模型，不急着选 HTTP / RPC / 本地进程协议
- 明确任务列表、任务详情、run 详情、approval 操作、dry-run / commit、report 的统一接口草案

主要交付物：

- `docs/51-backend-first-api-boundary.md`

---

## Stage 14 — 中枢台最小编排闭环（后续实现阶段）

目标：在后端抽象稳定后，跑通第一个真正体现“中枢台”特征的最小闭环。

候选闭环：

- 用户提交一个 coding task
- 中枢台做 capability routing
- 选择 Kimi Code 执行
- 执行前跑 guardrail preflight
- 落 task / event / run / report
- 如果需要外发或写入，经过 approval / dry-run / commit
- 最终形成可审计收口

要求：

- 不破坏现有工作流
- 有 fallback
- 有 report
- 有 evidence
- 可回放

---

## Stage 15 — UI / 看板前的后端准备（后续）

目标：在不急着做前端的前提下，先把未来看板所需后端对象和操作面准备齐。

要做的事：

- 梳理“总览页、任务页、执行页、审批页、产物页、报告页”分别需要哪些状态对象
- 确认 CLI 输出与状态模型的映射关系
- 确认未来服务化时最小接口边界

说明：

- 这一阶段仍以“后端先行”为原则
- 不是现在马上做 Web UI
- 但必须按未来能长出 UI 的方式组织后端

---

## Stage 16 — UI / Control Panel（远期）

目标：在后端抽象稳定后，为中枢台提供一个真正可操作、可观察、可审计的前端或看板。

候选能力：

- adapter / agent availability 总览
- task / event / run 浏览
- blocked / approval pending 列表
- dry-run / commit 操作面
- artifacts / evidence / reports 查看
- diagnostics / health / regression 状态总览

前提：

- 必须以后端抽象成熟为前提
- 不应倒逼后端临时补洞

---

## 当前策略总结

当前最合理的策略是：

1. 不返工已完成的 guardrail / ledger / controlled write 内核
2. 也不继续盲目深挖更多局部门禁功能
3. 先把“中枢台后端”这条主线的文档和抽象立起来
4. 给后续实现留下清晰的顺序和 handoff

换句话说：

> 现在项目已经把“中枢台的安全内核”打牢，接下来要补的是“中枢台本身”。
