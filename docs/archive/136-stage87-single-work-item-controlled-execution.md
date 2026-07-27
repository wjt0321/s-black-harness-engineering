# 阶段 87：单工作项受控执行闭环

> 状态：已完成并归档
> 日期：2026-07-27
> 归档实施计划：`plans/2026-07-27-stage87-single-work-item-controlled-execution.md`

## 目标与结果

阶段 87 将阶段 86 的只读在线状态推进为第一个真实、严格受限的外部智能体执行闭环：用户先预览并一次性确认一个工作项，Harness 再把它派发到用户已经打开的 Pi 或 OMP 会话，回收有界结果并闭合审计。

Pi 与 OMP 的真实验收均已通过。本阶段没有开放通用命令、任意参数、网络监听、自动重试、并行派发或 Agent 工具权限，也没有由 Harness 启动或关闭宿主进程。

## 已实现能力

- 新增版本化单工作项执行请求、独立派发绑定和固定项目级信箱协议；
- 只允许 `pi-local`、`omp-local` 两个审阅目标，固定请求/结果路径，不接受路径、参数或环境变量覆盖；
- 预览不写入，提交必须同时提供 `--commit` 和预览产生的一次性确认摘要；
- 确认摘要绑定任务、协作计划、工作项、目标、指令、输入产物、状态证据、超时和结果上限；
- 复用全局执行租约，started audit 必须先于派发，每次尝试只能有一个 terminal audit；
- 宿主扩展只允许调用 `sendUserMessage`，禁止 `exec`、`setActiveTools`、启动进程、网络、自动重试和并行派发；
- 派发前要求活动工具列表为空且宿主会话空闲，忙碌或工具未关闭时失败关闭；
- 原始结果仅进入 `.runtime/`，经过大小校验与敏感信息扫描后才形成公开投影；
- 中文控制面板增加单工作项预览、确认要求、执行状态和安全结果摘要。

## OMP 17.0.8 兼容结论

OMP 会自动发现 Claude、OpenCode、Codex、Cursor、Gemini、VS Code、Windsurf 和通用配置中的 MCP。`--no-tools` 只关闭内置工具，不保证关闭 MCP 工具；`--no-extensions` 在 17.0.8 中还会错误地忽略显式 `--extension`。

本机 OMP 通过 `PI_CODING_AGENT_DIR` 使用项目本地 `.runtime/pi-agent`，因此 OMP 全局智能体目录中的禁用名单不会作用于当前项目。验收采用项目本地隔离：

- `.runtime/pi-agent/mcp.json` 只保存 MCP 禁用名称，不含凭据；
- `mcp.enableProjectConfig=false`；
- 启动命令为 `omp --no-tools --extension .omp/extensions/s-black-live-status.ts`；
- 未修改 Claude、OpenCode、Codex 或 OMP 的全局 MCP 配置。

另修复了 OMP 的消息语义差异：显式 `deliverAs: followUp` 在空闲状态只排队而不启动轮次。最终实现先确认宿主空闲，再调用不带 `deliverAs` 的固定 `sendUserMessage`；宿主忙碌时返回 `host-session-busy`，不会插入现有轮次。

## 真实验收

### Pi

- 请求：`stage87-pi-smoke-003`
- 目标：`pi-local`
- 结果：`Pi 阶段87受控执行验收通过。`
- 输出摘要：`sha256:024f73b5fbf4caa590b61388dee946e5b5892a27a4adf856f34320fcac2e36e6`
- 审计：`attempt-20260727-005`，`closed_succeeded`

### OMP

- 请求：`stage87-omp-smoke-003`
- 目标：`omp-local`
- 结果：`OMP 阶段87受控执行验收通过。`
- 输出摘要：`sha256:e45a0293a85e4d1ab86b1ac2bfd4ef472cddb5fd8e4d4e99fc36dfbdbb83b7c2`
- 审计：`attempt-20260727-011`，`closed_succeeded`

实现期间发现的审计字段兼容、缺失超时字段、OMP 活动 MCP 工具和 OMP follow-up 排队问题均已失败关闭并修复；相关失败尝试均已有唯一终端审计，不存在未闭合执行。

## 继续保持的边界

- Harness 不启动、关闭或重启 Pi/OMP；
- 不开放任意 shell、argv、cwd、env、网络或文件工具；
- 不自动重试、不并行派发、不跨 Agent 转发、不形成自治循环；
- 不把只读状态、预览或人工计划确认解释为执行授权；
- 不接入 QwenPaw，不扩展到第二个工作项、事件流、产物或审阅闭环。

## 后续方向

下一候选是将当前“最终文本结果”扩展为真实事件、产物和人工审阅结果回收，再形成规划者、执行者、审阅者闭环。任何扩展仍需独立设计和用户授权。
