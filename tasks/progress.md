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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

- 新增只读 `adapter validate` CLI 命令，用于校验 Adapter execution envelope JSON 文件。
- 新增 `agent_runtime/adapter_validation.py`：检查文件位于项目根目录内且为安全 `.json` 文件，使用 `jsonschema` 校验整个 envelope，失败时只输出相对路径、schema 错误路径/规则和简短摘要，不回显整条 artifact 或敏感值。
- 更新 `agent_runtime/cli.py`：在 `adapter` 子命令下新增 `validate`，支持 `--file` 与 `--json`。
- 命令保持只读：不执行 adapter、不访问网络、不写 ledger、不读取 `.env`/credential。
- 补充 `tests/test_adapter_validate.py`，覆盖：valid examples PASS、invalid JSON、schema invalid、outside-root、unsafe file、非 JSON 扩展名、JSON 输出、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md` 与 `tasks/progress.md`，记录 `adapter validate` 用法。
- 已跑 `python -m pytest`：99 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

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

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime gate check` 对 task-20260703-001 + req-20260703-002 返回 BLOCKED（task 已 finished），对缺失 task 返回 ERROR，对缺失 request 返回 NEEDS_INPUT，JSON 输出脱敏。

- 继续下一阶段：Runtime Ledger Audit。
- 新增 `docs/superpowers/specs/2026-07-04-runtime-ledger-audit-design.md` 与 `docs/superpowers/plans/2026-07-04-runtime-ledger-audit.md`，记录设计与实现计划。
- 新增 `agent_runtime/runtime_ledger.py`：实现 `check_runtime_ledger()` 与 `RuntimeLedgerResult`，复用 `ledger_consistency.check_ledger_consistency()` 做 tasks/events 基础一致性检查，复用 `adapter_validation._load_envelope()` 安全加载 envelope；检查 adapter_request.task_id / execution_event.task_id 是否存在于 task ledger、execution_event.request_id 是否引用已知 adapter_request、task ledger 中是否有 request_id 相关 event metadata/artifacts 线索（仅 warn）、task 已 terminal 但 envelope request 仍要求继续时 warn。
- 更新 `agent_runtime/cli.py`：新增 `runtime check-ledger` 子命令，支持 `--tasks-file`、`--events-file`、`--envelope` 与全局 `--json`；输出 compact 摘要（status / counts / findings / next_action），JSON 输出结构化且脱敏。
- 补充 `tests/test_runtime_ledger.py`：覆盖正常通过、缺失 request task_id、缺失 event task_id、缺失 event request_id、无 event metadata 线索 warn、task 终态 warn、ledger 一致性失败、非法 envelope、人类输出脱敏、不写 ledger。
- 新增 `docs/15-runtime-ledger-audit.md`：说明命令目标、非目标、核心概念、数据流、检查规则表、输出格式、CLI 用法、模块关系和安全边界。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime check-ledger` 用法说明。
- 更新 `docs/14-task-runtime-bridge.md`：将 `runtime check-ledger` 从候选列表中移除，并指向 `docs/15-runtime-ledger-audit.md`。
- 更新 `README.md`：在文档索引中加入 `docs/15-runtime-ledger-audit.md`，并在当前状态中补充 `runtime check-ledger`。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger、不读取 `.env`/credential；输出不回显完整 `input` / `evidence` / `raw_ref` / `decision_ref` / `target`。
- 已跑 `python -m pytest`：177 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime check-ledger` 对仓库样例文件返回 WARN，正确报告 `request-id-no-event-metadata` 与 `task-terminal-but-request-pending`，JSON 输出脱敏。

- 进入下一阶段：Runtime Plan POC。
- 新增 `docs/16-runtime-plan.md`，说明 `runtime plan` 的目标、非目标、数据流、输出格式、CLI 用法、状态映射、模块关系与安全边界。
- 新增 `agent_runtime/runtime_plan.py`：实现 `plan_runtime_action()` 与 `RuntimePlanResult`，读取 task ledger 确认 task 存在且非终态，复用 `adapter_plan.plan_adapter_action()` 生成 envelope 草案，再提取安全的 `request_draft`；当 preflight 为 `needs_approval` 时额外提取 `approval_draft` 与 `event_draft`。
- 更新 `agent_runtime/cli.py`：新增 `runtime plan` 子命令，支持 `--task-id`、`--adapter`、`--operation`、`--target`、`--actor`、`--tasks-file` 与全局 `--json` / `--agent` / `--policy-profile`；输出 compact 人类摘要或脱敏 JSON。
- 补充 `tests/test_runtime_plan.py`：覆盖 pass、needs_approval、terminal task blocked、missing task、unknown adapter、JSON 脱敏、人类输出、不写 ledger、agent profile 选择、显式 tasks-file。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime plan` 用法说明。
- 更新 `README.md` 与 `README.en.md`：加入 `docs/16-runtime-plan.md` 与 runtime plan 能力说明。
- 更新 `AGENTS.md`：在已实现的 CLI 能力、关键源文件、测试列表与设计文档索引中加入 `runtime plan`。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger、不读取 `.env`/credential；输出不回显完整 `input` / `evidence` / `raw_ref` / `decision_ref` / secret match。
- 已跑 `python -m pytest`：189 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime plan` 对 task-20260703-001 + shell-local read_file 因 task 已 finished 返回 BLOCKED；对 running task 返回 PASS 或 NEEDS_APPROVAL，JSON 输出脱敏。

