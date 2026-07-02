# 02 — 路线图

## Stage 0 — 项目骨架

目标：先建立稳定的项目根目录和基础说明文件。

交付物：

- `README.md`
- `docs/01-vision-and-boundaries.md`
- `docs/02-roadmap.md`
- `tasks/progress.md`
- `decisions/0001-project-location.md`

状态：进行中。

---

## Stage 1 — 通用规则模型

目标：把Orchestrator、Media Agent、Memory Agent已经跑通的 harness 经验，抽象成可复用的规则格式。

要做的事：

- 设计 `policy schema`
- 明确规则类型：路径归属、密钥扫描、危险命令、只读区、外发前检查
- 准备Orchestrator / Media Agent / Memory Agent三份样例 policy
- 明确哪些规则是硬门禁，哪些只是提醒

注意：模型成本高峰期不放进硬门禁，只作为调度参考。

---

## Stage 2 — 任务账本

目标：定义任务如何被提交、执行、阻塞、恢复和完成。

要做的事：

- 设计任务状态：`planned`、`running`、`blocked`、`finished`、`failed`
- 决定任务记录用 JSONL 还是 SQLite
- 写几个任务记录样例
- 设计 `task status` 的输出格式

---

## Stage 3 — Agent 注册表

目标：在 Runtime 外部清楚记录有哪些 Agent、各自能力和边界。

要做的事：

- 起草 `agents.yaml`
- 定义字段：id、name、workspace、能力、禁区、默认任务类型、调用方式
- 把Orchestrator、Media Agent、Memory Agent先作为样例
- 明确 Agent 之间如何委派和验收

---

## Stage 4 — 工具适配器层

目标：不再把工具能力绑死在某一个宿主框架里，而是抽象成适配器。

候选适配器：

- QwenPaw Agent API
- Kimi CLI / ACP
- Claude Code ACP
- OMP / pi
- Shell
- 飞书
- GitHub
- 浏览器 / WebBridge

这一阶段先设计接口，不急着全部实现。

---

## Stage 5 — 最小 Runtime CLI

目标：做出第一个能跑的命令行入口。

候选命令：

```bash
agent-runtime check path <path>
agent-runtime check text --file BODY.md
agent-runtime check command "git push origin main"
agent-runtime task submit "整理 image-prompts"
agent-runtime task status <task-id>
agent-runtime agents list
```

这一阶段才开始写真正可执行的 Runtime 代码。

---

## Stage 6 — 小范围接入真实工作流

目标：选一个低风险真实任务，让它通过 Agent Runtime 跑一遍。

候选任务：

- 目录整理后的 path check
- GitHub 发文前 secret scan
- 多 Agent 任务分发后的状态记录
- 每日小任务进度账本

要求：

- 有回滚方案
- 有日志
- 有验证结果
- 不影响现有 QwenPaw 工作流
