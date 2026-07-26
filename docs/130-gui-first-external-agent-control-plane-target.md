<!-- parents: 01-vision-and-boundaries.md, 47-orchestration-hub-vision.md, 129-stage81-current-operator-inbox-and-approval-collection.md -->

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

Stage 81 已完成计划、socket/capability、fixture run、handoff/review/artifact 模型、操作资格、当前待办和静态中文 Control Panel。底层已有 fixed Git status 与 fixed Pi print 两项受控真实 operation。

当前仍缺少：

- live external Agent adapter；
- 真实 Agent readiness/session evidence；
- approval 到真实 dispatch 的绑定；
- work item 到外部 Agent 的真实派发；
- streaming event 与 artifact 回收；
- live Planner -> Executor -> Reviewer 闭环；
- GUI 的实时数据和结构化 command 通道；
- 多 Agent 并发、取消和 recovery 的真实验收。

因此项目已完成控制面骨架和视觉方向，但尚未完成外部 Agent 的真实生命线。

## 9. 下一能力包

### Stage 82 — External Agent Adapter Contract 与 MVP Boundary

- 冻结 identity、capability、readiness、session、dispatch、event、cancel、artifact、recovery contract；
- 把 approval evidence 安全审查作为 dispatch authority 的子问题；
- 明确 ACP/CLI/local process transport 的共同语义；
- 输出 schema、failure matrix、测试计划和 GUI 所需最小 live read model；
- 仍不调用 Agent、不启动 session、不实现网络 adapter、不新增真实 operation。

### 后续候选

1. 一个外部 Agent 的只读 live status adapter；
2. 单 work-item 真实受控 dispatch；
3. 真实 event/artifact/review 回收；
4. Planner -> Executor -> Reviewer 多 Agent 闭环；
5. Claude、Kimi、OMP/Pi、QwenPaw adapter 扩展；
6. live GUI 和桌面封装；
7. 并发、恢复和长期稳定性强化。

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