- 扩展 `runtime plan` 支持 `--draft-json`，输出完整但脱敏的 envelope 机器草案。
- 修改 `agent_runtime/runtime_plan.py`：`RuntimePlanResult` 新增 `envelope_draft` 字段；`plan_runtime_action()` 在 task 非终态且 envelope schema 校验通过后，把完整 envelope 存入 `envelope_draft`。
- 修改 `agent_runtime/cli.py`：`runtime plan` 子命令新增 `--draft-json` 参数；`_emit_runtime_plan_result()` 在 `--draft-json` 时输出 `{status, task_id, task_status, envelope_draft, findings, next_action}`；普通 `--json` 仍保持 compact 摘要，不包含 `envelope_draft`。
- 安全约束：`envelope_draft` 复用 `adapter_plan.plan_adapter_action()` 已做 schema 校验的 envelope；`input` payload 仅含 `operation`/`target`；`decision_ref` 为 `null`；不存在 `raw_ref`；task 终态/缺失时 `envelope_draft` 为 `null`。
- 补充 `tests/test_runtime_plan.py`：覆盖 `--draft-json` schema 校验通过、needs_approval 包含 approval/event、terminal task 不输出 draft、draft 中不含 raw_ref/decision_ref 真实值、普通 `--json` 兼容、不写 ledger。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime plan --draft-json` 用法、输出结构与行为约束。
- 更新 `docs/16-runtime-plan.md`：新增 `--draft-json` 详细说明与安全约束。
- 更新 `README.md` 与 `README.en.md`：当前状态中补充 `--draft-json` envelope draft 输出能力。
- 更新 `AGENTS.md`：在已实现的 CLI 能力与 `runtime plan` 关键源文件说明中加入 `--draft-json`。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger、不读取 `.env`/credential。
- 已跑 `python -m pytest`：195 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime plan --draft-json` 对 running task + shell-local read_file 输出 schema 合法 envelope；对 github-cli git_push 输出含 approval_record 与 approval_requested event；对 finished task 输出 `envelope_draft: null`。


- Runtime read-only planning bridge 阶段收口。
  - 新增 `agent_runtime/runtime_draft.py`：支持 `runtime draft validate` 与 `runtime draft inspect`，可从项目内安全 `.json` 文件或 stdin 读取 direct envelope / `runtime plan --draft-json` wrapper，并复用 envelope schema + consistency 校验。
  - 更新 `agent_runtime/cli.py`：新增 `runtime draft validate --file/--stdin` 与 `runtime draft inspect --file/--stdin`，inspect 输出 compact 摘要，不回显完整 target/input/evidence/raw_ref/decision_ref。
  - 新增 `tests/test_runtime_draft.py`：覆盖 file/stdin validate、outer wrapper、schema invalid、consistency invalid、inspect summary/JSON、安全路径、不写文件、安全输出。
  - 新增 `docs/17-runtime-planning-bridge.md` 与 `docs/18-release-notes-runtime-planning-bridge.md`，描述 runtime planning bridge 闭环与阶段 release 收口。
  - 已跑 `python -m pytest`：207 passed。
  - 已跑 `python -m agent_runtime.cli doctor`：PASS。
  - 已跑 `python tools/public_scan.py`：OK public scan。

- Runtime Report 只读聚合报告阶段收口。
  - 新增 `agent_runtime/runtime_report.py`：实现 `check_runtime_report()` 与 `RuntimeReportResult`，聚合 task snapshot、event summary、runtime draft/envelope inspect、runtime gate、runtime ledger audit、blockers 与 next_action。
  - 更新 `agent_runtime/cli.py`：新增 `runtime report` 子命令，支持 `--task-id`、`--request-id`、`--envelope`、`--tasks-file`、`--events-file` 与全局 `--json`。
  - 新增 `tests/test_runtime_report.py`：覆盖文本摘要、JSON 脱敏、terminal task blocked、只读不改文件。
  - 新增 `docs/19-runtime-report.md` 与 `docs/20-release-notes-runtime-report.md`：描述 runtime report 设计与 v0.4 阶段 release 收口。
  - 新增 `tasks/handoff-2026-07-05.md`：记录 v0.4 Runtime Report 阶段接续上下文、验证结果、安全边界与下一阶段建议。
  - 更新 `docs/10-cli-poc-usage.md`、`README.md`、`README.en.md`：补充 `runtime report` 用法与当前能力说明。
  - 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger/envelope、不读取 `.env`/credential；输出不回显完整 target/input/evidence/raw_ref/decision_ref。
  - 已跑 `python -m pytest`：211 passed。
  - 已跑 `python -m agent_runtime.cli doctor`：PASS。
  - 已跑 `python tools/public_scan.py`：OK public scan。
  - 已推送 main：`7aa092f Add read-only runtime report`。
  - 阶段冻结 tag：`v0.4.0-runtime-report`。

- Controlled Write Boundaries 受控写入边界设计完成。
  - 新增 `docs/21-controlled-write-boundaries.md`：定义从只读 Runtime 进入最小受控写入前的边界。
  - 明确本阶段不新增真实写入命令，不执行 adapter、不访问网络、不发送消息、不删除文件、不读取 credential。
  - 定义 `draft export` 与 `event append` 两类最低风险写入的允许路径、写前校验、写后校验、dry-run/commit 语义、overwrite 限制、append-only 规则与回滚恢复策略。
  - 明确审批语义必须收窄为 this command + this task_id + this request_id + this target path + this input hash，禁止泛化为长期授权。
  - 更新 `README.md` 与 `README.en.md` 文档索引。

## 2026-07-05

