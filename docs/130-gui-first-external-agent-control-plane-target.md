<!-- parents: 01-vision-and-boundaries.md, 47-orchestration-hub-vision.md, archive/129-stage81-current-operator-inbox-and-approval-collection.md -->

# 130 — GUI-first 聚合式 Agent 工作台目标与 Harness 边界

> 状态：长期产品目标；截至 2026-07-29，Agent Deck P0、任务工作区与受控任务登记已完成，阶段 97 的受限主控规划仍须独立设计与授权
> 日期：2026-07-29

## 1. 产品决策

本项目的最终目标是一个由用户掌控、GUI-first、本地优先的 **聚合式 Agent 工作台（Agent Deck）**。它统一接入 Claude Code、Kimi Code、Codex CLI、OMP/Pi、QwenPaw 和未来其他 Agent 工具，将它们组织为同一项目中的可见团队：用户发布目标、观察协作、验收结果；主 Agent 逐步承担计划、分工、协调、汇总和验收建议。Harness / Control Plane 是此工作台的可信底层，而不是用户默认面对的产品主体。

本项目不是：

- 另一个日常聊天 Agent；
- 新的模型 Provider 或通用模型 SDK；
- 替代 Claude、Kimi、OMP/Pi、QwenPaw 的 Agent Runtime；
- 以 TUI/CLI 为最终产品形态的开发者工具；
- MyAgent 的重写、分支或融合项目。

Harness 的职责是约束和编排外部 Agent，而不是重新实现它们已有的模型调用、上下文、记忆、工具系统和编码能力。

## 2. 最终产品形态

最终用户体验是一个统一的桌面或本地 GUI 工作台，而不是多个终端窗口、孤立聊天页面或内部控制表单。用户首先看到项目、任务、Agent 团队、协作和成果；链路、租约、审计与证据只在需要时展开。当前 `build/` 中的静态 Control Panel 是早期视觉与信息架构原型，不是最终运行架构。

```text
用户
  -> GUI / Desktop Control Panel
  -> Harness Control Plane
       -> Plan / Work Item / Run / Approval / Handoff / Review / Artifact
       -> Capability Routing / Policy / Audit / Recovery
       -> Agent Adapter / Socket Contract
            -> Claude Code
            -> Kimi Code
            -> OMP / Pi
            -> QwenPaw / ACP
            -> 未来其他 Agent
```

GUI 是默认产品入口。CLI 继续承担自动化、诊断、确定性 JSON、开发和恢复职责，但不定义最终 UX。

## 3. 权威边界

### Harness 拥有的事实

- collaboration plan；
- work item、依赖和角色分配；
- run、attempt、approval、handoff、review 和 artifact 状态；
- 操作者待办、操作资格和阻止原因；
- dispatch identity、idempotency、lease、audit 和 recovery lineage；
- Control Panel 的统一 read model。

### 外部 Agent 拥有的事实

- 模型和 Provider 选择；
- Agent 内部上下文、推理和 memory；
- Agent 原生 session；
- Agent 原生工具实现；
- 工具调用的原始输出；
- Agent 自身能够提供的 capability 和 transport 特性。

Harness 只能依据 adapter evidence 投影外部 Agent 状态，不得伪造 readiness、session、工具结果或完成状态。外部 Agent 也不得绕过 Harness 的计划、审批、审计和受控派发边界修改 control-plane 事实。

## 4. Agent Adapter / Socket 最小契约

未来所有 Agent 接入必须复用统一 contract，不为每个 Agent 建立专用主流程或专用 UI 分支。最小能力面应覆盖：

1. identity：稳定 Agent、adapter、transport 和版本身份；
2. capabilities：声明可处理的任务、工具、输入和 artifact 类型；
3. readiness：有界、可过期、可验证的可用性 evidence；
4. session：创建、恢复、关闭和外部 session identity 投影；
5. dispatch：接受结构化 work-item envelope，不接受任意 argv/cwd/env 旁路；
6. events：输出有序、可去重、可恢复的状态与进度事件；
7. cancellation：明确是否支持取消以及取消的最终状态；
8. artifacts：返回结构化 artifact reference 和安全摘要；
9. recovery：处理 timeout、进程退出、连接中断和 outcome unknown；
10. audit：把真实执行绑定到唯一 started/terminal audit 生命周期。

ACP、CLI、local process、WebSocket 或未来协议只是 transport；它们不得改变上层 plan/run/approval/handoff 语义。

## 5. 多 Agent 协同模型

多 Agent 协同以 Harness 管理的结构化对象为主，不以 Agent 之间自由、不可审计的聊天作为控制面事实。

推荐闭环：

