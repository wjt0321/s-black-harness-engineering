# 10 — 当前 CLI 使用入口

> 状态：当前参考；完整历史命令与阶段性示例见 `archive/10-cli-poc-usage-legacy-2026-07-29.md`。
> 目标：提供日常恢复、诊断、Agent Deck 观察与受控任务登记的最小入口，而不是重复历史阶段手册。

## 1. 快速恢复

```powershell
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
python -m agent_runtime.cli --help
```

新会话随后依次阅读：

1. `docs/000-stage-digest.md`；
2. `docs/00-index.md`；
3. 当前任务直接相关的事实源；
4. `tasks/handoff-2026-07-29-stage97.md`。

## 2. 常用只读命令

```powershell
# 项目健康检查
python -m agent_runtime.cli doctor

# 文档恢复上下文
python -m agent_runtime.cli docs context --json

# Agent Deck 当前安全快照：预览或原子写入 .runtime/，不派发 Agent
python -m agent_runtime.cli agent-deck snapshot --evaluated-at 2026-07-29T12:00:00Z --json
python -m agent_runtime.cli agent-deck snapshot --evaluated-at 2026-07-29T12:00:00Z --commit --json

# 查询既有任务账本
python -m agent_runtime.cli task list --json
python -m agent_runtime.cli orchestration overview --json

# 查询已登记的外部 Agent 状态与固定工作收件箱
python -m agent_runtime.cli orchestration external-agent status --json
python -m agent_runtime.cli orchestration control-panel snapshot --json
```

以 `--help` 作为具体参数的唯一权威来源：

```powershell
python -m agent_runtime.cli agent-deck --help
python -m agent_runtime.cli orchestration execution --help
```

## 3. Agent Deck 正式任务登记

浏览器内的任务草案只保存在当前会话；它不是执行授权。要将一个目标登记为 Harness 正式任务，使用固定入口：

```powershell
# 只预览：不写入账本、不启动 Agent
python -m agent_runtime.cli agent-deck mission submit `
  --goal "为 Agent Deck 整理下一阶段的结构化规划需求" `
  --dry-run --json

# 正式登记：只写入一项任务与一条 created 事件；不启动 Pi、OMP 或协作链路
python -m agent_runtime.cli agent-deck mission submit `
  --goal "为 Agent Deck 整理下一阶段的结构化规划需求" `
  --commit --json
```

该入口固定执行以下约束：

- 目标必须是单段、最多 500 字符 / 1 KiB 的文本，并先通过敏感信息扫描；
- task ID、event ID、账本位置和初始状态均由 Harness 生成；
- `--dry-run` 与 `--commit` 必须二选一；
- `--commit` 复用已有 task + `created` event A+B 事务、写后校验与失败回滚；
- 不接受路径、命令、argv、cwd、env、Agent 工具或宿主控制参数；
- 登记后只进入“等待主控 Agent 规划”收件箱，**不会**自动启动 Agent 或执行链路。

## 4. 受限真实执行

当前仅有三类真实执行能力；它们与 Agent Deck 的任务登记是分离的控制面能力：

| 能力 | 固定范围 | 必要条件 |
|:---|:---|:---|
| Git status | `git status --short --branch` | 显式 `--commit`、本机信任绑定、租约与审计 |
| Pi print | `pi --print --no-session --no-tools <prompt>` | 显式 `--commit`、固定运行时、租约与审计 |
| Pi/OMP 单工作项与三角色串行链路 | 已登记工作、固定角色拓扑 | 预检、一次性确认、宿主空闲、租约、审计、证据与最终人工决定 |

不要从此页复制历史阶段命令来扩大权限。真实执行的当前事实源与细节见：

- `111-pi-controlled-dry-run-print-implementation.md`；
- `archive/136-stage87-single-work-item-controlled-execution.md`；
- `archive/138-stage89-bounded-planner-executor-review-design.md`；
- `archive/140-stage91-gui-structured-approval-inbox.md`；
- `archive/146-stage96-controlled-mission-intake.md`。

## 5. 验证与发布前检查

```powershell
python -m pytest tests -q
python -m pytest tests/test_controlled_write_regression.py -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
```

文档改动还需在 Git Bash 中运行：

```bash
bash .githooks/pre-commit
```

## 6. 不变安全边界

- 不读取或回显 `.env`、token、keyring、私钥等凭据；
- 不开放通用 shell、任意 argv/cwd/env、网络 adapter、长期服务或数据库；
- 不由 Harness 启动、关闭或重启外部 Agent；
- 不自动重试、并行派发、运行中取消、恢复执行或自治循环；
- 前端快照、浏览器草案、预览和 readiness 都不是执行权限。

历史版本的完整 CLI 手册已原样归档：`archive/10-cli-poc-usage-legacy-2026-07-29.md`。需要追溯旧 command surface、迁移过程或历史 smoke 时再读取它。
