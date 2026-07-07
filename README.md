# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

> 一套轻量的 Agent Runtime / Harness Orchestrator，用来沉淀规则门禁、任务账本、Agent 注册表、工具适配器边界和完成验证流程，并逐步演进成多 Agent、多工具、多渠道的中枢运行台。

## 这个项目是什么

`s-black harness engineering` 是一个 Agent 工程基础设施项目。

它的目标不是替代聊天宿主，也不是先做 UI，而是先把 Agent 做事时最容易失控、最需要统一控制的部分单独抽出来：

- 规则检查
- 任务账本
- Agent 注册表
- 工具适配器边界
- 完成验证
- 受控写入流程
- 能力路由与中枢编排基础

最终希望形成一层**小型、可审计、可迁移**的 Runtime / Control Plane，让 QwenPaw 只是未来可接入的宿主/适配器之一，而不是唯一边界。

## 全景图

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

一句话理解：

- **门禁 / 账本 / 受控写入** 是这个项目的安全内核
- **统一接入 / 能力路由 / 状态控制 / 未来 UI** 才是这个项目最终要长成的中枢台主体

## 当前项目到了哪里

当前仓库已经从“只读检查 CLI”推进到了“最小受控写入 Runtime”，并开始补“中枢台后端”的总蓝图。

已落地的主线能力包括：

- 结构校验、密钥扫描、路径检查、action preflight
- registry / policy / ledger 查询与校验
- adapter execution envelope 的 plan / validate / inspect / gate check
- `runtime draft export --dry-run / --commit`
- `runtime event append --dry-run / --commit`
- `runtime task create --dry-run / --commit`
- `runtime event import --dry-run / --commit`
- `runtime event import --expected-plan-hash` 一致性冻结
- `runtime event import --require-dry-run` strict freeze mode
- controlled write regression 覆盖
- 中枢台总蓝图、adapter 接口、capability routing、control plane state 文档主线

## 当前边界

当前 Runtime 仍保持保守边界：

- 不执行真实 adapter
- 不访问网络
- 不发送消息
- 不读取 `.env` / credential / token / keyring
- 不做 UI 或后台服务
- 不静默扩张写权限

已实现的写入也都属于**受控写入**：只允许项目内安全路径、显式命令触发、写前校验、写后校验、失败回滚。

## 快速开始

```bash
python -m agent_runtime.cli doctor
python -m agent_runtime.cli check text --text hello
python -m agent_runtime.cli check path ./docs/06-adapter-layer.md --read
python -m agent_runtime.cli agents list
python -m agent_runtime.cli adapters list
python -m agent_runtime.cli policies list
```

更多 CLI 用法见 `docs/10-cli-poc-usage.md`。

## 推荐阅读

如果你第一次进入这个仓库，建议按这个顺序看：

1. `docs/00-index.md`
2. `docs/01-vision-and-boundaries.md`
3. `docs/02-roadmap.md`
4. `docs/47-orchestration-hub-vision.md`
5. `docs/48-adapter-runtime-interface.md`
6. `docs/49-capability-routing-model.md`
7. `docs/50-control-plane-state-model.md`
8. `docs/10-cli-poc-usage.md`
9. `docs/21-controlled-write-boundaries.md`

如果你只想看完整进度账本：

- `tasks/progress.md`

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `docs/` | 架构、路线图、协议说明、阶段文档 |
| `policies/` | Policy schema 和样例 policy |
| `agents/` | Agent 注册表 schema 和样例注册表 |
| `adapters/` | 工具适配器设计与相关 schema |
| `tasks/` | 任务账本 schema、样例、进度和交接记录 |
| `logs/` | 后续 Runtime 运行日志 |
| `decisions/` | 架构决策记录 |
| `notes/` | 每日推进笔记 |
| `assets/` | 项目视觉资产 |

## 持续集成

push 和 pull_request 到 `main` 分支时，GitHub Actions 会在 Python 3.11 和 3.12 上运行：

- `pytest`
- `doctor`
- ledger CLI smoke checks
- `public_scan`

详见 `.github/workflows/ci.yml`。

## 推进原则

保持小步、可审查、可回滚。

先把规则、状态模型、Agent 注册表、适配器边界和受控写入内核打稳，再逐步补齐统一接入、能力路由、控制面状态和未来 UI 可操作边界。
