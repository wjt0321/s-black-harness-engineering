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

- 进入下一阶段：真实 task ledger 只读查询。
- 新增 `agent_runtime/tasks.py`，从 `tasks/tasks.jsonl` / `tasks/events.jsonl` 或示例 JSONL 中读取任务快照与事件流。
- 接入 CLI：`python -m agent_runtime.cli task status <task-id>` 与 `python -m agent_runtime.cli task events <task-id>`。
- 补充 CLI 测试，覆盖任务快照、事件流、JSON 输出和缺失任务返回 `NEEDS_INPUT`。
- 更新 `docs/10-cli-poc-usage.md`，记录任务账本查询命令。
- 继续扩展 `check action`：现在会聚合 adapter 风险、command rules、publish rules 和 completion rules。
- GitHub publish 类动作会同时提示用户授权与 required checks；完成类动作会提示 required evidence。
- 补充对应 CLI 测试，覆盖 publish preflight 与 completion evidence。
- 新增 `--policy-profile` 参数，支持按 `s-black`、`wangcai`、`dabai` 或 `all` 选择样例 policy；同时修复重复注册全局参数时前置参数被子命令默认值覆盖的问题。
- 新增真实本地只读 ledger 样例：`tasks/tasks.jsonl` 与 `tasks/events.jsonl`。
- 调整 task loader：真实 ledger 存在时优先读取真实文件；不存在时才回退 `.examples.jsonl`。
- 补充 task loader 测试，覆盖真实 ledger 优先级与 fallback 行为。
- 新增 `docs/11-release-notes-v0.1.md`，沉淀 v0.1 release notes、当前 CLI 能力、安全边界、验证方式和已知限制。
- 更新 `README.md` 与 `README.en.md` 的文档列表。
- 新增 `pyproject.toml`，提供 Python 包元数据、pytest 配置、dev 依赖和可选 `agent-runtime` console script。
- 更新 CLI 使用说明，补充可编辑安装方式。
- 新增 `.github/workflows/ci.yml`，在 push / pull_request 到 main 时用 Python 3.11 和 3.12 跑 `pytest` 与 `doctor`。
- CI 已补充 ledger CLI smoke checks：`task validate` task/event 与 `task check-ledger`。
- 更新中英文 README 的持续集成说明。
- 新增 ledger 写入前 preflight schema 校验层 `agent_runtime/task_validation.py`。
- 新增 CLI 命令 `python -m agent_runtime.cli task validate --record-file <file> --schema task|event`。
- 校验保持只读：不写入、不追加、不修改 ledger，不执行外部命令，不访问网络。
- 失败输出仅包含行号、schema 类型和简短错误摘要，不回显整条 record 或敏感字段完整值。
- 补充测试覆盖：valid/invalid task、valid/invalid event、JSONL 语法错误行号、CLI valid/invalid、JSON 输出。
- 更新 `docs/10-cli-poc-usage.md` 与 `tasks/progress.md` 记录新命令。
- 已跑 `python -m pytest`：45 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已抽查 `task validate` 对合法 JSONL 返回 PASS，对缺字段/非法 JSON 返回 `VALIDATION_FAILED` 并正确报告行号。
- 新增仓库内 `tools/public_scan.py`，替代维护者本地临时 public scan 脚本。
- public scan 只读：仅扫描仓库内文本文件，不读 `.env`/credential，不访问网络，不执行外部命令，不写文件。
- public scan 覆盖 token 模式、Windows 绝对路径、Unix home 路径；命中时只输出相对路径、行号、规则 id，不回显完整命中值。
- 已加入 CI：`.github/workflows/ci.yml` 在 pytest 与 doctor 后运行 `python tools/public_scan.py`。
- 已替换仓库内遗留的 Windows 绝对路径示例（如 `DRIVE:/competition_notes/`、`DRIVE:/workspace`）为相对路径示例，避免 public scan 误报。
- 已补充 `tests/test_public_scan.py`，覆盖 clean 文本、token/路径命中、输出脱敏、跳过 credential 文件与二进制目录、行号报告、仓库级扫描通过。
- 已更新 `docs/10-cli-poc-usage.md`、`docs/11-release-notes-v0.1.md`、`tasks/progress.md`、`tasks/handoff-2026-07-03.md`，说明 public scan 已产品化并纳入 CI。
- 已跑 `python -m pytest`：55 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。
- 新增 ledger 跨记录一致性校验层 `agent_runtime/ledger_consistency.py`。
- 新增 CLI 命令 `python -m agent_runtime.cli task check-ledger --tasks-file <file> --events-file <file>`。
- 校验内容：event.task_id 存在性、状态流转连续性、created from_status 为 null、终态不可回退、snapshot status 与最新 event to_status 一致。
- 命令只读 JSONL，不写入/修复/追加 ledger，不执行外部命令，不访问网络。
- 失败输出仅含 event_id/task_id、行号、规则 id 与简短说明，不回显整条 record。
- 已补充 `tests/test_ledger_consistency.py`，覆盖当前 ledger 通过、未知 task_id、snapshot 不一致、终态回退、时间乱序排序、created 规则、首事件非 created、状态不连续、输出不脱敏、CLI valid/invalid。
- 已更新 `docs/10-cli-poc-usage.md`、`tasks/progress.md`、`tasks/handoff-2026-07-03.md`。
- 已跑 `python -m pytest`：66 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。
- 新增 `agent_runtime/policy_profile.py`，实现 agent -> policy profile 自动映射。
- 新增 `--agent <agent-id>` 与 `--assignee <agent-id>` 全局参数，供 `check text`、`check path`、`check action`、`policies list` 自动选择 policy profile。
- 解析优先级：`--policy` > `--policy-profile` > `--agent`/`--assignee` > 默认 `all`。
- 自动映射：orchestrator/s-black -> s-black，media-agent/wangcai -> wangcai，memory-agent/dabai -> dabai，unknown -> all。
- 不改变现有 `--policy-profile` 行为，已有测试继续通过。
- 已补充 `tests/test_policy_profile.py`，覆盖显式 profile 优先、各 agent 映射、unknown 回退 all、显式 policy 文件优先于 agent、CLI 各命令使用 agent 推断。
- 已更新 `docs/10-cli-poc-usage.md`、`tasks/progress.md`、`tasks/handoff-2026-07-03.md`。
- 已跑 `python -m pytest`：84 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。
- 将 agent -> policy profile 映射从 `agent_runtime/policy_profile.py` 硬编码迁移到 `agents/agents.sample.json` 的 `policy_profile` 字段。
- 更新 `agents/agents.schema.json`：新增可选字段 `policy_profile`，类型 string，minLength 1，给出常见示例。
- 更新 `agents/agents.sample.json`：orchestrator/kimi-code/claude-code/omp -> s-black，media-agent -> wangcai，memory-agent -> dabai。
- 改写 `agent_runtime/policy_profile.py`：从 agent registry 读取映射，保留极小 fallback；`resolve_profile(args, root)` 支持传入 root。
- 更新 `agent_runtime/cli.py`：所有 `resolve_profile` 调用传入 `root`。
- 更新 `tests/test_policy_profile.py`：覆盖 registry 读取、registry 覆盖 fallback、未知 agent 回退 all、缺失 registry 使用 fallback、原有 CLI 覆盖优先级。
- 更新 `docs/05-agent-registry.md`、`docs/10-cli-poc-usage.md`、`tasks/progress.md`、`tasks/handoff-2026-07-03.md`。
- 已跑 `python -m pytest`：84 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 下一步小任务

