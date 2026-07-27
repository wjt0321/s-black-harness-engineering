<!-- parents: 01-vision-and-boundaries.md, 47-orchestration-hub-vision.md, archive/129-stage81-current-operator-inbox-and-approval-collection.md -->

# 130 — GUI-first 外部 Agent 控制面目标与 MVP 边界

> 状态：长期产品目标已冻结；当前仅作为架构与路线约束，不授权任何新执行能力
> 日期：2026-07-26

## 1. 产品决策

本项目的最终目标是一个由用户掌控、GUI-first、本地优先的多 Agent Harness / Control Plane。它统一接入 Claude、Kimi、OMP/Pi、QwenPaw 和未来其他 Agent 工具，让用户在一个可视化看板内观察状态、分派任务、处理审批、跟踪执行、审阅结果并组织多 Agent 协同。

本项目不是：

- 另一个日常聊天 Agent；
- 新的模型 Provider 或通用模型 SDK；
- 替代 Claude、Kimi、OMP/Pi、QwenPaw 的 Agent Runtime；
- 以 TUI/CLI 为最终产品形态的开发者工具；
- MyAgent 的重写、分支或融合项目。

Harness 的职责是约束和编排外部 Agent，而不是重新实现它们已有的模型调用、上下文、记忆、工具系统和编码能力。

## 2. 最终产品形态

最终用户体验是一个统一的桌面或本地 GUI 控制台，而不是多个终端窗口和聊天页面。当前 `build/` 中的静态 Control Panel 是视觉与信息架构原型，不是最终运行架构。

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

阶段 81-85 已完成计划、插座/能力、样例运行、交接/审阅/产物模型、操作资格、当前待办、静态中文控制面板、统一外部智能体适配器契约、固定原子快照读取器和被动状态采集设计。阶段 86 已实现 Pi/OMP 项目级进程内状态扩展、固定生产绑定、原子快照、安全读取器多配置和中文控制面板实时状态区段。底层仍只有固定 Git 状态与固定 Pi 打印两项受控真实操作。

当前仍缺少：

- 用户手动启动 Pi/OMP 后的最终真实连接与退出验收；
- 可用于派发的真实智能体就绪与会话证据；
- 审批到真实派发的精确绑定；
- 工作项到外部智能体的真实受控派发；
- 真实事件流、产物和审阅结果回收；
- 规划者 -> 执行者 -> 审阅者闭环；
- 图形界面的实时数据和结构化命令通道；
- 多智能体并发、取消和恢复的真实验收。

当前 Pi/OMP 状态链路只证明“观察到宿主”，不证明模型可用、会话已绑定或允许派发。QwenPaw 2.0.1 的兼容接入延后到 Pi/OMP 验收之后。

## 9. 当前能力包

### 阶段 82-85 — 契约、读取器与采集设计（已完成并归档）

- 冻结统一外部智能体身份、能力、状态、会话、派发、事件、产物和恢复契约；
- 选择适配器拥有的固定原子快照作为首个只读观察面；
- 实现 `omp-acp` 有界稳定读取、严格身份/生产者绑定和失败关闭界面映射；
- 冻结宿主内被动采集、单写者租约、generation、原子替换、测试要求和实施停止线；
- 证据始终不授予执行或派发权限。

### 阶段 86 — Pi/OMP 真实只读状态接入（已完成并归档）

- 本机核验 Pi 0.82.0 与 OMP 1.3.14 的项目级扩展位置；
- 在 `.pi/extensions/` 与 `.omp/extensions/` 中实现极薄入口，共用无网络、无子进程的原子发布器；
- 增加 `pi-local`、`omp-local` 固定生产绑定和内容摘要审阅；
- 读取器只允许三个固定配置，不接受任意路径；
- 中文控制面板显示“未连接”“已连接，存在未绑定会话”或“状态已过期”；
- 本地状态目录权限已收紧；
- 自动验证、真实连接态、关闭态、租约释放和过期映射均已通过。

阶段 86 不由 Harness 启动智能体，不创建会话、不发送提示词、不调用模型、不主动连接 ACP、不派发任务，也不新增第三个真实执行操作。

### 后续候选

阶段 86 已验收并归档；后续按价值评估：真实审批绑定与单工作项受控派发、真实事件/产物/审阅回收、多智能体闭环、实时中文图形界面和桌面封装，以及 QwenPaw 2.0.1 等其他宿主的只读状态兼容。

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
