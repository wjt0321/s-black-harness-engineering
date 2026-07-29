# 146 — 阶段 96 设计：受控任务登记与规划收件箱

> 状态：已实施并归档
> 日期：2026-07-29

## 决策

将“任务草案如何进入 Harness”与“谁可以执行任务”严格拆开。用户目标先经过有界输入与安全扫描，再以固定元数据进入既有任务/事件账本；任务只获得“等待主控 Agent 规划”的可见状态，不获得运行权限。

## 契约

```text
用户目标
  -> agent-deck mission submit (--dry-run | --commit)
  -> goal 边界检查 + secret scan
  -> 自动生成 task ID / 固定候选字段
  -> 既有 submit_task A+B 事务
  -> task_queue 安全投影
  -> Agent Deck 看板显示“等待主控 Agent 规划”
```

输入不是命令、路径或执行参数。`--commit` 只写入固定 `tasks/tasks.jsonl` 与 `tasks/events.jsonl`；它不接触 adapter、进程、host、lease 或 execution audit。

## 状态模型

- 浏览器草案：只在当前浏览器会话，未登记；
- 已登记任务：账本 `planned`，在 Deck 显示“等待规划”；
- 规划提议：本阶段未实现；只有下一阶段在独立 contract 下创建；
- 已批准执行：仍完全由既有收件箱、预检、一次确认、lease、审计与最终人工决定控制。

## 安全论证

1. 编号、账本位置和初始角色全部由模块生成，阻断内部标识符、路径和运行参数注入；
2. 对目标先 scan，再由原有 task writer 再次校验，形成双层失败关闭；
3. 事务复用已验证的 A+B append、写后检查和回滚，而非新 writer；
4. read model 只承载固定的状态标签；自由标题仅沿用既有有界安全投影；
5. 前端没有 write bridge，因此无法从浏览器越过 `--commit` 边界。