```text
用户创建目标
  -> Harness 生成或接收 collaboration plan
  -> Planner Agent 输出结构化计划或修订建议
  -> 用户确认 / 审批
  -> Executor Agent 执行一个或多个 work item
  -> Harness 收集事件和 artifact
  -> Reviewer Agent 产生结构化 review decision
  -> Harness 决定完成、要求修改、retry、cancel 或 handoff
  -> 用户在统一看板中观察和控制全过程
```

Agent-to-Agent 通信通过 work item、handoff、artifact、review decision 和受控 message envelope 传递。Harness 必须能够回答：谁在何时把什么事实交给了谁、基于什么版本、产生了什么结果、是否经过审批。

## 6. GUI-first 原则

最终 Control Panel 至少应包含：

- Agent 拓扑和当前状态；
- capability、transport、readiness 和 session 摘要；
- 任务队列、work-item 泳道和依赖；
- 当前执行、进度事件和工具活动的安全摘要；
- approval inbox、阻止原因和可执行操作；
- handoff、review 和 artifact 时间线；
- retry、cancel、要求修改、批准交接等显式操作；
- audit、recovery 和 outcome-unknown 状态；
- 中文默认、可视化优先、无需依赖终端理解内部协议。

桌面壳可以在 Control Plane API/read model 稳定后采用 Tauri、Electron 或本地 WebView。桌面端不得直接拥有 ledger、审批或执行权限逻辑。

## 6.1 未来体验与视觉方向预留

后期 UI/UX 可借鉴高完成度消费级 Agent 产品的设计语言；`makecindy/cindy` 及其产品主页是本项目的参考之一。借鉴的是产品表达与交互品质，不复制其品牌、文案、素材、代码或信息架构。

- **产品感优先**：控制台应从“开发者调试页”提升为可信、从容、精致的 Agent 工作台；高信息密度不等于堆叠表格、日志和告警色。
- **冷静地呈现复杂性**：任务、协作、审批、结果与恢复状态以明确层级和渐进披露呈现；默认先回答用户当前最需要判断的事，再允许进入证据、事件和协议细节。
- **让协作可感知**：Agent、角色、handoff、当前轮次和产物关系应有直观、连续的可视化，而不只是一组孤立状态字段。
- **信任底座不抢视觉中心**：安全、审批、审计、阻止原因和恢复证据必须随时可达、措辞清楚，但不应把产品体验塑造成“风险告警墙”。
- **产品叙事与运行时分层**：未来静态 landing page 负责讲清“为什么需要多 Agent 中枢台、它带来怎样的掌控感”；登录后的 Control Panel 负责真实状态、受控操作与证据。两者可共享视觉 token 和品牌语言，但不得混淆营销展示与权威运行事实。
- **连续故事骨架**：官网优先以“**Harness Deck → 多角色协作流水线 → 信任保障 → 可塑性**”组织叙事：先说明可插入哪些 Agent 与能力，再展示从计划、执行到审阅和人工决定的协作闭环；接着说明审批、证据、审计与恢复如何让用户始终掌控；最后说明 Adapter、Skill、Automation 和开放协议如何让工作台持续成长。此骨架面向 Agent Runtime 自己的对象与文案，不复制第三方品牌、素材或信息架构。
- **中文优先与可访问性**：默认简体中文、可读性、键盘操作、动效降级和状态色之外的文本/图标冗余表达均是产品质量的一部分。

这不是当前 UI 实现授权，也不预设具体框架、视觉稿或动效。开始独立 GUI Stage 前，应将这组原则转化为设计 token、信息架构、关键任务流、可访问性验收和静态页面/控制面分别验证的原型。

## 6.2 Agent Deck 平台主线与 P0

2026-07-29 起，产品主线以 Agent Deck 为准：Harness 继续提供唯一可信的审批、租约、审计、证据和受控派发，但产品默认路径改为“用户给出目标 → 团队协作 → 主摘要与验收”。

P0 先完成：中文应用壳、项目空间、自然语言任务入口、统一 Agent 团队卡片、协作时间线、结果与验收视图，以及 Pi/OMP 的真实试运行投影。Codex CLI、Claude Code、Kimi Code 等先以统一待接入模型出现；不得声称已获得真实状态或执行能力。阶段 94 的验收范围与证据见 `archive/144-stage94-agent-deck-pilot-acceptance.md`。

Cindy 及类似产品仅作为任务入口、设置层级、成员协作感和产品完成度的交互参考；不得复制任何第三方品牌、素材、代码、文案或信息架构。shadcn/ui 是受控展示层候选，不持有执行 authority。

## 7. 可用 MVP 定义

本项目的 MVP 不是单 Agent 聊天，也不是只读静态看板。MVP 必须证明统一 contract 能支撑真实的多 Agent 工作闭环：

