# Agent Deck 平台 MVP 设计

> 状态：范围与第一段设计已获用户确认；实施前须由用户审阅本文件并确认实施计划。
>
> 日期：2026-07-29
> 关联当前阶段：[`../../143-agent-deck-platform-mvp.md`](../../143-agent-deck-platform-mvp.md)

## 1. 目标与产品重置

Agent Runtime 的产品主线调整为 **Agent Deck**：一个本地优先的聚合式多 Agent 工作台。它将用户系统中彼此独立的 CLI Agent（首批为 Pi 与 OMP，后续为 Codex CLI、Claude Code、Kimi Code 等）以统一项目、任务和团队视图组织起来。

用户的默认动作应当是：给出目标、观察协作、验收结果。主 Agent 最终应代替用户完成任务拆解、角色选择、成员协调、进度汇总和验收建议；用户仅在需要授权、处理冲突或最终验收时介入。

Harness 不是前台产品主角。它保留为唯一可信的底层：受控派发、policy、lease、approval、audit、evidence、artifact 边界和失败关闭。前台不应要求用户理解 `chain_id`、lease 或 audit event。

## 2. 非目标与冻结边界

本 MVP 不：

- 复制 Cindy 或任何第三方品牌、代码、素材、文案或信息架构；截图只作为产品完整感与交互层级参考；
- 替代任何已安装 CLI Agent 的模型、session、记忆、工具或原生设置；
- 新增任意 argv/cwd/env、通用 shell、任意文件写入、自动后台执行、网络 adapter、数据库或凭据管理；
- 让 UI 读取 `.env`、token、keyring、私钥或既有 CLI 的认证信息；
- 把“已发现”或“可见”解释为执行授权；
- 在第一阶段实现运行中取消、恢复执行、并发、自动重试或完全自治的主 Agent；
- 让 Harness 启动、关闭或重启外部 Agent。

现有 Pi/OMP 的固定真实链路、审计、不可变证据和最终人工决定仍然有效；平台只能通过已定义、受校验的结构化命令复用它们。

## 3. 为什么第一阶段选择“工作台优先”

可选路线有三条：

1. Adapter-first：先把更多 CLI 接入后端；技术覆盖快，但继续把用户留在不可见的底层；
2. 主 Agent-first：先做自动规划和调度；接近最终愿景，但在团队、任务和可视化尚不存在时过程不可理解；
3. **工作台优先 + Pi/OMP 真实试运行（采用）**：先建立项目、任务、团队和协作的产品外观，同时用现有 Pi/OMP 作为第一支真实团队验证状态和结果闭环。

选择第三条，因为它最早让用户看见并使用“聚合式 Agent 平台”，同时不抛弃已验收的 Harness 边界。

## 4. MVP 用户旅程

```text
选择项目 / 新建任务
  -> 用自然语言描述目标
  -> 选择“协同执行”或接受默认协作建议
  -> 查看主 Agent 的简明计划与队友分工
  -> 观察 Pi / OMP 状态、交接和产物摘要
  -> 查看主摘要、审阅建议与证据摘要
  -> 通过 / 要求修改 / 有限放弃
```

第一阶段的“主 Agent”仅是显式的产品角色与协调策略占位，不得假装具备未实现的自治能力。真实任务仍严格复用已登记工作卡和现有受控 `Pi → OMP → Pi` 或反向拓扑；界面将它们翻译成规划、执行、审阅三种团队角色。

## 5. 页面与交互信息架构

### 5.1 应用壳

常驻左侧导航采用中文、分组、可折叠的信息层级：

```text
新建任务
任务看板
Agent 团队
协作记录
交付与验收
──────────
项目
  当前项目
  进行中的任务
  已完成任务
──────────
自动化
插件
设置
```

桌面工作台采用低干扰深色默认主题，并支持浅色、深色、跟随系统、字号和可访问性设置。视觉目标是克制、清晰、可扫描和高信息密度，不形成日志墙或风险告警墙。

### 5.2 首页 / 新建任务

首页中心是自然语言任务输入，而不是内部 command 表单。它展示：当前项目、协同模式、推荐或已选择的成员、任务发送动作和快速开始卡片（分析代码、实现功能、审查修复、研究方案）。

