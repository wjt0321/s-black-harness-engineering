# 进度账本

## 2026-07-02

- 创建项目根目录：本地 checkout 目录。
- 创建初始目录：`docs/`、`policies/`、`adapters/`、`tasks/`、`logs/`、`decisions/`、`notes/`。
- 写入首批框架文件：README、愿景与边界、路线图、进度账本、项目位置决策。
- 当前阶段：Stage 0 — 项目骨架。
- 用户反馈：首版文档不应使用英文，长期项目文档应默认中文，方便用户直接查看和判断。
- 已将首批框架文档改为中文。
- 开始 Stage 1 — 通用规则模型。
- 已从Orchestrator现有 harness POC 抽象出第一版通用 `policy schema`。
- 新增 `docs/03-policy-schema.md`，记录规则模型、严重级别、动作类型、路径规则、密钥规则、命令规则、外发规则和完成验证规则。
- 新增 `policies/policy.schema.json`，作为第一版 JSON Schema 草案。
- 新增 `policies/s-black.sample.policy.json`，作为Orchestrator样例 policy。
- 已用 `python -m json.tool` 验证两份 JSON 文件语法有效。
- 开始 Stage 2 — 任务账本。
- 新增 `docs/04-task-state-model.md`，定义 `planned`、`running`、`blocked`、`finished`、`failed` 五种状态及流转规则。
- 确认第一版任务记录优先使用 JSONL，暂不使用 SQLite。
- 新增 `tasks/task.schema.json` 和 `tasks/event.schema.json`，作为任务对象和事件对象的 JSON Schema 草案。
- 新增 `tasks/examples.jsonl` 和 `tasks/events.examples.jsonl`，作为任务快照与事件流样例。
- 已用临时校验脚本验证 JSON Schema 与 JSONL 样例语法有效。
- 开始 Stage 3 — Agent 注册表。
- 新增 `docs/05-agent-registry.md`，说明 Agent 注册表目标、字段、能力标签、边界、委派与验收关系。
- 新增 `agents/agents.schema.json`，作为 Agent 注册表 JSON Schema 草案。
- 新增 `agents/agents.sample.json`，记录Orchestrator、Media Agent、Memory Agent、Kimi Code、Claude Code、OMP / pi 的第一版样例。
- 已用 `python -m json.tool` 验证两份 Agent 注册表 JSON 文件语法有效。
- 收完整 Stage 1 — 通用规则模型。
- 新增 `policies/wangcai.sample.policy.json`，约束Media Agent的 MiniMax 创作产物、轻量日常任务、外发动作和跨工作区边界。
- 新增 `policies/dabai.sample.policy.json`，约束Memory Agent的记忆守护边界、只读原则、跨 Agent 记忆归档和敏感信息保护。
- 调整 `policies/policy.schema.json` 的组合规则写法，使样例 policy 可通过 schema 校验。
- 已验证 `s-black.sample.policy.json`、`wangcai.sample.policy.json`、`dabai.sample.policy.json` 均为合法 JSON，并通过 `policy.schema.json` 校验。
- 更新 `docs/03-policy-schema.md` 的 Stage 1 落地范围说明。
- 会话结束前新增交接文档 `tasks/handoff-2026-07-02.md`，记录项目定位、今日完成、当前文件结构、明天建议入口和注意事项。

## 2026-07-03

- 继续 Stage 4 — 工具适配器层。
- 新增 `docs/06-adapter-layer.md`，定义 Adapter 的目标、非目标、统一字段、风险级别、输入/输出 envelope、preflight/postflight、failure mapping，以及与 Policy Schema、Task State、Agent Registry 的关系。
- 新增 `adapters/adapter.schema.json`，作为 Adapter 注册项 JSON Schema 草案。
- 新增 `adapters/adapters.sample.json`，包含 QwenPaw Agent API、Kimi Code ACP、Claude Code ACP、OMP / pi ACP、Shell、飞书、GitHub、WebBridge 八类适配器样例。
- 已验证 `adapter.schema.json` 和 `adapters.sample.json` 均为合法 JSON。
- 已验证 `adapters.sample.json` 通过 `adapter.schema.json` 校验。
- 新增 `docs/07-policy-task-bridge.md`，定义 Policy 检查结果如何映射到 Task 的 `blocked`、`running`、`finished`、`failed` 状态。
- 新增 `tasks/policy-event.examples.jsonl`，提供 policy 命中、用户授权恢复、secret scan evidence、只读路径阻断、completion evidence 不足等事件样例。
- 已验证 `tasks/policy-event.examples.jsonl` 为合法 JSONL。

- 新增 `docs/08-minimal-cli-design.md`，定义最小 CLI 命令边界：`check action`、`check text`、`check path`、`task status`、`task events`、`agents list`、`adapters list`、`policies list`、`doctor`。
- 新增 `cli/commands.sample.json`，把 CLI 命令边界结构化为样例数据，方便后续实现。
- 已验证 `cli/commands.sample.json` 为合法 JSON。
- 明确进入真实 CLI 实现时，可优先委派 Kimi Code 负责编码，Orchestrator 负责验收。

- 新增 `docs/09-policy-checker-poc-plan.md`，定义最小 Policy Checker POC 的目标、非目标、推荐代码位置、输入输出、`check text` / `check path` / `check action` 行为、测试样例、安全要求和验收标准。
- 明确第一版 POC 只做只读检查，不执行外部命令、不访问网络、不写真实 task ledger、不读取密钥文件。
- 明确后续进入代码实现时可委派 Kimi Code 编写，Orchestrator 负责安全与质量验收。

- 完成最小只读 CLI POC 第一版实现，新增 `agent_runtime/` 与 `tests/`。
- 已支持 `python -m agent_runtime.cli` 与 `python -m agent_runtime`。
- 已实现：`doctor`、`check text`、`check path`、`check action`、`agents list`、`adapters list`、`policies list`。
- 已补聚焦测试：text secret scan、path rules、doctor、CLI 基础行为。
- 已确认 `check text` 不回显完整 secret match；测试中的 token 仅在内存中动态拼接。
- 已确认第一版只读：不执行外部命令、不访问网络、不发送消息、不删除文件、不写真实 task ledger。
- 已跑 `python -m pytest tests -q`：23 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑公开扫描：OK public scan。
- 已抽查 `check action --adapter github-cli --operation git_push` 返回 `NEEDS_APPROVAL`，低风险 shell read 返回 `PASS`。

- 新增 `docs/10-cli-poc-usage.md`，说明当前 CLI POC 的运行方式、命令示例、全局参数、返回码、安全边界和当前限制。
- 更新 `README.md` 和 `README.en.md`，加入“当前已可运行”和快速开始命令，并补齐当前文档列表。
- 至此，项目完成一个阶段性闭环：从愿景/路线图 -> policy schema -> task state -> agent registry -> adapter layer -> policy-task bridge -> CLI 设计 -> policy checker POC 计划 -> 只读 CLI POC 实现 -> 使用说明。
- 新增 `tasks/handoff-2026-07-03.md`，为下一阶段留下恢复上下文、已完成清单、验收命令和候选路线。

## 下一步小任务

1. 后续再扩展 `check action` 的 publish_rules / completion_rules 关联。
2. 后续可增加真实 `tasks/tasks.jsonl` 与 `tasks/events.jsonl` 的只读查询样例。
3. 后续可考虑发布版本标签，例如 `v0.1.0-planning-poc`。