1. 至少接入三类外部 Agent transport/implementation，且不出现 Agent-specific 主流程；
2. GUI 可以展示真实 Agent 状态和当前任务；
3. 用户可以创建或确认 collaboration plan，并把 work item 分配给 Agent；
4. 至少一个 Planner -> Executor -> Reviewer 闭环真实完成；
5. dispatch 必须经过明确 approval、identity、lease 和 audit；
6. 执行事件、artifact、review、retry/cancel 至少各有一条真实验收路径；
7. 任一 Agent 不可用时能够 fail closed，并在看板中给出稳定原因；
8. 所有公开投影保持 bounded、deterministic，并不释放凭据或不受控原文。

MVP 可以继续限制为单用户、本地运行、显式人工审批、有限并发、有限 Agent 列表和有限 operation；不要求云端、多租户、自动无限运行或完整插件生态。

## 8. 当前完成度与真实缺口

阶段 86–93 已完成 Pi/OMP 的只读状态、单工作项受控执行、不可变证据、人工审阅、有限三角色串行、GUI 启动/最终决定和有限放弃；它们继续作为可信底层。阶段 94–96 已将产品主线推进到 Agent Deck：中文工作台、浏览器草案、真实任务安全队列，以及受控正式任务登记与“等待主控 Agent 规划”收件箱均已完成。

当前已经具备：

- 一个统一展示项目、任务、团队、协作、交付与验收的本地前端；
- 真实 Pi/OMP 受控链路、证据、审阅和最终人工决定；
- 将用户目标安全登记为 Harness 任务，而不把草案或登记本身解释为执行授权；
- Codex CLI、Claude Code、Kimi Code 等统一待接入模型，且不伪造它们的真实状态或能力。

当前真实缺口：

- 主控 Agent 尚未对已登记任务产生结构化、可审阅的计划提议；
- GUI 尚无经独立设计的本地写入/确认桥接；
- Claude、Kimi、QwenPaw 等尚未完成与 Pi/OMP 同等级的真实 adapter 接入；
- 取消、恢复、有限并发和多项目能力仍未进入当前产品范围。

因此，下一步不是扩大自由执行，而是在阶段 97 中完成受限主控规划提议的独立设计。Pi/OMP 链路仍只允许一个经过确认的固定工作项进入用户已打开的空闲会话；它不代表通用会话控制、项目文件回收、工具授权或自治能力。

## 9. 当前能力包

### 可信 Harness 底层（阶段 82–93，已完成并归档）

- 统一 Agent identity、capability、readiness、session、dispatch、event、artifact、recovery 与 audit 契约；
- Pi/OMP 固定原子状态读取、身份/生产者绑定、中文控制面板和失败关闭；
- 单工作项派发、lease、started/terminal audit、真实事件、不可变证据、人工审阅与固定恢复；
- 有界 `Planner → Executor → Reviewer` 串行链路、GUI 结构化启动与最终业务决定；
- 不开放任意命令、Agent 工具、网络、服务、并发或自治循环。

对应验收事实源从 `archive/135-stage86-pi-omp-live-status-integration.md` 至 `archive/142-stage93-pending-final-decision-abandonment.md`。

### Agent Deck 产品切片（阶段 94–96，已完成并归档）

- 阶段 94：中文 P0 工作台、Agent 团队、协作时间线、交付与验收展示，并完成 Pi/OMP 真实试运行；
- 阶段 95：浏览器协作草案与 Harness 真实安全任务队列分开展示；
- 阶段 96：有界目标经显式提交进入固定任务账本，显示“等待主控 Agent 规划”，但不启动 Agent。

事实源：`archive/144-stage94-agent-deck-pilot-acceptance.md`、`archive/145-stage95-agent-deck-mission-workspace.md`、`archive/146-stage96-controlled-mission-intake.md`。

### 后续候选

阶段 97“受限主控 Agent 结构化规划提议”必须先冻结计划输入、输出 schema、持久化/审计、确认门和失败关闭语义。运行中取消、恢复执行、有限并发、QwenPaw 兼容和 GUI 写入桥接均不是当前默认实现项，必须另行设计和授权。

## 10. 反偏航检查表

任何新 Stage 开始前都必须回答：

- 它是否让统一 GUI 更接近真实可用，而不是增加另一个终端入口？
- 它是否复用统一 Agent adapter/socket contract，而不是增加专用旁路？
- 它是否强化 Harness 的控制、审批、状态、协同或审计，而不是重做外部 Agent？
- 它是否能服务 Claude、Kimi、OMP/Pi、QwenPaw 中至少两类实现，而不是只绑定单一产品？
- 它是否保持外部 Agent 与 Harness 的事实权威分离？
- 它是否为 Planner/Executor/Reviewer、handoff、artifact 或 review 闭环提供实际价值？
- 它是否避免把 preview、readiness、fixture approval 或业务资格解释为执行授权？
- 它是否有明确停止线、测试计划和回滚/恢复语义？

如果答案是否定的，该能力默认不进入当前产品主线。