“协同执行”必须显式提示第一阶段只允许的固定受控路径；自由文本可以创建任务草稿，但不得绕开已登记工作项直接获得真实执行能力。

### 5.3 任务详情

任务详情由四个可并列阅读的区域组成：

1. **任务摘要**：目标、总体状态、当前负责人、下一步、是否需要用户介入；
2. **Agent 团队**：成员身份、角色、readiness、当前工作和状态；
3. **协作时间线**：可读的计划、交接、产物、审阅和等待确认事件；
4. **结果与验收**：主摘要、产物卡片、审阅建议和最终业务决定。

内部链路 ID、租约、审计、证据摘要、固定 failure code 仅放在“过程与证据”按需展开区域。它们必须可追溯，但不应抢占默认阅读路径。

### 5.4 Agent 团队与设置

Agent 团队页为每个成员统一展示：名称、图标、角色、安装/发现状态、readiness、能力摘要、当前任务和最近结果。第一版显示 Pi 与 OMP 的真实状态；Codex CLI、Claude Code、Kimi Code 等以统一的“待接入”卡片出现，而不是各自长出专用首页。

设置页面分为：外观、项目偏好、Agent 接入、协作策略、自动化和插件。平台只显示认证状态或“由原 CLI 管理”的说明；不读取、存储或回显凭据。

## 6. 首批 Pi/OMP 试运行团队

| 平台角色 | 首批真实成员 | 允许职责 | 证据来源 |
| --- | --- | --- | --- |
| 规划成员 | Pi | 受控规划与目标拆解 | 既有 planner candidate 与审计 |
| 执行成员 | OMP | 固定单工作项执行 | 既有 execution receipt / artifact |
| 审阅成员 | Pi | 受控审阅与结论 | 既有 review advice 与证据 |
| 协作协调者 | Harness 既有编排 | 状态投影与角色转换 | 既有 chain/read model |

平台显示的协作事件必须从现有权威 read model 或受扫描、版本化的安全投影产生；不得把未受信原始 stdout 直接当作 UI 控制事实。

第一批真实验收使用 Pi/OMP 的已登记、固定测试工作项。验收目标是平台是否正确展示真实成员状态、角色交接、结果摘要、人工决定与失败关闭，而不是扩大执行权限。

## 7. 目标架构与分层

```text
React + TypeScript + Vite + Tailwind + shadcn/ui（展示与本地视图状态）
  -> 版本化的 Agent Deck Read Model（只读、可测试、安全摘要）
  -> Python Harness / Control Plane（唯一的 command authority）
  -> 统一 Agent Adapter Contract
  -> Pi / OMP（首批真实试运行成员）
  -> Codex CLI / Claude Code / Kimi Code（后续适配器）
```

前端是正式候选方向，但实施开始前仍需锁定 Node/npm 版本、依赖来源、离线/缓存策略、构建可复现性和 public scan 策略。任何写操作继续经由 Python 的确定性、版本化结构化 command contract，执行前必须经过 eligibility、approval、expected state、lease 和 audit 检查。

第一实现切片可以先采用确定性 snapshot 与 fixture，随后接入已有 Pi/OMP 只读实时状态。引入服务、桌面容器或持续监听前，必须单独设计并获得授权；不可为了“实时”而静默开放端口或后台服务。

## 7.1 P0 前端数据交接

Python 只通过 `agent-deck/read-model/v1` 生成安全只读投影。显式 `--commit` 仅原子写入固定文件 `.runtime/agent-deck/v1/agent-deck.snapshot.json`；不接受输出路径，不启动服务，不开放 UI dispatch。React 开发工作台只读取该固定安全快照；当前真实 Pi/OMP 启动和最终决定继续由既有 Tk GUI 严格结构化信封完成。

固定快照只释放已有安全 read model 中的项目、成员状态、已登记工作卡、链路状态和证据摘要。它不包含原始 prompt、stdout/stderr、会话引用、绝对路径、凭据或未受信事件文本。

## 8. 统一 Agent Adapter 展示模型

