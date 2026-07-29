# 144 — 阶段 94 Agent Deck P0 与 Pi/OMP 真实试运行验收

> 状态：**已验收并归档。**
> 日期：2026-07-29
> 产品主线：本地优先的聚合式 Agent 平台（Agent Deck）；Harness 保持唯一可信执行底层。

## 验收结论

阶段 94 的 Agent Deck P0 已完成。它将项目入口、Agent 团队、协作时间线与交付/验收统一为中文工作台；Pi/OMP 作为首批真实试运行成员完成了一次完整的 `Pi → OMP → Pi` 受控协作，并由操作者独立提交最终“通过”。

React 前台只消费固定的 `agent-deck/read-model/v1` 安全快照；Harness 仍唯一持有命令权限、审批、lease、审计、证据和最终决定的写入边界。P0 没有新增真实 operation、任意命令入口、宿主启动、网络 adapter、长期服务、并发、自动重试、运行中取消、恢复执行或自动批准。

## 已交付的产品路径

- 中文 Agent Deck 工作台：项目概览、自然语言任务入口草稿、Pi/OMP 团队卡片、待接入成员、协作时间线及结果/验收视图；
- Pi/OMP 为真实试运行成员：Pi 承担规划与审阅，OMP 承担执行；Codex CLI、Claude Code、Kimi Code 保持统一“待接入”模型，绝不伪造 readiness 或执行能力；
- 固定、版本化、最大 128 KiB 的 `.runtime/agent-deck/v1/agent-deck.snapshot.json`；导出通过原子替换写入，且只携带安全摘要；
- React/Vite/Tailwind/shadcn 展示层只读取该安全快照。Vite 的 `publicDir` 直接指向固定 runtime handoff；`ui_dispatch` 必须为 `false`，前台没有派发、批准、取消、恢复或命令桥接。

## 真实 Pi/OMP 验收证据

操作者重新打开 Pi 和 OMP 后，既有固定受控链路在一次启动授权内完成：

| 角色 | 宿主 | 尝试 | 结果 |
|:---|:---|:---|:---|
| 规划 | Pi | `attempt-20260729-019` | 成功，规划候选已归档 |
| 执行 | OMP | `attempt-20260729-021` | 成功，执行摘要已归档并进入审阅门禁 |
| 审阅 | Pi | `attempt-20260729-023` | 成功，建议 `approve`，无 findings |

链路 ID 为 `chain-20260729-acceptance-forward-111423627`：

- 创建于 `2026-07-29T11:15:12Z`，三轮实际派发位于 `2026-07-29T11:15:19Z` 至 `2026-07-29T11:16:43Z`；
- 每轮均具有 started/terminal audit、固定输入、有界输出、不可变内容寻址产物和进程树回收；
- 审阅建议的摘要为：固定结构化信封、提交前只读检查、仅接受业务结论的最终页及阶段 89 审计/lease/output 约束均满足；
- 操作者于 `2026-07-29T11:31:08.533Z` 独立提交最终 `approve`，完成记录 ID 为 `review-76edffe1c0e290bcbf1b775412485a6f943f380fe1c1e65431c1967772857932`；
- 新 CLI 进程只读复核到链路终态 `approved`。`recover-final-decision` 随后按预期失败关闭，因为不存在待恢复的最终决定。

## Agent Deck 前台投影验收

最终决定后重新导出运行时快照；其 schema 为 `agent-deck/read-model/v1`、`source_mode` 为 `runtime`，时间线中该链路精确投影为 `approved`。生产构建后的 `frontend/dist/agent-deck.snapshot.json` 复核到同一状态，且 `ui_dispatch=false`。

Pi 和 OMP 当时的宿主观察已超过 TTL，快照因此如实投影为“已连接，存在未绑定会话 / 观察已超过 TTL”。这是安全 read model 的准确状态，不会被前台改标为空闲、就绪或可执行，也不改变已归档的真实链路结果。

## 验证记录

以下命令在最终链路和最终投影后成功：

```powershell
python -m pytest tests -q
python -m pytest tests/test_controlled_write_regression.py -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
git diff --check
bash .githooks/pre-commit

Set-Location frontend
npm ci --ignore-scripts
npm run test
npm run typecheck
npm run build
```

其中 Python 全量测试通过；受控写入回归通过；前端 7 个测试文件、12 个测试通过，类型检查和 Vite 生产构建通过。

## 后续边界

阶段 95 仅可在新的独立设计和用户授权后开始。下一候选是把 Agent Deck 从“安全可见的 P0 团队工作台”扩展为更完整的协作交互产品；无论选择何种前台能力，都不得绕开 Harness 的固定 command authority，也不得把已接入的 Pi/OMP 试运行权限泛化为自由执行权限。
