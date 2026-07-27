# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 85 外部智能体状态采集方案设计评审已归档
- commit：以当前 Git HEAD 为准
- 日期：2026-07-27
- 活跃 `docs/` 只保留当前架构、规范、命令行参考和下一里程碑入口；阶段 85 归档后仍为 29 份。

## 当前阶段

- **阶段 85 — 已完成并归档：选定“宿主内被动采集并原子发布”方案，冻结发布、可信身份、失败处理、测试要求和实施停止线。**
- 阶段 85 归档事实源：`archive/134-stage85-external-agent-status-collection-design-review.md`。
- 下一里程碑入口：`135-next-milestone-real-status-integration.md`。
- 下一里程碑目标是让 OMP/Pi 的真实观察状态出现在中文控制面板上，不再拆分纯设计小阶段。
- 当前尚未开始实施状态采集器，也没有创建正式状态快照或连接 ACP。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`。
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`。

共同边界：显式 `--commit`、单机租约、固定参数、有界输入输出、started/terminal audit、Windows Job Object 进程树回收。阶段 85 不改变这两项能力。

## 仍未开放

- 通用 shell、任意 adapter execution、POSIX fallback；
- 网络 adapter、服务、数据库、自动后台执行；
- Pi read/write/edit/bash 工具；
- 未经独立设计评审和授权的第三个真实操作；
- 真实状态采集器、固定状态命令或 ACP 主动探测；
- 真实外部智能体 readiness、session 或智能体间调用；
- 真实 approval ledger、work-item dispatch、streaming event/artifact/review 回收；
- 自动 Planner -> Executor -> Reviewer 闭环。

## 下次恢复顺序

1. `README.md`
2. `docs/00-index.md`
3. `docs/135-next-milestone-real-status-integration.md`
4. `docs/130-gui-first-external-agent-control-plane-target.md`
5. `docs/archive/134-stage85-external-agent-status-collection-design-review.md`（核对状态采集设计）
6. `docs/archive/133-stage84-bounded-atomic-snapshot-reader-implementation.md`（核对读取器实现）
7. `docs/47-orchestration-hub-vision.md`
8. `docs/48-adapter-runtime-interface.md`
9. `docs/49-capability-routing-model.md`
10. `docs/21-controlled-write-boundaries.md`
11. `tasks/handoff-2026-07-27.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步做什么

- **阶段 86 — OMP/Pi 真实状态接入与中文控制面板展示（待授权启动）。**
- 一次性完成真实宿主接口核验、状态采集器、原子快照、读取器联调、中文控制面板接入和真实只读 smoke。
- 不创建会话、不调用模型、不派发任务，也不新增第三个 Harness 真实执行操作。

## 收口验证

本次归档和推送前必须通过：阶段 82-85 契约专项、中文阶段解析回归、全量 pytest、public scan、doctor、docs context、Markdown 链接/路径审计、活跃文档数、pre-commit 与 diff check。