- 进入下一阶段：最小 Controlled Write POC 第一步 —— `runtime draft export --dry-run`。
- 新增 `agent_runtime/runtime_draft_export.py`：实现 `dry_run_export()` 与 `DraftExportResult`。
  - 复用 `runtime_draft._load_runtime_draft` / `_validate_envelope` / `_build_draft_summary` 加载并校验 direct envelope 与 `runtime plan --draft-json` wrapper。
  - 实现输出路径守卫：必须在项目根目录内、后缀 `.json`、不能路径逃逸、不能指向 credential/git internals、默认禁止覆盖已存在文件。
  - 复用 `agent_runtime.policy.check_text` 做 secret pattern 扫描，复用 `tools/public_scan.py` 的 `SCAN_RULES` 做 public-release 风险扫描；命中时只输出规则 id 与行号，不回显完整匹配值。
  - dry-run 通过时返回 `would_write=false`、校验状态、artifact counts 与 next_action；不写入任何文件。
- 更新 `agent_runtime/cli.py`：新增 `runtime draft export` 子命令，支持 `--file`/`--stdin`、`--output`、强制 `--dry-run`、全局 `--json`。
  - 未提供 `--dry-run` 时返回 `error`，提示仅支持 dry-run。
  - 人类/JSON 输出不回显完整 `target` / `input` / `raw_ref` / `decision_ref` / evidence description。
- 新增 `tests/test_runtime_draft_export.py`，覆盖：
  - stdin direct envelope dry-run pass 且不写文件。
  - file wrapper dry-run pass。
  - schema invalid / consistency invalid 返回 `validation_failed`。
  - 路径逃逸（`..`）被 block。
  - 错误后缀（`.txt`）被 block。
  - 已存在输出文件被 block 且原文件不被修改。
  - secret pattern（GitHub token）被 block 且不回显完整 token。
  - public scan（Windows 绝对路径）被 block 且不回显完整路径。
  - JSON 输出不含完整 target / input / raw_ref / decision_ref / evidence description。
- 新增 `docs/22-runtime-draft-export-dry-run.md`：说明命令目标、CLI 用法、路径守卫、扫描规则、输出格式、错误状态与安全边界。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime draft export --dry-run` 用法示例。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/22-runtime-draft-export-dry-run.md`，当前状态补充 dry-run 导出能力。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除文件、不写真实 ledger/envelope、不读取 `.env`/credential。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests -q`：221 passed（新增 10 个测试）。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime draft export --dry-run` 对 running task + shell-local read_file 输出 PASS 且不创建目标文件；对含 GitHub token 的 draft 返回 BLOCKED 且不回显 token。

- Runtime Draft Export Dry-run 阶段正式收口。
  - 新增 `docs/23-release-notes-runtime-draft-export-dry-run.md`：记录 v0.5 阶段定位、新增能力、安全边界、验证结果与后续建议。
  - 新增 `tasks/handoff-2026-07-05-draft-export.md`：记录 v0.5 接续上下文、当前链路、恢复命令、安全边界和下一阶段建议。
  - 更新 `README.md` 与 `README.en.md` 文档索引。
  - 阶段冻结 tag：`v0.5.0-runtime-draft-export-dry-run`。

## 2026-07-05（续）

- 进入下一阶段：最小 Controlled Write POC 第二步 —— `runtime draft export --commit`。
- 扩展 `agent_runtime/runtime_draft_export.py`：
  - 新增 `export_draft(..., commit=False)` 统一入口；保留 `dry_run_export` 兼容旧调用。
  - 新增 `committed`、`post_validate`、`post_inspect` 字段到 `DraftExportResult`。
  - commit 路径复用 dry-run 全部预检（load/validate/path guard/scan）。
  - 新增 `drafts/runtime/` 路径守卫：commit 模式下 `--output` 必须位于 `drafts/runtime/...`。
  - 写入格式稳定：`json.dumps(..., ensure_ascii=False, indent=2) + "\n"`。
  - 写入后调用 `validate_runtime_draft` 与 `inspect_runtime_draft` 做二次校验。
  - 失败回滚：post-write 校验失败时 `unlink()` 半写入文件；回滚失败时返回 `rollback-failed`。
- 更新 `agent_runtime/cli.py`：
  - `--dry-run` 与 `--commit` 改为两个独立标志，由命令逻辑保证互斥与必选一个。
  - 都不提供或同时提供时返回结构化 `error` 结果。
  - 渲染函数输出 `Committed`/`Post validate`/`Post inspect`。
- 新增 `tests/test_runtime_draft_export_commit.py`，覆盖：
  - commit pass 写入新文件且内容可被 `runtime draft validate` 通过。
  - commit 自动创建 `drafts/runtime/...` 父目录。
  - dry-run 仍不写文件。
  - `--dry-run`/`--commit` 互斥报错。
  - 二者都不提供报错。
  - commit 输出不在 `drafts/runtime/` 下被 block。
  - 已存在输出文件被 block 且不覆盖。
  - schema invalid 时不写文件。
  - secret/public scan 命中时不写文件且不回显。
  - post-validation 失败触发回滚、文件被删除。
- 新增 `docs/24-runtime-draft-export-commit.md`：说明 commit 目标、CLI 用法、路径守卫、写入/回滚、扫描、错误状态。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime draft export --commit` 用法与约束。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/24-runtime-draft-export-commit.md`，当前状态补充 `--commit` 能力与边界。
- 保持安全边界：不执行 adapter、不访问网络、不发送消息、不删除非本命令创建的文件、不写 task/event ledger、不读取 `.env`/credential。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests -v`：232 passed（新增 11 个测试）。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime draft export --commit` 对 shell-local read_file 写入 `drafts/runtime/.../*.json` 并通过 post validate/inspect；对 schema invalid 和已存在文件均不写且正确报错。

- Runtime Draft Export Commit 阶段正式收口。
  - 新增 `docs/25-release-notes-runtime-draft-export-commit.md`：记录 v0.6 阶段定位、新增能力、写入边界、验证结果与后续建议。
  - 新增 `tasks/handoff-2026-07-05-draft-export-commit.md`：记录 v0.6 接续上下文、当前链路、恢复命令、安全边界和下一阶段建议。
  - 更新 `README.md` 与 `README.en.md` 文档索引。
  - 阶段冻结 tag：`v0.6.0-runtime-draft-export-commit`。

