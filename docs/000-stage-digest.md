# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 92 已于 2026-07-28 完成正向与反向真实 Pi/OMP GUI 自动串行和最终决定验收
- commit：当前工作树包含阶段 93 已验证、待提交的实现与自动化测试变更；未获得本次 commit/push 授权
- 日期：2026-07-28
- 活跃 `docs/` 根目录为 29 份；阶段 92 及此前的已验收阶段均已归档

## 当前阶段

- **阶段 93 — 实现与自动化验证完成，待真实 GUI 验收：仅允许操作者不可逆地放弃一条已等待最终人工决定的链路。** 它不取消运行中 Agent、不终止进程、不重试、不恢复失败角色，也不修改既有证据或人工审阅。
- 当前事实源：`142-stage93-pending-final-decision-abandonment.md`。
- 已验收基线：`archive/141-stage92-registered-work-inbox.md`；前序事实源：`archive/140-stage91-gui-structured-approval-inbox.md`、`archive/139-stage90-live-chinese-control-panel-read-model.md`、`archive/138-stage89-bounded-planner-executor-review-design.md`。
- 仅对 `awaiting_final_human_decision` 提供 preview / 一次性确认 / `--commit` 的固定放弃；提交复用不可变 `stop` 记录并精确绑定执行和审阅摘要。任意其他状态、漂移或确认不匹配均失败关闭。

## 已冻结边界

- 仅允许 `pi-local -> omp-local -> pi-local` 或反向拓扑；单条链路最多三次既有单工作项派发。
- 启动确认只绑定稳定业务范围；每个角色前固定等待两秒状态稳定窗口后，只读取一次新鲜 `observed/open` 宿主状态。任何失败写入不可变 `stop` 并结束当前链路。
- 规划候选和审阅建议为严格、有界、已扫描 JSON；审阅提示只绑定执行产物摘要和既有证据，不拼接原始执行文本。
- 最终人工决定与阶段 88 审阅记录精确绑定；`finalization_pending` 的恢复不重新调用 Agent。
- 阶段 93 放弃只在三轮结束、最终人工决定尚未开始时写固定 `stop`；不具备运行中取消或恢复执行能力。

## 当前真实执行能力

1. Windows 固定 Git 状态：固定 `git status --short --branch`。
2. Windows 固定 Pi 打印：固定 `pi --print --no-session --no-tools <prompt>`。
3. 单工作项外部智能体派发，以及阶段 89 的有限自动串行 wrapper。

均要求显式 `--commit`、租约、固定输入、审计、输出约束和失败关闭；没有任意 shell、工具权限、网络、并行、自动重试或自动批准。

## 仍未开放

- 通用 shell、任意适配器执行、POSIX fallback；
- 网络适配器、服务、数据库、自动后台执行；
- 由 Harness 启动、关闭或重启外部 Agent；
- Pi/OMP 的 read/write/edit/bash 或 MCP 工具权限；
- 自动采纳规划者计划、审阅建议、自动修改或自动批准；
- 任意项目文件产物回收、通用 GUI 命令通道、运行中取消、恢复执行、有限并发、QwenPaw 2.0.1 接入。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/142-stage93-pending-final-decision-abandonment.md`
3. `docs/archive/141-stage92-registered-work-inbox.md`
4. `docs/02-roadmap.md`
5. `docs/130-gui-first-external-agent-control-plane-target.md`
6. `docs/archive/140-stage91-gui-structured-approval-inbox.md`
7. `docs/archive/138-stage89-bounded-planner-executor-review-design.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 下一步推荐入口

- **阶段 93 — 真实 GUI 验收与归档**
  - 入口文档：`docs/142-stage93-pending-final-decision-abandonment.md`
  - 重点：仅验收待决最终决定的固定放弃；不得把它解释为运行中 Agent 取消、自动恢复或重试。

后续能力仍未授权：运行中取消、恢复执行、有限并发，以及 QwenPaw 2.0.1 等其他宿主兼容。
