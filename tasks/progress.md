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

## 2026-07-04

- 继续 Adapter execution envelope 阶段：在 `adapter validate` 中集成跨 artifact 一致性校验。
- 修改 `agent_runtime/adapter_validation.py`：schema 校验通过后，新增 `_check_envelope_consistency` 对 envelope 内 artifact 做只读一致性检查。
- 一致性规则：
  - `duplicate-request-id`：`adapter_request.request_id` 唯一。
  - `approval-references-unknown-request`、`response-references-unknown-request`、`event-references-unknown-request`：各 artifact 的 `request_id` 必须引用存在的 `adapter_request`。
  - `approval-scope-mismatch`：`approval_record.scope` 的 `task_id` / `adapter_id` / `operation` / `target` 必须与对应 `adapter_request` 完全一致。
  - `needs-approval-missing-record`：`requires_approval` 且 `preflight.status == "needs_approval"` 的请求必须存在 pending/granted 的 `approval_record`。
  - `approval-requested-event-unknown-approval`：`approval_requested` 事件的 `metadata.approval_id` 必须引用存在的 `approval_record`。
- 保持只读边界：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential；失败输出仅含相对路径、artifact id、规则 id 和简短摘要，不回显完整 artifact 或 payload。
- 补充 `tests/test_adapter_validate.py`：覆盖 unknown approval request、unknown response request、unknown event request、approval scope mismatch、needs approval missing record、unknown approval_id in event、duplicate request_id，以及 JSON 输出和不写 ledger。
- 更新 `docs/10-cli-poc-usage.md`，说明 `adapter validate` 现在包含 schema + consistency 双重校验。
- 更新 `tasks/progress.md` 记录本次进展。
- 已跑 `python -m pytest`：106 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增只读 `adapter inspect` CLI 命令，用于读取 Adapter execution envelope JSON 文件并输出紧凑摘要。
- 新增 `agent_runtime/adapter_validation.py` 中 `_load_envelope` / `_build_envelope_summary` / `inspect_envelope_file` 逻辑：先调用 `validate_envelope_file` 做 schema + consistency 校验，校验通过后再解析并汇总 artifact 信息。
- 复用现有安全读取逻辑：文件必须在项目根目录内、为安全 `.json` 文件、拒绝 `.env`/credential 类文件。
- 摘要包含 envelope version/description、artifact counts by type、requests/approvals/responses 列表、event_type 计数、overall flags（requires_approval_count、pending_approval_count、response_count、evidence_count）。
- 人类输出紧凑，不打印完整 envelope 与 input payload；JSON 输出结构化为 `{status, summary}`；失败时返回与 `adapter validate` 相同的状态/返回码且不输出 summary。
- 更新 `agent_runtime/cli.py`：在 `adapter` 子命令下新增 `inspect`，支持 `--file` 与 `--json`。
- 补充 `tests/test_adapter_inspect.py`：覆盖合法 envelope 人类输出与 JSON 输出、schema/JSON 非法时不输出 summary、outside-root/unsafe 文件被拒、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md`，新增 `adapter inspect` 用法说明。
- 已跑 `python -m pytest`：113 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增只读 `adapter approval check` CLI 命令，用于检查某个 `adapter_request` 是否存在可继续执行的 `approval_record`。
- 新增 `agent_runtime/adapter_approval.py`：复用 `adapter_validation.validate_envelope_file` 做 schema + consistency 校验，再按 `request_id` 定位请求与授权记录，返回 `pass` / `blocked` / `needs_approval` / `needs_input` / `validation_failed`。
- 状态映射：`granted` -> `pass`（返回码 0），`pending` -> `needs_approval`（返回码 3），`denied` / `expired` -> `blocked`（返回码 2），请求不存在 -> `needs_input`（返回码 4），不需要授权 -> `pass`，校验失败 -> `validation_failed`（返回码 5）。
- 放宽 `adapter_validation` 中 `needs-approval-missing-record` 一致性规则：只要存在对应 `approval_record` 即满足要求（不再限定 `pending`/`granted`），使 `denied`/`expired` 也能作为合法 envelope 状态被检查。
- 输出摘要包含 `request_id`、`adapter_id`、`operation`、`target`、`requires_approval`、`approval_id`、`approval_status`、`decision_ref`（如有），不包含 `input` payload。
- 更新 `agent_runtime/cli.py`：在 `adapter` 下新增 `approval check` 子命令，支持 `--file`、`--request-id` 与 `--json`。
- 补充 `tests/test_adapter_approval.py`：覆盖 `granted` PASS、`pending` NEEDS_APPROVAL、`denied` BLOCKED、`expired` BLOCKED、不需要授权 PASS、未知请求 NEEDS_INPUT、非法 envelope 不输出 approval 摘要、outside-root/unsafe 文件被拒、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md`，新增 `adapter approval check` 用法说明与状态映射表。
- 已跑 `python -m pytest`：125 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增只读 `adapter response check` CLI 命令，用于检查某个 `adapter_request` 是否已有 `adapter_response` 以及 response/evidence 状态。
- 新增 `agent_runtime/adapter_response.py`：复用 `adapter_validation.validate_envelope_file` 做 schema + consistency 校验，再按 `request_id` 定位请求与 response，返回 `pass` / `blocked` / `needs_approval` / `needs_input` / `validation_failed`。
- 状态映射：`succeeded` 且 `evidence_count > 0` -> `pass`（返回码 0）；`succeeded` 但 `evidence_count == 0` -> `blocked`（返回码 2）；`blocked` -> `blocked`；`failed` -> `blocked`；`needs_approval` -> `needs_approval`（返回码 3）；`needs_input` -> `needs_input`（返回码 4）；`skipped` -> `blocked`；无 response -> `needs_input`（返回码 4）；请求不存在 -> `needs_input`（返回码 4）；校验失败 -> `validation_failed`（返回码 5）。
- 输出摘要包含 `request_id`、`adapter_id`、`operation`、`target`、`response_id`、`response_status`、`artifact_count`、`evidence_count`、`raw_ref_present`；不输出 `input` payload、evidence description 或 `raw_ref` 值。
- 更新 `agent_runtime/cli.py`：在 `adapter` 下新增 `response check` 子命令，支持 `--file`、`--request-id` 与 `--json`。
- 补充 `tests/test_adapter_response.py`：覆盖 `succeeded` + evidence PASS、`succeeded` 无 evidence BLOCKED、missing response NEEDS_INPUT、unknown request NEEDS_INPUT、`blocked`/`failed`/`needs_approval`/`needs_input`/`skipped` 各状态、非法 envelope 不输出 response 摘要、outside-root/unsafe 文件被拒、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md`，新增 `adapter response check` 用法说明与状态映射表。
- 更新 `tasks/progress.md` 记录本次进展。
- 已跑 `python -m pytest`：140 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

- 新增只读 `adapter gate check` CLI 命令，用于聚合 `adapter approval check` 与 `adapter response check`，给出某个 request 当前是否可继续的单一判断。
- 新增 `agent_runtime/adapter_gate.py`：复用 `check_adapter_approval` 与 `check_adapter_response`，先跑 approval check；若未通过则 stage 为 `approval` 并直接返回 approval 状态；若通过则 stage 为 `response` 并以 response 状态为最终状态；`can_proceed` 仅在最终状态为 `pass` 时为 `true`。
- 状态映射：不需要授权 + succeeded + evidence -> `pass`；approval pending -> `needs_approval`；approval denied/expired -> `blocked`；approval granted 但无 response -> `needs_input`；response succeeded 无 evidence -> `blocked`；response blocked/failed/skipped -> `blocked`；response needs_approval/needs_input -> 对应状态；请求不存在 -> `needs_input`；envelope 非法 -> `validation_failed`/`error`。
- 输出摘要包含 `request_id`、`stage`、`approval_status`、`response_status`、`can_proceed`、`next_action`，可附带 approval/response 子摘要；不输出 `input` payload、evidence description 或 `raw_ref` 值。
- 更新 `agent_runtime/cli.py`：在 `adapter` 下新增 `gate check` 子命令，支持 `--file`、`--request-id` 与 `--json`。
- 补充 `tests/test_adapter_gate.py`：覆盖不需要授权 + succeeded evidence PASS、pending approval NEEDS_APPROVAL stage approval、granted 但 missing response NEEDS_INPUT stage response、granted + succeeded evidence PASS、denied BLOCKED stage approval、response succeeded 无 evidence BLOCKED stage response、unknown request NEEDS_INPUT、invalid envelope 不输出 payload summary、outside-root/unsafe 文件被拒、不写 ledger、人类输出紧凑。
- 更新 `docs/10-cli-poc-usage.md`，新增 `adapter gate check` 用法说明、JSON 结构、聚合规则与状态映射表。
- 更新 `tasks/progress.md` 记录本次进展。

- 新增 `docs/13-release-notes-adapter-envelope.md`，对 Adapter execution envelope 只读 gate 链路做阶段收口：覆盖 plan / validate / inspect / approval check / response check / gate check、只读安全边界、验证结果、已知限制与下一阶段建议。
- 更新 README 中英文文档列表，加入 `docs/13-release-notes-adapter-envelope.md`。

- 进入下一阶段：Task Runtime Bridge / Runtime Gate POC。
- 新增 `docs/14-task-runtime-bridge.md`，中文说明 task preflight / runtime gate / task event draft 如何衔接 adapter gate 与 task ledger：定义数据流、聚合规则、event draft 生成规则、CLI 用法和只读安全边界。
- 新增 `agent_runtime/runtime_gate.py`：实现 `check_runtime_gate`，按 `task_id` + `request_id` 读取 task snapshot、task event stream 和 adapter envelope，复用 `adapter_gate.check_adapter_gate`，聚合 task 状态与 gate 状态，生成建议的 task event draft。
- 更新 `agent_runtime/tasks.py`：`load_tasks` / `load_events` / `find_task` / `find_task_events` 支持可选的 `explicit_file` 参数，方便 `runtime gate check` 显式指定 ledger 文件；`_load_records` 兼容绝对路径输入。
- 更新 `agent_runtime/cli.py`：新增 `runtime gate check` 子命令，支持 `--task-id`、`--request-id`、`--envelope`、`--tasks-file`、`--events-file` 与全局 `--json`；输出包含 task 状态、gate 摘要和建议 event draft，均不回显完整 payload/evidence/raw_ref。
- 补充 `tests/test_runtime_gate.py`：覆盖 task running + gate pass、approval pending/denied、missing response、task 终态阻断、task 不存在、request 不存在、envelope 非法、人类输出脱敏、显式 ledger 文件、拒绝根目录外/不安全 ledger 路径、不写 ledger、终态优先阻断。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime gate check` 用法、JSON 结构、聚合规则、event draft 说明和行为约束。
- 更新 `README.md` 与 `README.en.md`：加入 `docs/14-task-runtime-bridge.md` 与 runtime gate check 能力说明。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger、不读取 `.env`/credential；输出不回显完整 `input` / `evidence` / `raw_ref` / `decision_ref`。
- 已跑 `python -m pytest`：167 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。
- 已抽查 `runtime gate check` 对 task-20260703-001 + req-20260703-002 返回 BLOCKED（task 已 finished），对缺失 task 返回 ERROR，对缺失 request 返回 NEEDS_INPUT，JSON 输出脱敏。
