# 01 — 愿景与边界

> 长期产品目标事实源：`130-gui-first-external-agent-control-plane-target.md`

## 背景问题

Claude、Kimi、OMP/Pi、QwenPaw 等 Agent 工具已经能够完成真实工作，但它们通常拥有不同的入口、session、工具、权限、事件和结果表达。用户需要在多个 CLI、TUI 或聊天窗口之间切换，难以统一观察任务、审批、交接、产物和失败恢复，也很难把宿主内置逻辑变成自己可掌控、可审计的长期系统。

本项目因此建设一个独立的 Agent Harness / Control Plane。QwenPaw、Claude、Kimi、OMP/Pi 和未来 Agent 都是可替换的外部执行节点，不是本项目本身。

## 项目愿景

最终产品是 GUI-first、本地优先的多 Agent 控制台：

```text
用户
  -> GUI / Desktop Control Panel
  -> Harness Control Plane
       -> Plan / Work Item / Run / Approval / Handoff / Review / Artifact
       -> Capability Routing / Policy / Audit / Recovery
       -> Agent Adapter / Socket
            -> Claude / Kimi / OMP/Pi / QwenPaw / 未来 Agent
```

用户应能够在统一看板中：

- 查看所有 Agent 的身份、能力、状态、session 和当前任务；
- 创建或确认协作计划，并把 work item 分配给不同 Agent；
- 处理审批、阻止、retry、cancel、review 和 handoff；
- 查看真实执行事件、artifact、错误和 recovery；
- 组织 Planner、Executor、Reviewer 等结构化多 Agent 协同。

CLI 继续服务自动化、诊断、恢复和确定性机器接口，但不是最终用户体验。

## 核心原则

1. **外部 Agent 中立**：不把单一 Agent 或 ACP transport 写成系统核心。
2. **GUI-first**：默认以可视化 Control Panel 呈现状态、控制和协同。
3. **Harness 不重做 Agent**：模型、上下文、记忆和原生工具由外部 Agent 负责。
4. **结构化协同**：Agent 通过 work item、handoff、artifact 和 review decision 协同，而不是依赖不可审计的自由聊天。
5. **规则与审批优先**：高风险动作必须经过稳定门禁、身份绑定和显式授权。
6. **事实权威分离**：Harness 拥有 control-plane 状态；外部 Agent 拥有原生 session 和工具执行事实。
7. **可审计、可恢复**：真实执行必须有 started/terminal audit、bounded output 和 outcome-unknown recovery。
8. **积木式接入**：新增 Agent 必须复用统一 adapter/socket contract，不增加专用主流程或 UI 旁路。

## 当前边界

Stage 81 已完成只读、fixture-backed 的协作计划、运行状态、操作资格、当前待办和静态中文 Control Panel。当前真实执行仍只有 fixed Git status 和 fixed Pi print。

当前尚未开放：

- live external Agent adapter；
- 真实 Agent readiness/session；
- approval 到真实 dispatch 的绑定；
- 多 Agent 的真实 Planner -> Executor -> Reviewer 闭环；
- 网络 adapter、长期服务、数据库和自动后台执行；
- 通用 shell、任意 argv/cwd/env 或未经独立设计的第三个真实 operation。

下一阶段必须先冻结统一外部 Agent adapter contract 和 MVP boundary，再讨论真实接入。
