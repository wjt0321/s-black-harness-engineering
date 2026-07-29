# 64 — 当前版本与文档治理

> 状态：当前治理规则；历史版本、Stage 47–51 记录与旧发布判断见 `archive/64-versioning-governance-legacy-2026-07-29.md`。

## 1. 权威来源

| 问题 | 首选事实源 |
|:---|:---|
| 当前断点、恢复顺序与下一设计入口 | `000-stage-digest.md` |
| 文档导航 | `00-index.md` |
| 产品方向与反偏航检查 | `130-gui-first-external-agent-control-plane-target.md` |
| 当前能力包与下一候选 | `02-roadmap.md` |
| 当前 CLI 用法 | `10-cli-poc-usage.md` |
| 当前实现细节 | 最新 `tasks/handoff-*.md` 与直接相关模块/测试 |
| 已完成设计、计划、验收与发布记录 | `archive/` |

同一事实不得在 README、roadmap、digest、handoff 和阶段文档中各自演化。它们的职责分别是：用户概览、能力方向、恢复断点、下一步工作包和历史事实。

## 2. 文档生命周期

- **根目录 `docs/`**：当前架构、边界、短入口和仍有效的规范；
- **`docs/archive/`**：已完成阶段、旧设计、旧计划、旧 CLI 入口、smoke 与发布记录；保留以供追溯，不把它们当默认操作说明；
- **`tasks/handoff-*.md`**：只保留最新文件作为恢复入口，旧 handoff 保持历史可追溯；
- **`tasks/progress.md`**：完整历史流水，不作为新会话第一阅读对象。

完成一个里程碑时：归档设计/计划/验收，更新 README、digest、index、roadmap 和必要的事实源，再写入下一阶段 handoff。不要删除历史内容；用 `git mv` 归档。

## 3. 版本与阶段原则

- Stage 不是版本号；只有具备明确兼容承诺、验证证据和发布决策时才评估语义化版本；
- 不因文档、内部重构或尚未验证的 capability 提升版本；
- 每项真实 operation 的范围、平台、输入、审计、failure mode 和恢复语义必须单独冻结；
- preview、read model、fixture、task registration、readiness 和 approval draft 都不是执行权限；
- 未实际成功的测试、smoke、commit、push 或发布不得写成已完成。

## 4. 当前发布与提交纪律

- 代码或 schema 改动至少运行全量 pytest、受控写入回归、doctor、public scan、`git diff --check`；文档改动还运行 `.githooks/pre-commit`；
- 前端改动同时运行 Vitest、typecheck 和 production build；
- commit 与 push 只在用户本次明确授权后进行；
- `.runtime/`、凭据、smoke 原文和本机状态不提交；
- 归档移动、索引更新和 handoff 更新与实现提交保持同一逻辑闭环。

## 5. 当前产品阶段

阶段 96 已完成受控任务登记与规划收件箱。阶段 97 是“受限主控 Agent 结构化规划提议”的独立设计入口：它不得扩大执行权限、前端写入桥接、Agent 工具、并发、网络或自治能力。

历史完整治理记录保留在 `archive/64-versioning-governance-legacy-2026-07-29.md`。
