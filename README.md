# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="160">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

> 一套轻量的 Agent Runtime / Harness Orchestrator，用来沉淀规则门禁、任务账本、Agent 注册表、工具适配器边界和完成验证流程。

## 这个项目是什么

`s-black harness engineering` 是一个 Agent 工程基础设施项目。

它的目标不是替代聊天宿主，也不是先做 UI，而是把 Agent 做事时最容易失控的部分单独抽出来：

- 规则检查
- 任务账本
- Agent 注册表
- 工具适配器边界
- 完成验证
- 受控写入流程

最终希望形成一层**小型、可审计、可迁移**的 Runtime，让 QwenPaw 只是未来可接入的宿主/适配器之一，而不是唯一边界。

## 当前项目到了哪里

当前仓库已经从“只读检查 CLI”推进到了“最小受控写入 Runtime”。

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
3. `docs/10-cli-poc-usage.md`
4. `docs/21-controlled-write-boundaries.md`
5. `docs/45-runtime-event-import-strict-freeze-mode.md`
6. `docs/46-release-notes-runtime-event-import-strict-freeze.md`

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

先把规则、任务模型、Agent 注册表、适配器边界和完成验证想清楚，再逐步放开可执行 Runtime 能力。