1. 后续可继续完善 agent 到 policy profile 的自动映射。
2. 后续可设计跨记录 ledger consistency 校验，例如 task_id 引用、事件顺序和状态流转合法性。
3. 后续可在公开扫描脚本产品化后再考虑加入 CI。

- 进入下一阶段：Adapter execution envelope 二期设计。
- 新增 `docs/12-adapter-execution-envelope.md`，定义 adapter request、adapter response、approval record、execution event 四类 artifact。
- 新增 `adapters/execution-envelope.schema.json`，作为 execution envelope artifact 集合的 JSON Schema。
- 新增 `adapters/execution-envelope.examples.json`，提供 GitHub push 需授权场景和 shell read 只读成功场景。
- 更新 `agent_runtime/doctor.py`，将 execution envelope schema 与 examples 纳入 doctor 校验。
- 更新 README 中英文文档列表与当前状态说明。
- 本阶段仍保持只读边界：不执行真实 adapter、不访问网络、不写 ledger、不记录真实密钥或本机私有路径。

- 新增只读 `adapter plan` CLI 命令，把 `check action` 的 preflight 结果包装成 Adapter execution envelope 草案。
- 新增 `agent_runtime/adapter_plan.py`：加载 adapter registry、运行 `check_action`、生成 `adapter_request`；当 preflight 为 `needs_approval` 时附加 `approval_record` 与 `approval_requested` execution event；并用 `jsonschema` 校验 envelope。
- 更新 `agent_runtime/cli.py`：新增 `adapter plan` 子命令，支持 `--adapter`、`--operation`、`--target`、`--actor`、`--task-id` 和全局 `--agent`/`--policy-profile`。
- 命令保持只读：不执行真实 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 补充 `tests/test_adapter_plan.py`，覆盖：GitHub push 需要授权、shell read PASS、JSON 输出 schema 校验、不写入 ledger、未知 adapter、按 agent 选择 profile、自定义 actor/task-id。
- 更新 `docs/10-cli-poc-usage.md` 与 `tasks/progress.md`，记录 `adapter plan` 用法。
- 已跑 `python -m pytest`：91 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增只读 `adapter validate` CLI 命令，用于校验 Adapter execution envelope JSON 文件。
- 新增 `agent_runtime/adapter_validation.py`：检查文件位于项目根目录内且为安全 `.json` 文件，使用 `jsonschema` 校验整个 envelope，失败时只输出相对路径、schema 错误路径/规则和简短摘要，不回显整条 artifact 或敏感值。
- 更新 `agent_runtime/cli.py`：在 `adapter` 子命令下新增 `validate`，支持 `--file` 与 `--json`。
- 命令保持只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 补充 `tests/test_adapter_validate.py`，覆盖：valid examples PASS、invalid JSON、schema invalid、outside-root、unsafe file、非 JSON 扩展名、JSON 输出、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md` 与 `tasks/progress.md`，记录 `adapter validate` 用法。
- 已跑 `python -m pytest`：99 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增明日接续文档 `tasks/handoff-2026-07-04.md`，记录当前远端状态、Adapter execution envelope 阶段成果、只读 `adapter plan` / `adapter validate` 能力、验证结果、推送与代理记录，以及明日建议路线。