## 2026-07-05（续）

- 进入下一阶段：最小 Controlled Write POC 第三步 —— `runtime event append --dry-run`。
- 新增 `agent_runtime/runtime_event_append.py`：实现 `append_event_dry_run()`，读取候选 event（`--file` 安全 `.json` 或 `--stdin`），做 schema 校验、task_id 存在性检查、模拟追加后的 ledger consistency、可选 runtime ledger audit、secret/public scan。
  - 使用临时 JSONL 文件模拟 append，检查后删除临时文件，不触碰真实 `tasks/events.jsonl`。
  - 输出只包含安全摘要：event_id、task_id、event_type、from/to status、would_append=false、ledger_check、runtime_audit、metadata_keys、artifact_count 等，不回显完整 message/metadata/artifacts/evidence。
  - secret/public scan 命中时返回 BLOCKED 且不回显完整匹配值。
- 更新 `agent_runtime/cli.py`：新增 `runtime event append` 子命令，支持 `--file`/`--stdin`、`--dry-run`、`--tasks-file`、`--events-file`、`--envelope` 与全局 `--json`。
  - 未提供 `--dry-run` 时返回 `error`。
- 新增 `tests/test_runtime_event_append_dry_run.py`，覆盖：pass、stdin、schema invalid、missing task、illegal transition、secret/public scan blocked、with envelope audit、JSON 脱敏、安全摘要输出、未提供 `--dry-run` 报错。
- 新增 `docs/26-runtime-event-append-dry-run.md`：说明命令目标、CLI 用法、校验链路、输出格式、安全边界与后续建议。
- 新增 `tasks/handoff-2026-07-05-event-append-dry-run.md`：记录当前上下文、恢复命令、验证结果和下一步建议。
- 更新 `docs/10-cli-poc-usage.md`、`README.md`、`README.en.md`、`tasks/progress.md`。
- 保持只读边界：不执行 adapter、不访问网络、不发送消息、不删除真实文件、不写 task/event ledger、不读取 `.env`/credential。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest`：243 passed。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。
- 已抽查 `runtime event append --dry-run` 对合法 candidate event返回 PASS 且不写 events file；对非法状态流转返回 VALIDATION_FAILED；对含 GitHub token 的 message 返回 BLOCKED 且不回显 token。

- Runtime Event Append Dry-run 阶段正式收口。
  - 新增 `docs/27-release-notes-runtime-event-append-dry-run.md`：记录 v0.7 阶段定位、检查内容、安全摘要、验证结果与后续建议。
  - 更新 `docs/26-runtime-event-append-dry-run.md`：同步当前安全摘要输出示例。
  - 更新 `tasks/handoff-2026-07-05-event-append-dry-run.md`：记录 v0.7 tag、验证结果和下一步建议。
  - 更新 `README.md` 与 `README.en.md` 文档索引。
  - 阶段冻结 tag：`v0.7.0-runtime-event-append-dry-run`。

- 留下下一阶段预备文档：`runtime event append --commit`。
  - 新增 `docs/28-runtime-event-append-commit.md`：仅作为下次实现前的边界与方案上下文，不实现代码、不修改 Runtime 行为。
  - 文档明确 append-only、写前 dry-run 全检查、event_id 去重、写后 validate/check-ledger/runtime audit、失败回滚、输出脱敏和 v0.8 建议 tag。
  - 更新 `README.md` 与 `README.en.md` 文档索引，便于下次从文档入口恢复。

## 2026-07-06

- 实现下一阶段：最小 Controlled Write POC 第四步 —— `runtime event append --commit`。
- 扩展 `agent_runtime/runtime_event_append.py`：
  - 保留 `append_event_dry_run()` 兼容已有调用；新增 `append_event(..., commit=False)` 统一入口。
  - commit 路径复用 dry-run 全部预检（候选 event 读取、schema 校验、task_id 存在性、event_id 去重、secret/public scan、模拟 append 后 ledger consistency、可选 runtime ledger audit）。
  - 新增 `_resolve_commit_events_path()` 与 `_has_trailing_newline()`：目标 events file 必须位于项目根目录内、后缀 `.jsonl`、不是 sample/credential/git internals；非空文件缺少末尾换行时直接 blocked。
  - 写入格式：`json.dumps(candidate, ensure_ascii=False) + "\n"`，只追加单行，不修改历史内容。
  - 写入后调用 `validate_records()`、`check_ledger_consistency()`，如有 envelope 再调用 `check_runtime_ledger()`。
  - 失败回滚：记录写入前原始 byte size 与是否新建文件；post-check 失败时截断回原大小或删除新文件；回滚成功后返回 `validation_failed`，回滚失败时返回 `error`。
  - 修复 post runtime audit 的 warn 状态判断（原 WIP 误用 `"warning"`，实际状态为 `"warn"`）。
- 更新 `agent_runtime/cli.py`：
  - `runtime event append` 新增 `--commit` 标志，与 `--dry-run` 由命令逻辑保证互斥且必选一个。
  - 渲染函数输出 `committed`、`post_validate`、`post_ledger_check`、`post_runtime_audit`、`rolled_back`、`rollback_error`。
- 新增 `tests/test_runtime_event_append_commit.py`，覆盖：
  - commit pass 追加一行且写后检查通过。
  - commit with envelope 写后 runtime audit 执行。
  - `--dry-run` 不写文件。
  - `--dry-run`/`--commit` 互斥报错。
  - 二者都不提供报错。
  - schema invalid 不写文件。
  - missing task 不写文件。
  - duplicate event_id 不写文件。
  - illegal transition 不写文件。
  - secret/public scan blocked 不写文件且不回显匹配值。
  - events file 不在项目内 blocked。
  - events file 后缀非 `.jsonl` blocked。
  - 无末尾换行 blocked。
  - post-check 失败触发回滚。
  - stdin commit pass。
  - JSON 输出脱敏。
- 更新 `docs/28-runtime-event-append-commit.md`：从预备设计改为实现文档，补充 CLI 形态、输出字段、实现文件与测试文件说明。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime event append --commit` 用法、约束与回滚说明。
- 更新 `README.md` 与 `README.en.md`：当前状态中补充 `runtime event append --commit` 能力与边界。
- 更新 `tasks/handoff-2026-07-05-event-append-dry-run.md`：说明 `--commit` 已实现，指向本日进度。
- 保持安全边界：不执行 adapter、不访问网络、不发送消息、不删除非本命令追加的内容、不写 task ledger / envelope、不读取 `.env`/credential。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

