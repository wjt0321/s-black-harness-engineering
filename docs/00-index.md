# 00 — 文档索引

> 先读 `000-stage-digest.md`。这里只按主题导航；已完成阶段在 `archive/`，不逐阶段展开。

## 当前入口

- `../README.md` — 项目定位、当前能力、快速开始。
- `000-stage-digest.md` — 当前断点和恢复顺序。
- `archive/139-stage90-live-chinese-control-panel-read-model.md` — 阶段 90 已验收事实源：实时中文只读图形面板、聚合读取模型与真实 Pi/OMP 图形验收。
- `archive/138-stage89-bounded-planner-executor-review-design.md` — 阶段 89 已验收事实源：一次启动授权后的有限自动串行规划者—执行者—审阅者闭环。
- `archive/137-stage88-external-agent-evidence-and-human-review.md` — 已完成实现事实源：Pi/OMP 真实事件、不可变产物与人工审阅。
- `archive/136-stage87-single-work-item-controlled-execution.md` — 阶段 87 归档事实源：Pi/OMP 单工作项受控执行与真实验收。
- `02-roadmap.md` — 能力包、当前里程碑与下一候选。
- `130-gui-first-external-agent-control-plane-target.md` — 中文图形控制面长期目标、最小可用边界和反偏航检查。
- `10-cli-poc-usage.md` — 完整命令行参数和示例。
- `111-pi-controlled-dry-run-print-implementation.md` — 最新真实执行事实源。
- `113-pi-runtime-binding-implementation.md` — 当前仅绑定审阅证据事实源。
- `MAINTENANCE.md` — 文档治理规则。

## 候选与延后决策

- `../decisions/0002-deferred-shadcn-frontend-direction.md` — 未来 React/Vite/shadcn 图形界面方向预留；当前不授权实现或扩大执行边界。

## 核心模型

- `01-vision-and-boundaries.md` — 愿景与边界。
- `03-policy-schema.md` — 策略结构。
- `04-task-state-model.md` — 任务与事件状态模型。
- `05-agent-registry.md` — 智能体注册表。
- `06-adapter-layer.md` — 适配层。
- `07-policy-task-bridge.md` — 策略与任务桥接。
- `08-minimal-cli-design.md` — 命令行基础设计。
- `12-adapter-execution-envelope.md` — 执行信封。
- `15-runtime-ledger-audit.md` — 账本与审计。

## 运行时与受控写入

- `16-runtime-plan.md` — 运行计划。
- `17-runtime-planning-bridge.md` — 计划桥接。
- `19-runtime-report.md` — 运行报告。
- `21-controlled-write-boundaries.md` — 当前写入与回滚边界。

## 编排控制面

- `47-orchestration-hub-vision.md` — 中枢台愿景。
- `48-adapter-runtime-interface.md` — 适配器运行接口。
- `49-capability-routing-model.md` — 能力路由。
- `50-control-plane-state-model.md` — 控制面状态。
- `51-backend-first-api-boundary.md` — 后端优先接口边界。
- `52-minimal-orchestration-loop.md` — 最小编排闭环。
- `64-versioning-governance.md` — 版本与阶段治理。

## 当前事实源

- `archive/139-stage90-live-chinese-control-panel-read-model.md` — 已验收实现：前台中文只读 GUI、Pi/OMP 安全状态、有限链路摘要与关闭后的过期投影。
- `archive/138-stage89-bounded-planner-executor-review-design.md` — 已验收实现：有限自动串行闭环的目标、冻结边界、契约、CLI 与真实 Pi/OMP 验收。
- `130-gui-first-external-agent-control-plane-target.md` — 长期产品主线与事实权威边界。
- `archive/137-stage88-external-agent-evidence-and-human-review.md` — 当前实现事实源：真实事件、不可变产物、固定恢复和人工审阅。
- `archive/136-stage87-single-work-item-controlled-execution.md` — 阶段 87 的单工作项执行实现与边界。
- `111-pi-controlled-dry-run-print-implementation.md` — 固定 Pi print 的实现与安全边界。

阶段 61、63、65 和 67-89 的已完成或冻结设计、实现与记录均已归档。

## 历史归档

| 目录 | 内容 |
|:---|:---|
| `archive/` | 已完成的设计、实现与里程碑事实源 |
| `archive/plans/` | 已执行的实施计划 |
| `archive/release-notes/` | 阶段与版本发布记录 |
| `archive/dry-runs/` | 历史试运行与提交记录 |
| `archive/smoke-regression/` | 历史冒烟验证与回归 |
| `archive/snapshots/2026-07-26/` | 文档治理前的长版入口快照 |

完整推进账本位于 `../tasks/progress.md`，仅在追溯历史决策时读取。
