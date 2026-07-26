# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

一个可审计的多 Agent 协作主控台。Kimi Code、Claude Code、OMP/Pi 和 QwenPaw Agent 是可替换的“插头”；项目提供统一“插座”、任务拆分、能力路由、交接、审阅、证据和操作边界，让用户最终能在一个看板里观察和控制它们协作。

## 当前状态

项目已完成 Stage 75，当前具备：

- 统一 Agent socket registry 与 capability routing；
- 可校验的多 Agent collaboration plan，包含 work item、依赖、handoff、artifact 和 review gate；
- 只读 Control Panel，展示协作计划、Agent 分工、派发资格和阻塞原因；
- 单 work item dispatch proposal 与 ACP runner readiness evidence 基础；
- policy、task/event/run/approval/artifact read model 和审计边界。

目前看板还不能启动真实 Kimi、Claude 或 OMP 协作。下一产品里程碑是可用协作看板与 fixture-backed 端到端演示，而不是继续扩展底层探针。

底层仍保留两项受限 Windows 真实执行能力：fixed Git status 与 fixed Pi print。两者都经过显式授权、固定参数、machine-local lease、执行审计和 Windows Job Object 进程树回收；它们是安全基础设施，不是产品主线。

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
- [`docs/123-multi-agent-control-hub-current-state-and-stage75-gate.md`](docs/123-multi-agent-control-hub-current-state-and-stage75-gate.md)：多 Agent 主控台目标、现状、缺口与方向决策。
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