- 进入下一阶段：为未来 task snapshot 受控写入做预检门禁 —— `runtime task create --dry-run`。
- 新增 `agent_runtime/runtime_task_create.py`：实现 `create_task_dry_run()`，只读模拟创建 task snapshot。
  - 候选 task 必须是单个 JSON object，通过 `tasks/task.schema.json`。
  - 检查 `task.id` 在目标 task ledger 中不得重复。
  - 目标 task ledger 路径必须位于项目根目录内、后缀 `.jsonl`、不能指向 credential/git internals。
  - secret/public scan 命中时 blocked 且不回显完整匹配值。
  - 用临时 task ledger 追加 candidate，配合现有 events ledger 跑 `task check-ledger`；events ledger 不存在时使用空临时文件，允许新 task 暂时无对应事件。
  - 输出安全摘要：source、task_id、task_status、title_present、assignee_present、tag_count、artifact_count、evidence_count、would_create=False、ledger_check；不回显 title 内容、summary、evidence description 等自由文本。
- 更新 `agent_runtime/cli.py`：新增 `runtime task create` 子命令，支持 `--file`/`--stdin`、`--dry-run`、`--tasks-file`、`--events-file` 与全局 `--json`。
  - `--dry-run` 必须显式提供；`--commit` 虽预留参数但返回 `commit-not-implemented` 错误。
- 新增 `tests/test_runtime_task_create_dry_run.py`，覆盖：
  - dry-run pass（含无现有 events ledger 的情况）。
  - stdin 输入。
  - schema invalid / candidate 非 object。
  - 重复 task id。
  - secret scan / public scan blocked 且不回显（public scan 测试值在内存中动态拼接）。
  - task ledger 路径在项目根目录外 / 后缀不安全。
  - dry-run 不写真实 task ledger。
  - JSON 输出脱敏。
  - 未提供 `--dry-run` / 传入 `--commit` 报错。
- 新增 `docs/31-runtime-task-create-dry-run.md`：说明命令目标、CLI 用法、校验链路、输出格式、无对应 event 的处理、安全边界与测试覆盖。
- 更新 `docs/10-cli-poc-usage.md`：新增 `runtime task create --dry-run` 用法与约束。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/31-runtime-task-create-dry-run.md`，当前状态补充 `runtime task create --dry-run` 能力与边界。
- 保持安全边界：不实现 `--commit`、不写 `tasks/tasks.jsonl`、不写 `tasks/events.jsonl`、不执行 adapter、不访问网络、不发送消息、不读取 `.env`/credential、不回显完整 secret match / evidence description / summary。
- 不生成 `docs/superpowers/...`，不改 `AGENTS.md`。


## 2026-07-07 — Runtime Task Create Commit

- 实现 `runtime task create --commit`，把 task create dry-run 门禁扩展为受控写入。
  - 复用 candidate 读取、schema validation、task id 去重、secret/public scan、临时 ledger 模拟 append 与 ledger consistency。
  - 唯一写入动作：向 task ledger JSONL 末尾追加 exactly one JSON object。
  - 不自动写 event ledger；如需 created event，需后续显式执行 `runtime event append --commit`。
  - commit target guard：项目根内、安全 `.jsonl`、禁止 sample ledger（`tasks/examples.jsonl` 与 `*.examples.jsonl`）、禁止 `.git` / credential / secret 路径。
  - 现有非空 tasks file 无末尾换行时 blocked；父目录不存在时 blocked；不自动修复历史 ledger。
  - 写前记录原始 byte size；写后运行 task schema validate 与 ledger consistency；失败时 truncate 回原 byte size，若本命令新建文件则删除。
  - 输出安全摘要：task_id、task_status、title_present、assignee_present、tag_count、artifact_count、evidence_count、would_create、ledger_check、committed、post_validate、post_ledger_check、rolled_back；不回显 title / summary / evidence description / secret match。
- 更新 `agent_runtime/cli.py`：`runtime task create` 支持 `--dry-run` / `--commit` 显式互斥二选一，移除 `commit-not-implemented` 分支。
- 新增 `tests/test_runtime_task_create_commit.py`，覆盖 commit pass、新建 ledger、dry-run 不写、互斥/缺失模式、schema invalid、duplicate、secret/public scan、路径逃逸、后缀不安全、sample ledger、git internals、尾部无换行、post-check 回滚、stdin commit、JSON 输出脱敏。
- 更新 `docs/10-cli-poc-usage.md`、`docs/34-release-notes-runtime-task-create-commit.md`、README/README.en、AGENTS.md。
- 验证：`python -m pytest -q` 通过；`python -m agent_runtime.cli doctor` PASS；`python tools/public_scan.py` OK；`git diff --check` PASS。

## 2026-07-07（续）— Runtime Task Create Smoke / Report Loop

- 补 `runtime task create --commit` 端到端 smoke loop，覆盖：task create dry-run -> task create commit -> event append dry-run -> event append commit -> task validate / task check-ledger -> runtime report。
- 新增 `tests/test_runtime_task_create_smoke_loop.py`：在 `tmp_path` 构造临时项目根、空 ledger、candidate task/event、envelope，断言每一步状态与 ledger 行数，且输出不泄露 `title` / `summary` / `evidence description` / `artifact payload`。
- 修复 `runtime report` 人类输出泄露 task title 的问题：`agent_runtime/runtime_report.py` 的 `_sanitize_task_snapshot` 不再保留 `title`，改为 `title_present`；`agent_runtime/cli.py` 的 report 渲染不再打印完整 title。
- 新增 `docs/35-runtime-task-create-smoke.md`：说明 smoke loop 目标、步骤、安全边界、输出示例与验证结果。
- 更新 `docs/10-cli-poc-usage.md`：新增 "Runtime Task Create Smoke / Report Loop" 小节，并同步 `runtime report` 文本输出示例。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/35-runtime-task-create-smoke.md`。
- 验证：`python -m pytest tests/test_runtime_task_create_smoke_loop.py tests/test_runtime_report.py -q` 通过；`python -m agent_runtime.cli doctor` PASS；`python tools/public_scan.py` OK；`git diff --check` PASS。
- 不新增真实写入权限；本阶段不打 tag。