平台层统一使用以下概念，具体 transport 由 adapter 解释：

```text
AgentProfile
  id / display_name / icon / source_kind
  discovery_status / readiness / stale_at
  capabilities[] / supported_roles[]
  native_session_summary (optional)
  current_assignment (optional)
  credential_owner = "native_cli" | "system" | "not_required"

TaskProjection
  task_id / project_id / goal_summary / lifecycle
  team[] / current_owner / next_action
  timeline[] / artifacts[] / review_summary
  human_decision_state / evidence_summary
```

第一阶段只要求 `AgentProfile` 的 Pi/OMP 真实投影；其他 Agent 可以只有稳定身份和 `not_integrated` 状态。不得伪造其 readiness、模型、session 或能力。

## 9. 分阶段路线

### P0 — Agent Deck 工作台基础（本阶段）

- 正式确定产品语言、页面架构和前后端边界；
- 建立 React/Vite/shadcn 的可复现前端工程与中文应用壳；
- 建立版本化只读 Agent Deck snapshot；
- 显示 Pi/OMP 真实状态和统一 Agent 卡片；
- 从固定 Pi/OMP 试运行链路投影可读任务详情、协作时间线和验收入口；
- 不新增自由真实执行能力。

### P1 — 统一任务收件箱与团队接入

- 将已登记工作卡转换为用户可读任务模板；
- 设计 Codex CLI、Claude Code、Kimi Code 的只读发现/状态 adapter；
- 在平台中统一显示可用成员与不可用原因；
- 继续保持单工作项、显式启动确认和人工最终决定。

### P2 — 主 Agent 协作提议

- 由受限主 Agent 生成可解释计划、成员分工和验收建议；
- 所有计划、分工和写操作继续需要用户授权或既有受控策略；
- 不宣称“完全自治”，直到取消、恢复、并发、异常处理和更广 adapter contract 都经过独立设计与真实验收。

## 10. P0 验收标准

P0 只有同时满足以下条件才算通过：

1. 用户可在中文 Agent Deck 中创建或选择项目，并进入自然语言任务入口；
2. 用户可在不输入链路 ID、任务 ID、计划 ID 或 Socket ID 的情况下发起一个已登记 Pi/OMP 试运行；
3. Pi 与 OMP 的真实安全状态在统一 Agent 团队视图中正确显示，并在过期或不可用时失败关闭；
4. 试运行任务页按规划、执行、审阅角色展示真实状态转换、交接和安全摘要；
5. 现有不可变证据、审阅建议、通过/要求修改、有限放弃与失败关闭仍可从任务页到达；
6. 前端没有凭据、通用命令、任意文件权限或独立执行 authority；
7. 所有新 schema、边界和 UI 行为都有 pytest 或前端自动化测试，并完成真实 Pi/OMP GUI 验收；
8. 构建、public scan、doc maintenance、`doctor` 和受控写入回归均通过。

## 11. 风险与决策门

- **前端供应链风险**：在安装 npm 依赖前锁定版本、来源和可复现构建策略；
- **实时数据边界**：先用 snapshot，后续任何监听、IPC 或服务必须单独设计；
- **用户期望与真实能力差**：UI 必须把“草稿”“已登记可执行”“等待授权”“实际运行”区分清楚；
- **跨 Agent 伪互通**：仅在 adapter 有真实、受验证能力时显示协作；不得靠拼接终端文本伪造共享记忆；
- **产品偏航**：每一个 P0 任务必须让用户更接近“发布目标、观察团队、验收结果”的主路径，否则不进入本阶段。

## 12. 实施前审阅清单

用户审阅本文件时，确认：

- P0 是否以 Agent Deck 工作台而非底层取消/恢复能力为主线；
- Pi/OMP 是否可作为首批真实试运行成员；
- React + TypeScript + Vite + Tailwind + shadcn/ui 是否继续作为 P0 正式候选技术栈；
- 第一版是否只接入真实只读状态与固定已登记试运行，而不开放泛化 CLI 执行；
- P1/P2 的顺序是否符合“先看见团队，再扩展接入，再增强主 Agent”的优先级。
