# 47 — Orchestration Hub Vision

## 阶段定位

本文用于校正 `s-black harness engineering` 的项目定位：它不应只被理解为“规则门禁工具”或“受控写入 Runtime”，而应被定义为一个面向多 Agent、多工具、多渠道的**中枢运行台（Orchestration Hub / Control Plane）**。

当前已经落地的 policy、ledger、controlled write、freeze 与 verification 能力，不是项目的全部，而是未来中枢台的**安全与审计内核**。

## 为什么要校正定位

当前仓库已经在以下方向投入了较多实现：

- 规则检查
- 路径守卫
- secret scan
- task / event ledger
- controlled write
- freeze / strict freeze
- completion verification

这些都很重要，而且没有做错。

但如果仓库叙事继续只围绕“门禁”展开，会导致两个问题：

1. 项目愿景被压缩成一套安全检查工具，而不是 Agent 系统的中枢运行层。
2. 后续若要接入 Kimi、Claude、OMP、Shell、飞书、GitHub、WebBridge、Obsidian、邮件、日历等能力，会缺少统一编排语义。

因此需要明确：

> 门禁不是项目本体，门禁只是中枢运行台的内核能力之一。

## 最终希望形成的结构

```text
用户 / CLI / 飞书 / 未来 UI
  -> Orchestration Hub / Control Plane
  -> Capability Routing
  -> Policy Guardrails / Approval / Completion Checks
  -> Agent & Tool Adapters
       -> QwenPaw
       -> Kimi Code / WebBridge
       -> Claude Code
       -> OMP / pi
       -> Shell
       -> GitHub
       -> Lark
       -> Obsidian
       -> 其他外部系统
  -> Task / Event / Run / Approval / Artifact State
  -> Report / Audit / Observability
```

## 中枢台的五层结构

### 1. 接入层（Adapter Layer）

负责把不同宿主、工具、Agent 与外部系统统一接进来。

典型对象：

- QwenPaw
- Kimi Code ACP
- Kimi WebBridge
- Claude Code ACP
- OMP / pi
- Shell
- GitHub CLI / API
- 飞书
- Obsidian
- 邮件 / 日历 / NAS / Gitea

这一层回答的问题是：

- 这个工具是什么
- 它支持什么操作
- 它的输入输出长什么样
- 它的风险等级和前置条件是什么

### 2. 编排层（Orchestration Layer）

负责决定任务如何被拆解、路由、执行、审查与收口。

这一层回答的问题是：

- 哪个任务应该交给哪个 Agent / Adapter
- 哪些步骤串行，哪些步骤并行
- 哪些步骤必须 dry-run 再 commit
- 哪些步骤必须审批
- 谁负责执行，谁负责 review

### 3. 状态层（Control Plane State）

负责把运行过程沉淀成可追踪状态，而不是只留在聊天和 stdout 里。

关键对象包括：

- task
- event
- run
- approval request
- artifact
- evidence
- report

这一层回答的问题是：

- 现在系统在做什么
- 做到哪一步了
- 卡在哪里
- 证据在哪里

### 4. 安全与审计内核（Guardrail Core）

这是当前已经做得最实的一层。

能力包括：

- policy check
- path guard
- secret scan
- action preflight
- controlled write
- consistency freeze
- strict freeze
- completion verification

这一层回答的问题是：

- 什么能做
- 什么不能做
- 什么必须审批
- 什么必须可回滚
- 什么不能只靠口头宣称完成

### 5. 观察层（Observability Layer）

未来 UI、CLI 总览、日报、诊断和运行审计都依赖这一层。

需要支持的问题包括：

- 当前有哪些 agent / adapter 可用
- 最近跑了哪些任务
- 哪些任务 blocked
- 哪些 run 失败率高
- 哪些审批悬而未决
- 哪些 ledger / artifact / report 可回放

## 当前阶段的准确定位

更准确的说法不是：

> 我们在做一个完整中枢台。

而应该是：

> 我们已经完成了中枢台里最底层、最难返工的“规则 / 账本 / 受控写入内核”，接下来要把统一接入、能力路由、控制面状态和未来 UI 可操作边界补上。

## 与 UI 的关系

未来确实应有 UI 看板或前端操作面板，但当前优先级应是：

- 先把后端统一抽象设计清楚
- 再让 UI 消费这些状态和动作边界

原因：

- 如果后端只是堆一批 CLI 命令，UI 之后大概率要返工。
- 如果后端一开始就按 capability、run-state、approval、artifact、report 这些对象组织，UI 只是晚一点接上去。

因此本阶段结论是：

> 先后端，后前端；但后端现在就要按未来可被 UI 驱动的方式设计。

## 本文后的紧接主线

在本定位校正之后，建议继续补齐四条后端设计主线：

1. `48 — Adapter Runtime Interface`
2. `49 — Capability Routing Model`
3. `50 — Control Plane State Model`
4. `51 — Backend-first API Boundary`

其中：

- 48 负责回答“工具如何接进来”
- 49 负责回答“能力如何路由和解耦”
- 50 负责回答“控制面到底记录哪些状态对象”
- 51 负责回答“即使现在没有 UI，未来 UI 应如何操作后端”

## 本阶段不做什么

本文不实现：

- UI 页面
- HTTP 服务
- WebSocket 推送
- 真实多 Agent 编排引擎
- 新的外部写权限
- 新的真实 adapter execution

本文只做项目愿景和后端主线校正，为后续设计和实现建立统一叙事。