## 2026-07-07（再续）— Controlled Write Regression

- 新增 `docs/36-controlled-write-regression.md`：梳理三个受控写入点（`runtime draft export --commit`、`runtime event append --commit`、`runtime task create --commit`）的唯一写入目标、path guard、post-check、rollback、输出脱敏；列出必须保持只读的命令。
- 新增 `tests/test_controlled_write_regression.py`：在 `tmp_path` 临时项目根中跑通 task create dry-run/commit -> event append dry-run/commit -> task validate/check-ledger -> runtime report，断言 ledger 行数、report 不泄露 title/message、仓库真实 ledger 不被修改。
- 更新 `.github/workflows/ci.yml`：在 ledger smoke checks 后新增 `Run controlled write regression tests` 步骤，显式跑受控写入回归测试。
- 更新 `docs/10-cli-poc-usage.md`：新增 "Controlled Write Regression" 小节，说明本地/CI 命令与断言。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/36-controlled-write-regression.md`。
- 不新增任何写权限，不进入 adapter execution；本阶段不打 tag。
- 验证：`python -m pytest tests/test_controlled_write_regression.py -q` 通过；`python -m pytest -q` 通过；`python -m agent_runtime.cli doctor` PASS；`python tools/public_scan.py` OK；`git diff --check` PASS。


## 2026-07-07（四续）— Runtime Event Import Dry-run 预备设计

- 新增 `docs/37-runtime-event-import-dry-run.md`：仅设计，不实现 CLI，不新增写权限。
- 设计未来 `runtime event import --dry-run` 的批量语义：JSONL 输入、all-or-nothing preflight、输入顺序即模拟导入顺序、不允许部分成功。
- 明确候选 event 批量预检需覆盖：schema validation、candidate 内部重复 event_id、与现有 ledger 重复 event_id、引用不存在 task、非法状态迁移、secret/public scan 与输出脱敏。
- 明确未来 commit 阶段必须另写设计，不能直接从 dry-run 推导。
- 更新 README / README.en 文档索引与 `docs/10-cli-poc-usage.md` 用法说明。
- 不实现 `runtime event import` CLI，不写 ledger，不新增任何写权限。

## 2026-07-07（五续）— Runtime Event Import Dry-run 实现

- 实现 `runtime event import --dry-run` 批量 event 预检命令。
- 新增 `agent_runtime/runtime_event_import.py`：
  - 读取候选 `.jsonl` 文件，逐行解析并校验 JSON 语法、object 形状、`tasks/event.schema.json`。
  - 对每行 candidate 执行 secret scan 与 public scan，命中时 blocked 且不回显完整匹配值。
  - 检测 candidate 内部重复 `event_id`、与现有 event ledger 重复 `event_id`、引用不存在 task。
  - 在临时文件中模拟 `existing events + candidate events in input order`，运行 `task validate --schema event` 与 `task check-ledger` 等价检查；检查后删除临时文件。
  - 批量语义为 all-or-nothing preflight；输入顺序即模拟顺序；不自动排序。
  - 输出安全摘要：`event_count`、`blank_line_count`、`task_count`、`event_type_counts`、`candidate_event_ids_present`、`would_import`、`ledger_check` 等，不回显 `message` / metadata / artifacts / evidence / target / input / raw_ref / decision_ref / secret match。
- 更新 `agent_runtime/cli.py`：新增 `runtime event import` 子命令，支持 `--file`（必填）、`--dry-run`（必填）、`--tasks-file`、`--events-file` 与全局 `--json`；不实现 `--commit`。
- 新增 `tests/test_runtime_event_import_dry_run.py`，覆盖：
  - dry-run pass（单 event / 多 event / 多 task）。
  - 输入文件不存在、项目根外、后缀非 `.jsonl`、位于 `.git` 路径下。
  - invalid JSON、非 object 行、schema invalid。
  - candidate 内部重复 event_id、与现有 ledger 重复 event_id。
  - 引用不存在 task、非法状态迁移。
  - secret scan / public scan blocked 且输出脱敏。
  - 空行计数与忽略行为。
  - dry-run 不修改真实 events/tasks ledger。
  - JSON 输出脱敏。
  - 未提供 `--dry-run` 报错。
- 新增 `docs/38-release-notes-runtime-event-import-dry-run.md`：阶段收口说明，含能力、批量语义、检查内容、输出摘要、安全边界、验证结果与后续建议。
- 更新 `docs/10-cli-poc-usage.md`：将 "Runtime Event Import Dry-run 预备设计" 改为实现说明与 CLI 示例。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/38-release-notes-runtime-event-import-dry-run.md`，当前状态补充 `runtime event import --dry-run`。
- 保持安全边界：不实现 `--commit`、不写真实 ledger、不执行 adapter、不访问网络、不发送消息、不读取 `.env`/credential、不删除文件。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests/test_runtime_event_import_dry_run.py -q`：通过。
- 已跑 `python -m pytest -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-07（六续）— Runtime Event Import Commit 设计

