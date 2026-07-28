# 000 — 阶段摘要

> 新会话先读本页；历史细节按需进入 `00-index.md` 或 `archive/`。

## 当前基线

- 里程碑：阶段 90 实时中文控制面读取模型与只读图形面板已完成并归档；2026-07-28 已完成真实 Pi/OMP 图形验收
- commit：阶段 89 基线为 `e4bd207`；阶段 90 当前变更尚未提交
- 日期：2026-07-28
- 活跃 `docs/` 根目录为 28 份；阶段 90 及此前的阶段事实源均已归档

## 当前阶段

- **阶段 90 — 已完成：操作者前台启动中文只读窗口，真实验收确认 Pi/OMP 状态、有限链路摘要与 OMP 关闭后的过期投影。**
- 归档事实源：`archive/139-stage90-live-chinese-control-panel-read-model.md`。
- 前序事实源：`archive/138-stage89-bounded-planner-executor-review-design.md`、`archive/137-stage88-external-agent-evidence-and-human-review.md`。
- GUI 没有派发、批准、最终决定、重试、取消、恢复或宿主控制入口；`--json` 仅构建一次确定性快照。

## 已冻结边界

- 仅允许 `pi-local -> omp-local -> pi-local` 或反向拓扑；单条链路最多三次既有单工作项派发。
- 启动确认只绑定稳定业务范围；每个角色前固定等待两秒状态稳定窗口后，只读取一次新鲜 `observed/open` 宿主状态。任何失败写入不可变 `stop` 并结束当前链路。
- 规划候选和审阅建议为严格、有界、已扫描 JSON；审阅提示只绑定执行产物摘要和既有证据，不拼接原始执行文本。
- 最终人工决定与阶段 88 审阅记录精确绑定；恢复不重新调用 Agent。

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
- 任意项目文件产物回收、GUI 结构化命令通道、有限取消/恢复、QwenPaw 2.0.1 接入。

## 下次恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/00-index.md`
3. `docs/02-roadmap.md`
4. `docs/130-gui-first-external-agent-control-plane-target.md`
5. `docs/archive/139-stage90-live-chinese-control-panel-read-model.md`
6. `docs/archive/138-stage89-bounded-planner-executor-review-design.md`

然后运行：

```bash
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
```

## 后续候选（尚未授权）

- GUI 承载既有一次性确认的结构化审批收件箱；
- 有界取消、恢复或有限并发；
- QwenPaw 2.0.1 等其他宿主兼容。
