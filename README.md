# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

> 一套轻量的 Agent Runtime / Harness Orchestrator，用来沉淀规则门禁、任务账本、Agent 注册表、工具适配器边界和完成验证流程。

## 这个项目是什么

`s-black harness engineering` 是一个长期工程项目，目标是把 Agent 调度、规则检查、任务记录、工具适配和交付验证，从单一宿主框架中逐步抽象出来，形成一套小型、可审计、可迁移的运行层。

它不是要立刻替代 QwenPaw。第一阶段只做文档、协议、schema、样例和边界设计，在设计稳定前不接入真实执行链路。

## 与 QwenPaw 的关系

[QwenPaw](https://github.com/agentscope-ai/QwenPaw) 是一个公开的多 Agent 桌面/运行框架项目，也是本项目早期实践和日常使用的重要宿主环境。

`s-black harness engineering` 会把 QwenPaw 视为未来可接入的宿主/适配器之一，而不是要替代它。这个仓库当前关注的是独立的规则、账本、注册表和适配器边界设计。

## 当前状态

- 阶段：只读 CLI POC + Adapter execution envelope 检查链路已可运行
- 创建日期：2026-07-02
- 当前实现：最小只读 CLI，可做结构校验、密钥扫描、路径检查、action preflight、registry 查询、ledger 校验，以及 adapter envelope 的 plan / validate / inspect / approval check / response check / gate check，和 task + adapter envelope 的 runtime plan（含 `--draft-json` envelope 草案输出） / runtime draft validate / runtime draft inspect / runtime gate check / runtime check-ledger
- 当前边界：adapter 链路与 runtime plan / runtime draft validate / runtime draft inspect / runtime gate / runtime ledger audit 仍只读，不执行真实外部动作

## 持续集成

push 和 pull_request 到 `main` 分支时，GitHub Actions 会在 Python 3.11 和 3.12 上运行 `pytest`、`doctor`、ledger CLI smoke checks 和 `public_scan`。详见 `.github/workflows/ci.yml`。

## 快速开始

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
```

更多用法见 `docs/10-cli-poc-usage.md`。

## 初始范围

这套 Runtime 未来预计覆盖：

1. **Agent 注册表**：记录 Agent 的能力、边界、工作区和委派关系。
2. **任务路由**：判断一个任务应该交给哪个 Agent 或工具处理。
3. **规则门禁**：在外发、删除、改配置、push 等高风险动作前做检查。
4. **工具适配器**：把 QwenPaw、Kimi、Claude、OMP、Shell、飞书、GitHub、WebBridge 等封装成统一接口。
5. **任务状态账本**：记录任务从计划、执行、阻塞、失败到完成的过程。
6. **完成验证**：任务完成前必须有证据，避免只靠口头结果宣称完成。
7. **记忆与文档交接**：把关键上下文落到合适的位置，而不是只留在聊天里。

## 第一阶段暂不做什么

第一阶段不做：

- 不替代 QwenPaw
- 不做 UI 或桌面壳
- 不启动长期后台服务
- 不接管现有定时任务
- 不做模型代理或计费系统
- 不在设计稳定前静默执行真实外部操作

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `docs/` | 架构、路线图、协议说明 |
| `policies/` | Policy schema 和样例 policy |
| `agents/` | Agent 注册表 schema 和样例注册表 |
| `adapters/` | 后续工具适配器设计或代码 |
| `tasks/` | 任务账本 schema、样例、进度和交接记录 |
| `logs/` | 后续 Runtime 运行日志 |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

## 当前文档

- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `docs/03-policy-schema.md`
- `docs/04-task-state-model.md`
- `docs/05-agent-registry.md`
- `docs/06-adapter-layer.md`
- `docs/07-policy-task-bridge.md`
- `docs/08-minimal-cli-design.md`
- `docs/09-policy-checker-poc-plan.md`
- `docs/10-cli-poc-usage.md`
- `docs/11-release-notes-v0.1.md`
- `docs/12-adapter-execution-envelope.md`
- `docs/13-release-notes-adapter-envelope.md`
- `docs/14-task-runtime-bridge.md`
- `docs/15-runtime-ledger-audit.md`
- `docs/16-runtime-plan.md`
- `docs/17-runtime-planning-bridge.md`
- `docs/18-release-notes-runtime-planning-bridge.md`

## 推进原则

保持小步、可审查、可回滚。先把规则、任务模型、Agent 注册表、适配器边界和完成验证想清楚，再开始写真正可执行的 Runtime 代码。