- 新增 `docs/39-runtime-event-import-commit-design.md`：为未来 `runtime event import --commit` 独立定义事务边界，不从 dry-run 直接推导实现。
- 设计重点：
  - commit 必须采用 all-or-nothing append transaction，不允许部分成功。
  - commit 内部必须重跑 preflight，不信任“之前 dry-run 通过过”。
  - 明确 dry-run / commit 一致性问题：candidate 内容变化、目标 ledger 在两次调用间变化、plan hash / ledger fingerprint 的必要性。
  - 明确推荐的 commit 流程：preflight reload -> write preparation -> append block -> post-check -> success summary。
  - 明确 rollback 策略：第一版建议继续采用 byte-size truncate rollback。
  - 明确第一版保守边界：不允许目标 `events_file` 不存在；只允许向现有 ledger 文件尾部追加连续 block；post-check 必须跑 `task validate --schema event` + `task check-ledger`。
  - 明确输出脱敏、删除边界、是否要求 dry-run、是否允许自动排序、是否允许 JSON array 输入等风险决策。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/39-runtime-event-import-commit-design.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。

## 2026-07-07（七续）— Runtime Event Import Consistency Freeze 设计

- 新增 `docs/41-runtime-event-import-consistency-freeze.md`：定义 `runtime event import --dry-run` 与 `--commit` 之间的一致性冻结策略，避免出现“dry-run 审阅的是 A，commit 提交的是 B”的时间差风险。
- 设计重点：
  - 区分两类风险：candidate 文件在 dry-run 后被改动、目标 events ledger 在 dry-run 与 commit 之间发生变化。
  - 引入 `candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count` 与 `plan_hash` 的建议字段。
  - 明确 `plan_hash` 应基于 candidate fingerprint、目标 ledger fingerprint、目标路径与事务语义等稳定字段计算，不替代 commit 内部 preflight，只补“审阅上下文一致性”这一层。
  - 建议 dry-run 默认输出 freeze 信息，commit 可选接收 `--expected-plan-hash`；若显式提供，则在 preflight 前先做 freeze 比对，mismatch 一律 `blocked`。
  - 第一版建议先冻结 candidate + events ledger，不强制冻结 tasks ledger；也不把 freeze 做成 commit 默认硬门槛。
  - 明确 freeze 失败输出只能回显 hash / 相对路径 / byte size / line count 等安全摘要，不得回显 candidate 原始 JSON 行与敏感字段。
- 更新 `README.md` / `README.en.md` 文档索引，加入 `docs/41-runtime-event-import-consistency-freeze.md`。
- 本阶段只写设计，不实现 CLI，不新增真实写权限，不改 Runtime 行为。


## 2026-07-07（七续）— Runtime Event Import Commit 实现

- 实现 `runtime event import --commit` 批量 event 受控追加命令。
- 修改 `agent_runtime/runtime_event_import.py`：
  - 新增 `EventImportCommitResult` 数据类，输出安全摘要。
  - 抽公共 preflight 为 `_run_preflight`，dry-run 与 commit 共用；commit 调用时通过 `require_events_file_exists=True` 要求目标 events ledger 必须已存在。
  - `import_events_commit` 按 `preflight -> target guard -> write preparation -> append block -> post-check -> rollback` 顺序执行。
  - 写入前记录 `original_size_bytes`；写入失败或 post-check 失败时按原始 byte size truncate 回滚。
  - rollback 失败时返回 `rollback_error`。
- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--commit` 参数。
  - `--dry-run` / `--commit` 互斥；都不传时报错 `missing-import-mode`。
  - 渲染函数同时处理 dry-run 与 commit 结果，输出保持脱敏。
- 新增 `tests/test_runtime_event_import_commit.py`，覆盖：
  - commit pass（多个 event 作为连续 block 成功追加）。
  - `--dry-run` / `--commit` 互斥。
  - 两者都不传时报错。
  - candidate 文件不存在 / 根外 / 后缀非 `.jsonl` / 位于 `.git` 路径下。
  - invalid JSON / 非 object / schema invalid。
  - candidate 内部重复 `event_id`、与现有 ledger 重复 `event_id`。
  - unknown task、非法状态迁移。
  - secret scan / public scan blocked 且输出脱敏。
  - events ledger 不存在 -> blocked。
  - events ledger 非空但末尾无换行 -> blocked。
  - post-check `task validate` / `task check-ledger` 失败触发回滚。
  - 写入中途 OSError 触发回滚。
  - rollback 失败时正确报告 `rollback_error`。
  - commit 不修改 task ledger。
  - JSON 输出脱敏。
- 新增 `docs/40-release-notes-runtime-event-import-commit.md`：阶段收口说明，含能力、事务语义、commit 流程、输出摘要、安全边界、测试覆盖、验证结果与已知限制。
- 更新 `docs/10-cli-poc-usage.md`：将 "Runtime Event Import Dry-run" 扩展为 "Runtime Event Import"，补充 `--commit` 用法、成功示例与互斥约束。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/40-release-notes-runtime-event-import-commit.md`，当前状态与边界补充 `runtime event import --dry-run` / `--commit`。
- 保持安全边界：不执行 adapter、不访问网络、不发送消息、不读取 `.env`/credential、不删除文件；`--commit` 仅向已存在的 event ledger 追加连续 block，失败则回滚。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests/test_runtime_event_import_commit.py -q`：通过。
- 已跑 `python -m pytest tests/test_runtime_event_import_dry_run.py -q`：通过。
- 已跑 `python -m pytest -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。


