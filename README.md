# s-black harness engineering

<p align="center">
  <img src="assets/logo-256.png" alt="s-black harness engineering logo" width="140">
</p>

<p align="center">
  <strong>中文</strong> · <a href="README.en.md">English</a>
</p>

一个可审计的多 Agent 协作主控台。Kimi Code、Claude Code、OMP/Pi 和 QwenPaw Agent 是可替换的“插头”；项目提供统一“插座”、任务拆分、能力路由、交接、审阅、证据和操作边界，让用户最终能在一个看板里观察和控制它们协作。

## 当前状态

项目已完成 Stage 78，当前具备：

- 统一 Agent socket registry、capability routing 与显式角色绑定；
- 可校验的多 Agent collaboration plan，包含 work item、依赖、handoff、artifact 和 review gate；
- 中文优先的 Control Panel、人工协作 fixture、工作项泳道和 handoff/artifact 时间线；
- 浏览器内存人工计划编辑器，以及结构、依赖、Agent 插座绑定和审阅要求校验；
- `editing -> validated -> operator_confirmed` 人工确认状态机；
- 用户主动复制或下载符合 collaboration plan v1 的候选 JSON；
- 单 work item dispatch proposal、ACP readiness evidence 基础和完整审计边界。

看板仍不能启动真实 Kimi、Claude 或 OMP 协作。校验、人工确认、复制和下载都不会授予派发权，始终保持 `dispatch_eligible=false`、`execution=not_executed`。下一产品里程碑是 **Stage 79 协作运行状态模型设计**：先定义开始、取消、重试、审阅、交接、阻塞恢复和 artifact 回收，不调用 Agent。

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
- [`docs/126-stage78-manual-confirmation-and-controlled-export.md`](docs/126-stage78-manual-confirmation-and-controlled-export.md)：当前人工计划校验、人工确认与受控导出事实源。
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
