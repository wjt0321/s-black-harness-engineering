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

目标：定义中枢台如何以“积木式可插拔”方式统一接入 Agent、工具和外部系统，而不是每个工具各写一套调用方式。

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

## Stage 13 — Backend-first API Boundary（设计文档已落地，协议选择仍暂缓）

目标：虽然现在不急着做 UI，但后端必须先按未来可被 UI 调用的方式设计。

要做的事：

- 定义未来 UI / CLI / automation 共同依赖的 API 边界
- 先做资源模型，不急着选 HTTP / RPC / 本地进程协议
- 明确任务列表、任务详情、run 详情、approval 操作、dry-run / commit、report 的统一接口草案

主要交付物：

- `docs/51-backend-first-api-boundary.md`

说明：

- 资源模型与操作模型已在 51 中定义。
- 协议（REST / RPC / 本地进程调用）和鉴权细节仍不在本阶段展开。
- 本阶段仍保持“文档先行”，不进入协议实现。

---

## Stage 14 — 中枢台最小编排闭环（设计文档已落地，受控实现仍暂缓）

目标：在后端抽象稳定后，跑通第一个真正体现“中枢台”特征的最小闭环。

主要交付物：

- `docs/52-minimal-orchestration-loop.md`
- `docs/53-minimal-orchestration-loop-cli-draft.md`（命令面草案参考，非正式 API 边界）

候选闭环：

- 提交 task intent
- 中枢台做 capability routing（49）
- 执行 guardrail preflight（不阻塞闭环设计，只决定执行模式）
- 按 dry-run / commit 模式执行 adapter（48）
- 沉淀 task / event / run / artifact / evidence（50）
- 如需审批，创建 approval request 并暂停等待决议
- 生成 report，给出 next_action

要求：

- 不破坏现有工作流
- 有 capability-level fallback
- 有 report
- 有 evidence
- 可回放
- 不进入真实多系统放权、UI、服务化、数据库选型

---

## Stage 15 — UI / 看板前的后端准备（read-model CLI 第一版已落地，前端实现仍暂缓）

目标：在不急着做前端的前提下，先把未来看板所需后端对象和操作面准备齐。

主要交付物：

- `docs/54-backend-preparation-before-ui.md`
- `docs/55-release-notes-orchestration-read-models.md`
- 十只读 `orchestration *` CLI 命令（见 55）

要做的事：

- 梳理“总览页、任务页、执行页、审批页、产物页、报告页”分别需要哪些状态对象
- 确认 CLI 输出与状态模型的映射关系
- 为每一类页面提供最小只读 CLI read model

已落地能力：

- 总览页：`orchestration overview`
- 任务页：`orchestration task list` / `orchestration task get`
- 执行页：`orchestration run list` / `orchestration run inspect`
- 审批页：`orchestration approval list` / `orchestration approval get`
- 产物页：`orchestration artifact list` / `orchestration artifact get`
- 报告页：`orchestration report generate`

说明：

- 这一阶段仍以“后端先行”为原则
- 不是现在马上做 Web UI，也不是做服务/数据库
- 所有 read model 都是只读 CLI，不写 ledger、不执行 adapter、不访问网络
- Run / Approval / Artifact 当前为 envelope-scoped；Report 为 runtime-report-backed，均未引入独立持久集合

---

## Stage 15.5 — Orchestration 受控写入边界（第一批 controlled handoff / approval resolve 已落地）

目标：在进入第一批 orchestration 写入命令前，先把 dry-run / commit 语义、capability routing handoff、approval resolve 安全边界定清楚，并实际落地第一批 handoff / controlled-write 命令。

主要交付物：

- `docs/56-orchestration-controlled-write-boundary.md`（design gate）
- `docs/57-release-notes-orchestration-controlled-handoff.md`
- `orchestration route preview`（只读 capability routing preview）
- `orchestration preflight`（只读 routing + guardrail 聚合）
- `orchestration approval resolve`（event-ledger append 方案受控写入）

已落地能力：

- `route preview` 输出安全 routing decision，为 `preflight` / `runtime plan` 提供输入。
- `preflight` 聚合 routing + guardrail，明确 `effective_mode`、`requires_approval`、`requires_dry_run`。
- `approval resolve` 只记录 decision，不执行原请求；`--dry-run` 预览 event，`--commit` 追加 `approval_resolved` event 到 ledger；granted 后仍需重新发起 preflight/run。
- `tasks/event.schema.json` 新增 `approval_resolved` event_type。

要做的事（仍保留）：

- 明确 `orchestration run --dry-run/--commit` 的 draft/export 产物形态和 freeze guard。
- 明确 `orchestration task submit --commit` 与现有 `runtime task create --commit` 的关系。
- 在 retry / fallback 自动化进入实现前，先确认 run 侧状态沉淀规则。

说明：

- 本阶段先实现只读 handoff 命令，再实现第一条受控写入命令；`orchestration run --commit`、retry / fallback、真实 adapter execution 仍未开放。
- 不标记 Stage 16 开始；Stage 16 仍保持远期。
- 完成本阶段后，下一步建议先明确 run draft/export 产物形态，再进入 Stage 14 run 侧实现。

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

## Guardrail 主线策略

guardrail / ledger / controlled write 这条主线仍然是必需能力，不应被放弃。

但从当前阶段开始，它的推进策略调整为：

1. **允许继续补完**：如果后续在接入、编排或控制面设计中发现 guardrail 缺口，可以继续回补。
2. **不阻塞主线**：只要不影响中枢台后端主线推进，就不要求在当前阶段把所有门禁一次性做完。
3. **阶段性回补**：可以在每完成一个中枢台阶段后，回头整理本阶段暴露出的 guardrail 缺口。
4. **边做边发现**：允许在 capability routing、adapter 接入、state model、future UI 准备过程中，再反推哪些 guardrail 还需要增强。

这意味着：

> guardrail 不是“做完了才准继续”，而是“作为长期内核，伴随中枢台成长持续补完”。

## 当前策略总结

当前最合理的策略是：

1. 不返工已完成的 guardrail / ledger / controlled write 内核
2. 不把 guardrail 当成必须一次性收尾的前置阻塞项
3. 先把“中枢台后端”这条主线的文档和抽象立起来
4. 在后续阶段中持续记录和回补 guardrail 缺口
5. 给后续实现留下清晰的顺序和 handoff

换句话说：

> 现在项目已经把“中枢台的安全内核”打牢，接下来要补的是“中枢台本身”；而安全内核会在后续阶段继续跟着主线一起长。
