# 0002 — 延后采用 shadcn 的前端方向预留

> 状态：Reserved / P0 Candidate（正式候选，实施待设计审阅）
> 日期：2026-07-29
> 约束：阶段 94 已将本方向纳入 Agent Deck P0 候选；本文本身不授权扩大执行边界

## 背景

项目长期目标是 GUI-first、本地优先的外部 Agent Harness / Control Plane。当前 `build/` 中的静态 Control Panel 仍是视觉与信息架构原型，权威状态、资格判断、审批语义、审计和真实执行边界继续由 Python control plane 持有。

为避免未来建设 live GUI 时重新讨论基础技术方向，预留以下候选方案：

```text
React + TypeScript + Vite + Tailwind CSS + shadcn/ui
```

如后续确有桌面封装需求，可在 Web UI 与 command contract 稳定后另行评估 Tauri；桌面壳不得拥有或复制执行授权逻辑。

## 为什么保留这个方向

- shadcn/ui 以项目内组件源码为主要使用方式，便于审计、裁剪和形成自有设计系统；
- 适合控制台常见的表格、状态标记、侧栏、详情面板、审批对话框和命令搜索等高密度界面；
- React + TypeScript 有利于为 read model 和结构化 command 建立显式类型边界；
- Vite 适合本地 GUI 的静态构建与后续 WebView 封装，不要求现在引入服务端渲染；
- 可将简体中文 UI、可访问性和状态语义统一沉淀为可复用组件，而不是继续扩大 Python HTML 字符串模板。

这只是候选方向，不表示已完成技术选型。实施前仍需根据当时的维护状态、供应链风险、构建可复现性和桌面封装需求重新评审。

视觉与体验层应遵循 `docs/130-gui-first-external-agent-control-plane-target.md` 的“未来体验与视觉方向预留”：参考高完成度消费级 Agent 产品的克制、清晰和协作可视化品质；静态产品叙事页与权威运行时控制面分层；不复制任何第三方的品牌、代码、素材或具体信息架构。

## 推荐的未来分层

```text
shadcn / React 展示层
    -> 确定性、版本化的 Read Model
    -> Python Harness Control Plane
    -> approval / policy / lease / audit
    -> fixed operation 或统一 external Agent adapter contract
```

前端负责展示、筛选、排序、搜索和本地视图状态。Python control plane 继续唯一负责：

- 当前状态与 stale target 判定；
- action eligibility 与 execution authorization；
- approval evidence、idempotency 和 expected state 校验；
- ledger、audit、lease、回滚和 terminal result；
- fixed operation 与 external Agent adapter 的实际调用边界。

## 不得跨越的边界

未来即使采用本方案，也不得因此：

- 暴露任意 `argv`、`cwd`、`env` 或通用 shell；
- 让浏览器或桌面壳直接写 ledger、审计或运行态文件；
- 从 UI 读取 `.env`、token、keyring、私钥等凭据；
- 把 preview、readiness、fixture approval、`action_eligible=true` 或可见按钮解释为执行授权；
- 绕过写前校验、写后校验、失败回滚、lease 或 started/terminal audit；
- 静默增加网络 adapter、长期服务、后台执行或第三个真实 operation；
- 为不同 Agent 建立专用 UI 主流程，绕开统一 adapter/socket contract。

用户实际看见和操作的界面默认使用简体中文。无法合理翻译的协议名、Agent 名称和 Socket ID 可保留原文，但须紧邻中文解释。

## 建议的延后实施顺序

只有在产品主线推进到 live GUI 时，才重新打开此决策：

1. **只读原型**：独立 `frontend/` 工程，仅消费已提交 fixture 或确定性 snapshot JSON，不访问网络、不执行命令；
2. **Read Model 集成**：冻结版本化 schema，让新前端与现有静态 Control Panel 消费同一权威投影；
3. **结构化 Command Contract**：在 approval authority、idempotency、expected state 和 terminal audit 完成后，才设计最小写操作通道；
4. **桌面封装评估**：最后再评估 Tauri 或其他容器，不同时引入 shell、文件系统、自动更新等高权限插件。

现有 `agent_runtime/orchestration_control_panel.py` 在迁移期应作为兼容、回归和离线恢复入口保留，不宜一次性删除或重写。

## 重新评审触发条件

满足以下条件时，可以把本预留方向升级为正式设计：

- external Agent adapter contract 和 GUI 所需最小 live read model 已冻结；
- 至少一个外部 Agent 的只读 live status 路径已验证，或已有明确的 GUI 集成需求；
- Node/npm 构建链的版本锁定、离线/缓存策略、public scan 和供应链检查已形成方案；
- 已定义前端不得持有执行权限的 IPC、RPC 或本地 API 边界；
- 用户明确授权一个独立的 GUI 设计或实现 Stage。

## 当前结论

阶段 94 已将 React/Vite/shadcn/ui 升级为 Agent Deck P0 的正式展示层候选，详见 `../docs/143-agent-deck-platform-mvp.md` 与完整设计稿。用户审阅设计并确认实施计划前，仍不创建 `frontend/`、不安装 npm 依赖、不启动服务，也不扩大任何真实执行边界。