## 2026-07-07（八续）— Runtime Event Import Consistency Freeze 实现

- 实现 `runtime event import` 一致性冻结最小链路。
- 修改 `agent_runtime/runtime_event_import.py`：
  - 新增 `_FreezeState` 与 freeze 计算辅助函数：`_sha256_hex`、`_compute_candidate_fingerprint`、`_compute_events_ledger_fingerprint`、`_compute_plan_hash`、`_compute_freeze_state`。
  - `candidate_fingerprint`：candidate 文件非空原始行按输入顺序用 `\n` 拼接后 sha256。
  - `events_ledger_fingerprint`：目标 events ledger 完整 UTF-8 字节 sha256；不存在时 fingerprint 为 `null`。
  - `plan_hash`：稳定 JSON object canonical `json.dumps(..., sort_keys=True, separators=(",", ":"))` 后 sha256。
  - 扩展 `EventImportDryRunResult` 与 `EventImportCommitResult`，承载 freeze 字段。
  - `import_events_dry_run` 默认输出 `plan_hash`、`candidate_fingerprint`、`events_ledger_fingerprint`、`events_ledger_size_bytes`、`events_ledger_line_count`、`freeze_mode=advisory`。
  - `import_events_commit` 新增 `expected_plan_hash` 参数；在 preflight 前先 resolve candidate 路径并计算 freeze；若提供 `--expected-plan-hash` 且不一致，立即返回 `blocked`。
- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--expected-plan-hash` 参数。
  - 渲染函数输出 dry-run freeze 字段与 commit `freeze_check` / `expected_plan_hash` / `current_plan_hash`。
- 新增 `tests/test_runtime_event_import_freeze.py`，覆盖：
  - dry-run 输出 freeze 字段。
  - 同一输入重复 dry-run `plan_hash` 稳定。
  - candidate 改一行后 `plan_hash` 改变。
  - events ledger 改变后 `events_ledger_fingerprint` 与 `plan_hash` 改变。
  - commit 传正确 `--expected-plan-hash` 时通过。
  - commit 在 dry-run 后 candidate 文件被改动时 blocked。
  - commit 在 dry-run 后 events ledger 变化时 blocked。
  - mismatch 输出脱敏，不回显 candidate 原始 JSON 行。
  - 不提供 `--expected-plan-hash` 时，现有 commit 行为保持不变。
  - JSON 输出包含 freeze 字段但不泄露敏感内容。
- 新增 `docs/42-release-notes-runtime-event-import-consistency-freeze.md`：阶段收口说明，含能力、plan hash 输入、输出摘要、安全边界、测试覆盖、验证结果与已知限制。
- 更新 `docs/10-cli-poc-usage.md`：在 Runtime Event Import 章节新增 Consistency Freeze 小节，说明 dry-run freeze 字段与 `--expected-plan-hash` 用法。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/42-release-notes-runtime-event-import-consistency-freeze.md`，当前状态补充一致性冻结能力。
- 保持安全边界：不强制全局 always-on freeze、不冻结 tasks ledger、不实现 `--require-dry-run`、不访问网络、不读取 `.env`/credential。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests/test_runtime_event_import_freeze.py -q`：通过。
- 已跑 `python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q`：通过。
- 已跑 `python -m pytest -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。


## 2026-07-07（九续）— Controlled Write Regression 扩展：Event Import

- 把 `runtime event import --commit` 与 consistency freeze 纳入 controlled write regression 保护。
- 不新增写入能力，只补测试与文档。
- 修改 `tests/test_controlled_write_regression.py`：
  - 新增 `test_controlled_write_regression_event_import_does_not_touch_real_ledgers`。
  - 在临时项目根中完成：task create commit -> event append commit -> event import dry-run -> event import commit with `--expected-plan-hash` -> freeze mismatch blocked -> post-commit validate/check-ledger -> runtime report。
  - 断言 dry-run 输出 `plan_hash`；commit 成功批量追加；mismatch 返回 blocked 且不修改 events ledger；`task check-ledger` 与 `runtime report` 通过且脱敏；task ledger 不被 event import 修改；真实仓库 ledger 不变。
- 更新 `docs/36-controlled-write-regression.md`：
  - 在受控写入点列表新增 `runtime event import --commit`。
  - 更新回归测试链路说明，加入 event import dry-run / commit / freeze mismatch 场景。
- 新增 `docs/43-controlled-write-regression-event-import.md`：说明本次扩展的背景、纳入回归的写入点、测试链路、关键断言、CI 关系与安全边界。
- 更新 `README.md` 与 `README.en.md`：文档索引加入 `docs/43-controlled-write-regression-event-import.md`。
- 检查 `.github/workflows/ci.yml`：已包含 `python -m pytest tests/test_controlled_write_regression.py -q`，无需修改。
- 保持安全边界：所有写入在 `tmp_path` 临时项目根中完成；不修改真实 `tasks/tasks.jsonl` / `tasks/events.jsonl`；不访问网络、不读取 `.env`/credential、不删除文件。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests/test_controlled_write_regression.py -q`：通过。
- 已跑 `python -m pytest tests/test_runtime_event_import_dry_run.py tests/test_runtime_event_import_commit.py tests/test_runtime_event_import_freeze.py -q`：通过。
- 已跑 `python -m pytest -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。
