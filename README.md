# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

轻量、可审计的 Agent Runtime / Harness Orchestrator。它把规则门禁、任务账本、能力路由、受控写入、执行审计和宿主适配从聊天应用中抽离，形成可测试的本地控制面。

## 当前状态

项目已完成 Stage 62，并具备两项受限的 Windows 真实执行能力：

- fixed Git status：仅允许固定 `git status --short --branch`。
- fixed Pi print：仅允许固定 `pi --print --no-session --no-tools <prompt>`，真实 DeepSeek smoke 已通过。

两者都要求显式 `--commit`，并经过 machine-local lease、固定参数、边界校验、started/terminal audit 和 Windows Job Object 进程树回收。Pi 输出只公开 digest、字节数和审计证据，不公开 prompt、模型原文或凭据。

此外，仓库已具备：

- policy、registry、task/event/run/approval/artifact read model；
- dry-run、plan hash、受控 ledger 追加与失败回滚；
- capability routing、workflow/profile/contract 校验；
- 静态只读 Control Panel 与 one-shot host/consumer 管道；
- Pi preflight、有限 approval 与 postflight projection 基础设施。

## 安全边界

当前仍然不提供：

- 通用 shell 或任意 adapter execution；
- POSIX 真实执行；
- 网络 adapter、长期服务、数据库或自动后台任务；
- Pi read/write/edit/bash 工具授权；
- 静默读取 `.env`、token、keyring 或其他凭据文件；
- 未经设计和授权的第三个真实 operation。

## 快速开始

```bash
pip install -e .[dev]
python -m agent_runtime.cli doctor
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli --help
```

常用验证：

```bash
python -m pytest tests -q
python tools/public_scan.py
python -m agent_runtime.cli doctor
git diff --check
```

完整 CLI 参数见 [`docs/10-cli-poc-usage.md`](docs/10-cli-poc-usage.md)。

## 文档入口

- [`docs/000-stage-digest.md`](docs/000-stage-digest.md)：当前状态和恢复顺序。
- [`docs/00-index.md`](docs/00-index.md)：按主题导航。
- [`docs/02-roadmap.md`](docs/02-roadmap.md)：已完成能力包与下一候选。
- [`docs/111-pi-controlled-dry-run-print-implementation.md`](docs/111-pi-controlled-dry-run-print-implementation.md)：当前最新真实执行事实源。
- [`docs/archive/`](docs/archive/)：完整历史设计、计划、smoke 与 release notes。

## 仓库结构

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/` | Python 包、CLI 和控制面逻辑 |
| `tests/` | pytest 测试 |
| `docs/` | 当前架构、规范与使用入口 |
| `docs/archive/` | 已完成阶段和历史快照 |
| `adapters/` / `agents/` / `policies/` | 示例注册表与规则 |
| `tasks/` | 示例 ledger、handoff 与推进记录 |
| `integrations/` | 宿主集成示例 |

版本和阶段治理见 [`docs/64-versioning-governance.md`](docs/64-versioning-governance.md)。
