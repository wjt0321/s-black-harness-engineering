# AGENTS.md

本文件是仓库内编码 Agent 的最小操作契约。项目文档以中文为主；不要把历史阶段流水继续堆回本文件。

## 快速恢复

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

依次阅读：

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. 当前任务直接相关的 1-2 份事实源
4. `tasks/handoff-2026-07-25.md`（仅需恢复 Stage 62 细节时）

不要先遍历整个 `docs/`、`docs/archive/` 或 `tasks/progress.md`。

## 当前能力与边界

项目是 Python 3.11+ 的本地 Agent Runtime / Harness 控制面。Stage 62 已完成。

允许的真实执行仅有：

- Windows fixed Git status：固定 `git status --short --branch`；
- Windows fixed Pi print：固定 `pi --print --no-session --no-tools <prompt>`。

两者都必须显式 `--commit`，并保持 lease、固定参数、审计、输出约束和进程树回收。除非用户另行授权且先完成独立设计，禁止新增第三个 operation、通用 shell、POSIX fallback、网络 adapter、长期服务、数据库或 Pi 工具权限。

MUST：

- 不读取或回显 `.env`、token、keyring、私钥等凭据；
- secret scan 只释放规则 id 和安全提示；
- 写前校验、写后校验、失败回滚；
- 保持 path containment、bounded input/output 和 fail-closed；
- 真实执行必须先写 started audit，结束后写唯一 terminal audit；
- 修改共享执行边界时运行全量测试和对应回归。

NEVER：

- 用任意 argv/cwd/env override 绕过 fixed operation；
- 把 preview/read model 解释为执行权限；
- 覆盖已有 ledger 或放宽 reserved audit event writer；
- 静默扩大网络、文件写入或宿主权限；
- 删除历史文档；已完成内容用 `git mv` 归档。

## 开发约定

- 优先标准库和现有 helper；最小 diff，不做无关重构。
- 所有 CLI 入口必须支持确定性 JSON 输出和稳定 failure code。
- 新增非平凡逻辑必须有 pytest。
- 修改受控写入或执行链时，先读对应模块和测试，保持现有事务与审计语义。
- `.runtime/` 是机器本地、gitignored 运行态，不得提交凭据或 smoke 原文。

常用入口：

| 路径 | 用途 |
|:---|:---|
| `agent_runtime/cli.py` | CLI 入口 |
| `agent_runtime/orchestration_contract.py` | 对外能力清单 |
| `agent_runtime/execution_*` | lease、trust、audit 与执行基础设施 |
| `agent_runtime/orchestration_*_execution.py` | 固定 operation 编排 |
| `tests/` | 行为与边界契约 |
| `docs/10-cli-poc-usage.md` | CLI 参考 |
| `docs/21-controlled-write-boundaries.md` | 写入边界 |
| `docs/111-pi-controlled-dry-run-print-implementation.md` | 当前 Pi 执行事实源 |

## 验证契约

代码或 schema 变更至少运行：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

受控写入变更额外运行：

```bash
python -m pytest tests/test_controlled_write_regression.py -q
```

文档变更检查索引、相对链接和 `docs/` 活跃文档数；Git Bash 可运行：

```bash
bash .githooks/pre-commit
```

测试、smoke 或外部发布未实际成功时，不得声称完成。commit/push 需要用户本次明确授权。

## 文档治理

- `README*`：面向使用者，只保留当前状态、边界、快速开始和入口。
- `AGENTS.md`：只保留操作契约，不记录逐 Stage 历史。
- `docs/000-stage-digest.md`：单屏恢复当前断点。
- `docs/00-index.md`：按主题导航，不逐文件写摘要。
- `docs/02-roadmap.md`：只列能力包和下一候选。
- 已完成设计、实施计划、smoke 与旧长版入口归档到 `docs/archive/`；完整历史仍可由 Git 与 archive 追溯。
