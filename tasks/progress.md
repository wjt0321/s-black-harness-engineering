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

## 2026-07-10 — Post-freeze 下一拍：Retry / Fallback Commit 设计与落地

- 进入 post-freeze 后的下一拍 design gate：新增 `docs/70-orchestration-run-retry-fallback-commit-design.md`。
- 目标不是放开真实 adapter execution，而是把恢复性分支的 commit 语义补齐为新的受控写入设计层：retry commit / fallback commit 继续复用现有 `orchestration run --commit` 的 A+B 事务模型。
- 设计重点：lineage-aware envelope metadata、lifecycle event metadata、`--expected-plan-hash` 必填、source request 存在性校验、重复 commit 防护、approval 重新 preflight、A/B rollback 不留下半条 lineage。
- 第一版继续复用现有 `run_planned` / `run_draft_exported` event_type，只在 metadata 中表达 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`，避免过早扩张 schema enum。
- 后续已完成实现并 push：retry / fallback commit 第一版已落地，commit 为 `ac83ccf`（`Add retry and fallback run commit flow`）。
- 已同步更新 `docs/00-index.md`、`docs/02-roadmap.md`、`README.md` 与 `README.en.md`，把 70 号设计文档接入中枢台后端主线阅读路径。

## 2026-07-10 — Run Lineage / Recovery Read Model 第一版

- 在 retry / fallback commit 已落地后，继续补 read model 可见性：新增 `docs/71-release-notes-run-lineage-read-models.md`。
- `orchestration run inspect` 已支持输出 `lineage_type`、`retry_of`、`fallback_from`、`fallback_to`。
- `orchestration run list` 已支持在每条 run 摘要中显示紧凑 lineage 标识，普通 run 不误标。
- `orchestration report generate` 已补 lineage 安全摘要。
- lineage 提取优先复用 envelope `adapter_request.context`，不引入独立 Run storage，不扩 event schema enum。
- 已同步更新 `docs/00-index.md`、`docs/02-roadmap.md`、`README.md`、`README.en.md` 与 `docs/10-cli-poc-usage.md`，把 71 号 release notes 和 read-model 用法接入主线。

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

## 2026-07-07（十续）— v0.11 Runtime Event Import Release

- 新增 `docs/44-release-notes-v0.11-runtime-event-import.md`：汇总 Runtime Event Import 能力包，版本号为 `v0.11.0-runtime-event-import`。
- Release 范围覆盖：
  - `runtime event import --dry-run` 批量预检。
  - `runtime event import --commit` 受控批量写入、post-check 与 byte-size rollback。
  - consistency freeze：dry-run 输出 `plan_hash`，commit 可选 `--expected-plan-hash`。
  - controlled write regression 扩展：将 event import commit 与 freeze mismatch 纳入统一回归保护。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/44-release-notes-v0.11-runtime-event-import.md`，并整理 Runtime Event Import 相关文档顺序。
- 本阶段不新增代码能力，仅做 release notes、验证、tag 与收口。

## 2026-07-07（十一续）— Runtime Event Import Strict Freeze Mode 设计

- 新增 `docs/45-runtime-event-import-strict-freeze-mode.md`：定义未来 strict freeze mode 边界，本阶段只写设计，不实现 CLI，不新增真实写权限。
- 设计重点：
  - 当前 v0.11 freeze 是 advisory-first：dry-run 输出 `plan_hash`，commit 可选 `--expected-plan-hash`，但不强制绑定 dry-run。
  - strict freeze mode 建议新增 `--require-dry-run`，表达“本次 commit 必须绑定某次 dry-run 审阅结果”。
  - `--require-dry-run` 只能与 `--commit` 一起使用，且必须同时提供 `--expected-plan-hash`。
  - 缺少 expected hash 属于命令使用错误，建议返回 `error` / `missing-expected-plan-hash`。
  - hash mismatch 继续沿用现有 `plan-hash-mismatch` blocked 语义。
  - 第一版 strict mode 不强制 tasks ledger fingerprint，不新增单独 events ledger fingerprint 参数，不允许创建新 event ledger。
  - 未来实现 strict mode 后，controlled write regression 必须覆盖成功、缺 hash、stale hash 与兼容路径。
- 更新 `README.md` 与 `README.en.md` 文档索引，加入 `docs/45-runtime-event-import-strict-freeze-mode.md`。
- 本阶段不新增代码能力，仅做设计与文档维护。

## 2026-07-07（十二续）— Runtime Event Import Strict Freeze Mode 实现

- 实现 `runtime event import --commit --require-dry-run` strict freeze mode。
- 修改 `agent_runtime/cli.py`：
  - `runtime event import` 新增 `--require-dry-run` 参数。
  - 校验 `--require-dry-run` 不能与 `--dry-run` 同用、只能与 `--commit` 同用。
  - 将 `require_dry_run` 传给 `import_events_commit`。
- 修改 `agent_runtime/runtime_event_import.py`：
  - `import_events_commit` 新增 `require_dry_run: bool = False`。
  - 缺少 `--expected-plan-hash` 时返回 `error`（`rule_id=missing-expected-plan-hash`）。
  - hash 一致时继续完整 preflight + append + post-check + rollback；hash 不一致直接 `blocked`。
- 新增 `tests/test_runtime_event_import_strict_freeze.py`，覆盖：
  - require-dry-run + 缺少 expected hash -> error。
  - require-dry-run + dry-run -> error。
  - require-dry-run + commit + 正确 hash -> success。
  - require-dry-run + commit + stale hash -> blocked + ledger 不变。
  - stale hash 输出脱敏。
  - 向后兼容路径保持不变。
- 更新 `tests/test_controlled_write_regression.py`：
  - 新增 `test_controlled_write_regression_event_import_strict_freeze`。
  - 在临时项目根中覆盖 `--require-dry-run` 成功与 stale hash 失败路径。
- 新增 `docs/46-release-notes-runtime-event-import-strict-freeze.md`：阶段收口说明。
- 更新 `docs/10-cli-poc-usage.md`：在 Runtime Event Import 章节新增 Strict Freeze Mode 小节与示例。
- 更新 `README.md` / `README.en.md`：文档索引加入 `docs/46-release-notes-runtime-event-import-strict-freeze.md`，当前状态补充 strict freeze mode。
- 保持安全边界：不执行 adapter、不访问网络、不发送消息、不读取 `.env`/credential；`--commit` 仍只允许向已存在的 event ledger 追加连续 block，失败按 byte size 回滚。
- 不修改 `AGENTS.md`。
- 已跑 `python -m pytest tests/test_runtime_event_import_strict_freeze.py -q`：通过。
- 已跑 `python -m pytest tests/test_controlled_write_regression.py -q`：通过。
- 已跑 `python -m pytest -q`：通过。
- 已跑 `python -m agent_runtime.cli doctor`：PASS。
- 已跑 `python tools/public_scan.py`：OK public scan。

## 2026-07-09 — Stage 15 第一版 read-model CLI 收口

- 实现并验证 Stage 15 六类页面视角的最小只读 CLI read model：
  - 总览页：`orchestration overview`
  - 任务页：`orchestration task list` / `orchestration task get`
  - 执行页：`orchestration run list` / `orchestration run inspect`
  - 审批页：`orchestration approval list` / `orchestration approval get`
  - 产物页：`orchestration artifact list` / `orchestration artifact get`
  - 报告页：`orchestration report generate`
- 新增对应 Python 模块：
  - `agent_runtime/orchestration_overview.py`
  - `agent_runtime/orchestration_tasks.py`
  - `agent_runtime/orchestration_run.py`
  - `agent_runtime/orchestration_approval.py`
  - `agent_runtime/orchestration_artifact.py`
  - `agent_runtime/orchestration_report.py`
- 在 `agent_runtime/cli.py` 中注册所有 `orchestration` 子命令，统一支持 `--json` 与项目根目录 `--root`。
- 新增对应测试文件：
  - `tests/test_orchestration_overview.py`
  - `tests/test_orchestration_tasks.py`
  - `tests/test_orchestration_run_list.py`
  - `tests/test_orchestration_approval.py`
  - `tests/test_orchestration_artifact.py`
  - `tests/test_orchestration_report.py`
- 所有命令保持只读：不写 ledger/draft/envelope、不执行 adapter、不访问网络、不引入服务/API/数据库/UI。
- 安全边界：不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- 资源边界明确：Run / Approval / Artifact 当前为 envelope-scoped read model；Report 为 runtime-report-backed 实时聚合，未引入独立持久集合。
- 新增阶段收口文档 `docs/55-release-notes-orchestration-read-models.md`。
- 更新 `docs/00-index.md`：在中枢台后端主线与发布/阶段收口列表中加入 55，并更新「当前最重要的几份文档」。
- 更新 `docs/02-roadmap.md`：Stage 15 状态从「设计文档已落地」调整为「read-model CLI 第一版已落地」，补充 Stage 13/14 状态说明，不将 Stage 16 标为开始。
- 更新 `docs/10-cli-poc-usage.md`：新增「Orchestration Read-Model CLI」章节，给出六类页面命令示例与边界说明。
- 更新 `README.md` / `README.en.md`：同步 Stage 13-15 状态、调整进度估算、在已落地能力列表中加入 read-model CLI、在推荐阅读中加入 55。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
  - GitHub Actions CI：在 Python 3.11 / 3.12 上 pytest + doctor + ledger smoke checks + public_scan 全部通过。
- 本阶段不新增受控写入 orchestration 命令（如 `orchestration run`、`orchestration approval resolve`、`orchestration task submit`），这些仍留在 53 的命令草案中，待后续进入 Stage 14 受控实现时再展开。
- 不引入 Windows 绝对路径、真实 agent id、内部称谓、敏感信息。

## 2026-07-09（续）— Orchestration 受控写入边界设计

- 新增 `docs/56-orchestration-controlled-write-boundary.md`：作为进入第一批 orchestration 写入命令前的 safety / design gate。
- 明确第一批写入命令优先级：
  - 先实现只读 handoff：`orchestration route preview`、`orchestration preflight`。
  - 再实现第一个受控写入：`orchestration approval resolve`。
  - 暂缓：`orchestration run --commit`、`orchestration task submit --commit`、retry / fallback 自动化。
- 统一 dry-run / commit 语义：
  - dry-run 只产出 plan/preview，不写 ledger/envelope。
  - commit 只在现有 controlled-write 机制内 append/export，必须 preflight reload、post-check、失败回滚。
  - commit 仍不等于真实外部执行；禁止网络/消息/真实 adapter execution。
  - 支持 expected plan hash / require-dry-run freeze guard。
- 定义 capability routing handoff：
  - routing 输出包含 selected_adapter_id、capability、operation、mode、risk_level、requires_approval、requires_dry_run、fallback_candidates、routing_reason、constraints。
  - 禁止输出完整 input payload、secret、raw adapter metadata。
  - routing 结果作为 `runtime plan` / `adapter plan` 的输入；routing 只做选择，不绕过 guardrail。
- 定义 approval resolve 安全语义：
  - 只记录 decision，不直接执行原请求。
  - granted 后必须重新发起 run/preflight，不能复用旧 preflight 直接 commit。
  - rejected 生成拒绝 event/report，不删除原 approval。
  - decision 绑定 approval_id + task_id + request_id + envelope/ledger context。
  - reason 做长度/内容限制，decision_ref 输出不回显完整值。
- 状态与产物边界：
  - 不引入 DB/service/UI/独立 Run/Approval/Artifact/Report storage。
  - 写 ledger 优先 append-only event；改 envelope 优先生成新 draft/export，不原地修改输入 envelope。
- 验收标准：每个新增写入命令必须有 JSON/human 测试、只读不写或 commit 回滚测试、脱敏检查、通过 pytest/doctor/public_scan/diff check。
- 更新 `docs/00-index.md`：在中枢台后端主线列表中加入 56。
- 更新 `docs/02-roadmap.md`：在 Stage 15 与 Stage 16 之间新增 Stage 15.5 safety gate 说明，不标记 Stage 16 开始。
- 本阶段不新增代码、不改测试、不改 README。
- 不引入 Windows 绝对路径、内部身份称谓、真实 agent id、敏感信息。

## 2026-07-09（续）— orchestration route preview 只读 handoff 命令落地

- 新增 `agent_runtime/orchestration_route.py`：实现 `RoutePreviewResult` 与 `preview_route()`。
  - 从 `adapters/adapters.sample.json` 读取 adapter registry。
  - 按 `requested_capability` 匹配 enabled adapter；无匹配时返回 `needs_input`。
  - `--adapter` 显式指定时校验支持性，不支持则返回 `blocked` 并给出 fallback candidates（仅列出支持该 capability 的 adapter）。
  - `--mode commit` 对 external / destructive / privileged 或 `requires_approval` 的 adapter 强制降级为 `dry-run`；route preview 本身仍只读。
  - `operation` 仅在 adapter `input_schema` 要求 `operation` 字段时才用 capability 推导，否则为 `null`。
  - 输出包含 `selected_adapter_id`、`capability`、`operation`、`requested_mode`、`selected_mode`、`risk_level`、`requires_approval`、`requires_dry_run`、`fallback_candidates`、`routing_reason`、`constraints`、`next_action`。
- 在 `agent_runtime/cli.py` 注册 `orchestration route preview` 子命令，支持 `--capability`、`--task-id`、`--adapter`、`--mode`、`--json`、全局 `--root`。
- 新增 `tests/test_orchestration_route_preview.py`，覆盖 JSON 结构、human smoke、指定 adapter、adapter 不支持 capability、无匹配 adapter、task 上下文、commit 被强制 dry-run、只读不写文件。
- 修复 `RoutePreviewResult.to_dict()`：始终输出 `selected_adapter_id`（含 `null`），保证 blocked/needs_input 结果也有稳定 key。
- 调整测试期望：blocked 时的 fallback candidates 应为支持该 capability 的 adapter（如 `github-cli`），而非不支持 capability 的显式 `--adapter`。
- 文档同步：
  - 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：把 `orchestration route preview` 从候选草案改为已存在只读命令，补充命令示例与边界说明。
  - 更新 `docs/56-orchestration-controlled-write-boundary.md`：标记 route preview 已落地，并说明其字段与约束语义。
  - 更新 `docs/10-cli-poc-usage.md`：在「Orchestration Read-Model CLI」章节新增 routing handoff 预览示例。
- 安全边界保持不变：
  - 不写 ledger / draft / envelope，不执行 adapter，不访问网络，不引入服务 / API / DB / UI。
  - 不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- 验证：
  - `python -m pytest tests/test_orchestration_route_preview.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 未实现事项（仍留在 53 草案 / 56 设计边界中）：
  - `orchestration preflight`（只读聚合）。
  - `orchestration approval resolve`（受控写入）。
  - `orchestration run --commit`、`orchestration task submit --commit`、retry / fallback 自动化。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

## 2026-07-09（续）— orchestration preflight 只读 handoff 命令落地

- 新增 `agent_runtime/orchestration_preflight.py`：实现 `PreflightResult` 与 `check_preflight()`。
  - 复用 `orchestration_route.preview_route()` 得到 routing decision；routing 不通过时直接返回其状态，不继续 guardrail。
  - 复用 `policy.check_action()` 做 guardrail preflight，不重复实现规则。
  - `--operation` 缺失时，若 route preview 已推导出 operation 则使用；否则返回 `needs_input`。
  - `--target` 缺失时，若所选 adapter 的 `input_schema` 要求 `target` 字段则返回 `needs_input`，不猜测 target。
  - `--mode commit` 时，若 routing 或 guardrail 任一要求 dry-run / approval，则 `effective_mode` 强制为 `dry-run`；preflight 本身仍只读。
  - 输出包含 `status`、`requested_capability`、`task_id`、`requested_mode`、`selected_mode`、`effective_mode`、`route` 安全摘要、`guardrail` 安全摘要、`requires_approval`、`requires_dry_run`、`constraints`、`findings`、`next_action`。
- 在 `agent_runtime/cli.py` 注册 `orchestration preflight` 子命令，支持 `--capability`、`--task-id`、`--adapter`、`--operation`、`--target`、`--mode`、`--json`、全局 `--root` / `--policy` / `--policy-profile` / `--agent` / `--assignee`。
- 新增 `tests/test_orchestration_preflight.py`，覆盖 JSON 结构、human smoke、route blocked 跳过 guardrail、missing operation、missing target、local commit allowed、external commit 降级、guardrail blocked、task 上下文、只读不写文件。
- 文档同步：
  - 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：把 `orchestration preflight` 从候选草案改为已存在只读命令，更新命令示例与脚本示例。
  - 更新 `docs/56-orchestration-controlled-write-boundary.md`：标记 preflight 已落地，说明输入/处理/输出语义。
  - 更新 `docs/10-cli-poc-usage.md`：新增 preflight 示例。
- 安全边界保持不变：
  - 不写 ledger / draft / envelope，不执行 adapter，不访问网络，不引入服务 / API / DB / UI。
  - 不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- 验证：
  - `python -m pytest tests/test_orchestration_preflight.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 未实现事项（仍留在 53 草案 / 56 设计边界中）：
  - `orchestration approval resolve`（受控写入）。
  - `orchestration run --commit`、`orchestration task submit --commit`、retry / fallback 自动化。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

## 2026-07-09（续）— orchestration approval resolve 受控写入命令落地

- 修复并实现 `agent_runtime/orchestration_approval_resolve.py`：
  - `ApprovalResolveResult` 与 `resolve_approval()` 通过 event-ledger append 方案记录审批决议。
  - `--dry-run` 只输出 `approval_resolved` event preview，不写 ledger。
  - `--commit` 复用 `runtime_event_append.append_event()` 的受控写入机制，追加单条 event 到 event ledger，写后做 schema / ledger / runtime audit 校验，失败按原始 byte size 回滚。
  - 校验 `--decision` 必须为 `granted` / `denied` / `expired`，`--reason` 必填且 1-500 字符。
  - 校验传入的 `task_id` / `request_id` 与 envelope 中 approval scope / request 一致，不一致返回 `blocked` 且不写。
  - event metadata 只保留 `approval_id`、`request_id`、`decision`、`reason_hash`、`reason_length`、`envelope_path`，不回显完整 reason，不保存 `decision_ref`。
  - `granted` 后的 `next_action` 明确要求重新发起新的 `orchestration preflight` / `orchestration run`，不能复用旧 preflight 直接 commit。
- 调整 `agent_runtime/cli.py` 中 `orchestration approval resolve` 的参数校验策略：
  - 移除 argparse 层的 `--decision` choices、`--reason` required、`--dry-run | --commit` 互斥组。
  - 把 decision / reason / mode 冲突与缺失的校验下沉到模块内，统一返回 JSON / human 错误，保持与现有受控写入命令一致的输出风格。
- 新增 `tests/test_orchestration_approval_resolve.py`，13 个测试覆盖：
  - dry-run 不写 events ledger、commit 成功追加 event。
  - commit 写后检查失败回滚。
  - missing approval、task mismatch、request mismatch。
  - invalid decision、missing reason、dry-run / commit 冲突。
  - human / JSON 输出、granted 后 next_action 要求新 preflight、denied 记录 decision。
  - 完整 reason / secret / `decision_ref` 不回显到 CLI 输出。
- 文档同步：
  - 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：把 `orchestration approval resolve` 从候选草案改为已存在受控写入命令，补充 dry-run / commit 示例与边界说明。
  - 更新 `docs/56-orchestration-controlled-write-boundary.md`：标记 `approval resolve` 已按 event-ledger append 方案落地，更新产物形态与下一步。
  - 更新 `docs/10-cli-poc-usage.md`：新增 `orchestration approval resolve` 示例，并更新当前安全边界说明。
- 安全边界保持不变：
  - 不写原 envelope，不执行 adapter，不访问网络，不引入服务 / API / DB / UI。
  - 不回显完整 `input` payload、`raw_ref`、`decision_ref`、`payload_refs`、evidence descriptions 或 secret match。
- 验证：
  - `python -m pytest tests/test_orchestration_approval_resolve.py -q`：13 passed。
  - `python -m pytest tests -q`：全部通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 未实现事项（仍留在 53 草案 / 56 设计边界中）：
  - `orchestration run --commit`、`orchestration task submit --commit`、retry / fallback 自动化。
  - envelope-draft-export 方案的 `approval resolve` 产物形态。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

## 2026-07-09（续）— Stage 15.5 收口：controlled handoff + approval resolve release notes

- 新增 `docs/57-release-notes-orchestration-controlled-handoff.md`，记录从 56 design gate 到第一批 handoff / controlled-write 命令落地的阶段成果。
- 更新 `docs/00-index.md`：
  - 中枢台后端主线列表加入 `57-release-notes-orchestration-controlled-handoff.md`。
  - 发布与阶段收口列表加入 57。
- 更新 `docs/02-roadmap.md`：
  - Stage 15.5 状态从「design gate / 设计先行」调整为「第一批 controlled handoff / approval resolve 已落地」。
  - 交付物加入 `docs/57-release-notes-orchestration-controlled-handoff.md`、`orchestration route preview`、`orchestration preflight`、`orchestration approval resolve`。
  - 不标记 Stage 16 开始；run --commit / retry / fallback 仍暂缓。
- 更新 `README.md` / `README.en.md`：
  - 阶段进度列表加入 Stage 15.5 并已落地状态。
  - 已落地能力列表加入 `orchestration route preview`、`orchestration preflight`、受控写入 `orchestration approval resolve`。
  - 推荐阅读列表加入 56 / 57。
- 本次为纯文档改动，不改代码/测试/schema。
- 验证：
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不弱化 guardrail，不夸大 run --commit 已实现。

## 2026-07-09（续）— Stage 15.6：orchestration run 受控执行设计 gate

- 新增 `docs/58-orchestration-run-controlled-execution-design.md`，作为进入 `orchestration run --dry-run/--commit` 实现前的设计 gate。
- 文档覆盖：
  - 命令候选形态：`--task-id`、`--request-id`、`--capability`、`--adapter`、`--operation`、`--target`、`--mode`、`--expected-plan-hash`、`--require-dry-run`。
  - dry-run 产物形态：只读 run plan preview，含 routing/preflight/candidate envelope/events/artifact/evidence refs 安全摘要和稳定 `plan_hash`。
  - commit 产物形态：不执行真实 adapter；优先 envelope draft export（A）+ run lifecycle events append（B），all-or-nothing 回滚；第一版可降级为只做 A。
  - freeze guard：`plan_hash` 覆盖稳定安全字段；commit `--expected-plan-hash` mismatch 返回 `blocked`；`--require-dry-run` 要求绑定审阅上下文。
  - approval handoff：preflight needs_approval 时 commit 不写产物；已有 `approval_resolved` event 仍需重新 preflight；granted 不是执行授权。
  - state model mapping：Run 暂不独立持久；Artifact/Evidence 仍 envelope-scoped；Report 仍 runtime-report-backed。
  - rollback / post-check：draft export 失败删除新文件，event append 失败按 byte size 回滚，post-check 包括 schema / ledger consistency / runtime audit / public scan。
  - 验收标准与下一步建议。
- 更新 `docs/00-index.md`：中枢台后端主线与发布/阶段收口列表加入 58。
- 更新 `docs/02-roadmap.md`：新增 Stage 15.6 设计 gate，不标记 Stage 16 开始。
- 本次为纯文档改动，不改代码/测试/schema。
- 验证：
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不弱化 guardrail，不夸大 run --commit 已实现。

## 2026-07-09（续）— Stage 15.7：orchestration run --dry-run 落地

- 新增 `agent_runtime/orchestration_run_dry_run.py`：
  - 实现 `RunDryRunResult` 与 `dry_run_run()`。
  - 复用 `orchestration_preflight.check_preflight()` 做 routing + guardrail 聚合。
  - 复用 `runtime_plan.plan_runtime_action()` 生成候选 envelope。
  - 输出 route/preflight/candidate_envelope_summary/candidate_events_summary/artifact_candidate_refs/evidence_candidate_refs/plan_hash/constraints/findings/next_action。
  - `plan_hash` 覆盖安全字段（task_id、request_id、capability、selected_adapter_id、operation、target safe summary、mode、route、preflight、candidate envelope/event 序列），不包含 timestamp/event_id/input payload/target 原文。
  - 对 `--commit` 模式返回 `needs_input`；缺失 task/operation/target 时返回稳定状态。
- 在 `agent_runtime/cli.py` 注册 `orchestration run --dry-run`：
  - 父 parser 增加 `--task-id`、`--request-id`、`--capability`、`--adapter`、`--operation`、`--target`、`--tasks-file`、`--dry-run`/`--commit`。
  - `orchestration run` 子命令改为 `required=False`，无子命令时默认执行 dry-run handler。
  - 新增 `_cmd_orchestration_run_dry_run` 与 `_emit_run_dry_run_result` 人类可读渲染。
  - `--commit` 仍未实现，传入时返回 `needs_input`。
- 新增 `tests/test_orchestration_run_dry_run.py`：
  - 覆盖模块层 dry-run pass/needs_approval/missing operation/missing target/adapter not supported/task not found/plan hash stability/只读不写/输出脱敏。
  - 覆盖 CLI JSON/人类可读输出。
  - 修正人类可读 smoke 测试，使其使用 `read_file` capability 以匹配期望 `pass` 状态。
- 文档同步：
  - 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：把 `orchestration run --dry-run` 标为已存在，`orchestration run --commit` 仍草案。
  - 更新 `docs/58-orchestration-run-controlled-execution-design.md`：标记 dry-run 已落地，commit 待实现。
  - 更新 `docs/10-cli-poc-usage.md`：新增 `orchestration run --dry-run` 示例与边界说明。
- 验证：
  - `python -m pytest tests/test_orchestration_run_dry_run.py -q`：11 passed。
  - `python -m pytest tests -q`：全绿。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不弱化 guardrail，`--commit` 仍明确未实现，不触发真实 adapter execution。

## 2026-07-09（续）— Stage 15.8：orchestration run --commit 第一版 A-only 落地

- 新增 `agent_runtime/orchestration_run_commit.py`：
  - 实现 `RunCommitResult` 与 `commit_run()`。
  - 复用 `orchestration_run_dry_run.dry_run_run()` 重新生成 run plan 并取 `envelope_draft`。
  - 复用 `runtime_draft_export` 的 controlled-write helper：`_validate_output_path`、`_validate_drafts_runtime_path`、`_scan_export_content`、`_write_envelope_file`、`_post_write_check`、`_rollback_file`。
  - 硬边界：
    - `--commit` 必须提供 `--output` 与 `--expected-plan-hash`，缺失返回 `needs_input`，不写。
    - `--commit` 会重新 dry-run/preflight；非 `pass` 状态（含 `needs_approval`）均不写。
    - `--expected-plan-hash` mismatch 返回 `blocked`，不写。
    - 输出路径必须位于 `drafts/runtime/` 下、`.json`、不覆盖已存在文件。
    - 写入后做 schema validate + inspect post-check，失败删除新文件回滚。
    - 不执行真实 adapter、不访问网络、不发送消息、不追加 event ledger（A-only）。
- 更新 `agent_runtime/orchestration_run_dry_run.py`：
  - `RunDryRunResult` 增加非序列化字段 `envelope_draft`，供 commit 阶段直接复用。
- 更新 `agent_runtime/cli.py`：
  - `orchestration run` parser 增加 `--output`、`--expected-plan-hash`、`--require-dry-run`。
  - handler 改名为 `_cmd_orchestration_run`，在 `--commit` 时调用 `commit_run`。
  - 新增 `_emit_run_commit_result` 人类可读渲染。
  - `--commit` 不再是未实现，但 `--require-dry-run` 只要求必须提供 expected hash。
- 新增 `tests/test_orchestration_run_commit.py`：
  - 覆盖 missing args、hash mismatch blocked no write、matching hash writes envelope draft、output exists blocked no overwrite、preflight needs_approval no write、terminal task no write、write failure no partial file、输出不含 sensitive refs、CLI JSON/human smoke、A-only 不追加 events。
- 修正 `tests/test_orchestration_run_dry_run.py`：
  - `test_cli_commit_returns_needs_input` 断言改为提示 `--output`/`--expected-plan-hash`。
- 文档同步：
  - 更新 `docs/53-minimal-orchestration-loop-cli-draft.md`：把 `orchestration run --commit` 标为已存在第一版 A-only controlled write。
  - 更新 `docs/58-orchestration-run-controlled-execution-design.md`：标记 commit A-only 已落地，B lifecycle events 仍后续。
  - 更新 `docs/10-cli-poc-usage.md`：新增 `orchestration run --commit` 示例与边界说明，更新安全边界与限制。
- 验证：
  - `python -m pytest tests/test_orchestration_run_commit.py -q`：11 passed。
  - `python -m pytest tests -q`：全绿。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不弱化 guardrail，`--commit` 仍明确不执行真实 adapter。

## 2026-07-09（续）— Stage 15.8 收口：docs/59-release-notes-orchestration-run-controlled-execution.md

- 新增 `docs/59-release-notes-orchestration-run-controlled-execution.md`，记录 `orchestration run --dry-run` 与 `orchestration run --commit` 第一版 A-only controlled write 落地。
- 文档覆盖：
  - 阶段定位：Stage 15.6 design gate 后的 run 侧第一版实现收口。
  - 已实现命令：`orchestration run --dry-run`（只读 plan preview + plan_hash）、`orchestration run --commit`（A-only envelope draft export）。
  - run dry-run 输出口径：route/preflight/candidate envelope/events/artifact/evidence 安全摘要、plan_hash；不写 ledger/envelope。
  - run commit 语义：必须 matching `--expected-plan-hash`；hash mismatch blocked；preflight 非 pass 不写；复用 `runtime draft export --commit` 受控写入机制；不执行 adapter、不追加 events、不写独立 Run storage。
  - post-check/rollback：schema/inspect 检查，失败删除刚生成的 draft 文件；不覆盖已有 output path。
  - 安全边界：不访问网络、不发送消息、不执行真实 adapter、不回显 input payload/target 原文/raw_ref/decision_ref/payload_refs/evidence descriptions。
  - 验证：run dry-run tests、run commit tests、全量 pytest、doctor、public_scan、diff check、GitHub CI success。
  - 未实现事项：B 侧 run lifecycle events、retry/fallback、task submit commit、真实 adapter execution、DB/service/UI。
  - 下一步建议：优先补 B 侧 run lifecycle events 的 event schema + controlled append，或先写 60 设计 gate。
- 更新 `docs/00-index.md`：中枢台后端主线与发布/阶段收口列表加入 59。
- 更新 `docs/02-roadmap.md`：
  - Stage 14 说明更新为「设计文档、命令草案与 run 侧 A-only commit 已落地」。
  - 新增 Stage 15.7（Orchestration Run Dry-run 落地）与 Stage 15.8（Orchestration Run Commit A-only 落地）。
  - Stage 15.5 说明去掉「run --commit 仍暂缓」。
  - 不标记 Stage 16 开始。
- 更新 `README.md` / `README.en.md`：
  - 阶段进度列表加入 ✅ Stage 15.7 / ✅ Stage 15.8。
  - 已落地能力列表加入 `orchestration run --dry-run` 与 `orchestration run --commit` A-only，明确不执行真实 adapter、不追加 events。
- 本次为纯文档改动，不改代码/测试/schema。
- 验证：
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不说真实 adapter execution 已实现；不弱化 guardrail。

## 2026-07-09（续）— Stage 15.9：Run Lifecycle Events design gate

- 新增 `docs/60-orchestration-run-lifecycle-events-design.md`，作为进入 B 侧 run lifecycle events 实现前的 design gate。
- 文档覆盖：
  - 阶段定位：59 已完成 A-only commit，60 定义 B 侧 event trail 设计。
  - 候选 event types：`run_planned`、`run_draft_exported`、`run_blocked` 进入 schema enum；`run_commit_failed` 暂不落地。
  - event payload 安全字段：基础字段 + metadata 安全子集；禁止 input/target 原文、raw_ref、decision_ref、payload_refs、evidence descriptions、reason 原文、secret match。
  - B 侧 controlled append：复用 `runtime event append/import --commit`，batch all-or-nothing，失败 byte size truncate 回滚。
  - A+B 组合策略：A 成功 B 失败时回滚 A（删除 draft）和 B（truncate）；要求显式 `--events-file`。
  - freeze guard 与 idempotency：plan_hash 语义不变；event_id 避免冲突；重复 commit blocked。
  - approval/blocked 分支：preflight needs_approval、hash mismatch、terminal task 均不写 A/B；第一版不写 `run_blocked`。
  - read-model 影响：`orchestration run list` 可后续考虑纳入 lifecycle events；`task events` 自然显示；report 仍 runtime-report-backed。
  - 验收标准与下一步建议。
- 更新 `docs/00-index.md`：中枢台后端主线与发布/阶段收口列表加入 60。
- 更新 `docs/02-roadmap.md`：新增 Stage 15.9（Run Lifecycle Events design gate），不标记 Stage 16 开始。
- 更新 `docs/58-orchestration-run-controlled-execution-design.md`：下一步建议指向 60。
- 本次为纯文档改动，不改代码/测试/schema。
- 验证：
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。
- 不说 B 侧 events 已实现；不说真实 adapter execution 已开放；不弱化 guardrail。

## 2026-07-09（续）— Stage 15.9 实现：Run Lifecycle Events A+B

- 升级 `orchestration run --commit` 从 A-only 到 A+B：
  - A：envelope draft/export 文件（复用 `runtime draft export --commit` 机制）。
  - B：追加 `run_planned` + `run_draft_exported` 生命周期事件到 event ledger（复用 `runtime event append` 受控写入机制）。
  - all-or-nothing：A 成功 B 失败时删除 draft 文件并按原始 byte size truncate 回滚 event ledger。
- 更新 `tasks/event.schema.json`：`event_type` enum 新增 `run_planned`、`run_draft_exported`、`run_blocked`。
- 更新 `agent_runtime/orchestration_run_commit.py`：
  - `commit_run()` 新增 `events_file` 参数，缺失返回 `needs_input`。
  - 成功路径生成两个 lifecycle event 并 batch append。
  - `RunCommitResult` 新增 `event_refs`，`write_summary` 增加 events_file / appended_event_count / event post-check 字段。
- 更新 `agent_runtime/cli.py`：`orchestration run` parser 增加 `--events-file`；commit handler 传递并展示 events_file 和 event_refs。
- 更新测试：
  - `tests/test_orchestration_run_commit.py`：所有 commit 测试传入 `events_file`；新增事件顺序、metadata 脱敏、B 失败回滚、CLI `--events-file`、不修改已有合法事件等测试；删除旧 A-only「不追加事件」测试。
  - `tests/test_task_validation.py`：新增 schema enum 接受 `run_planned` / `run_draft_exported` / `run_blocked` / `approval_resolved` 的参数化测试。
- 文档同步：
  - `docs/53-minimal-orchestration-loop-cli-draft.md`：`orchestration run --commit` 从 A-only 改为 A+B。
  - `docs/58-orchestration-run-controlled-execution-design.md`：标记 B lifecycle events 已落地。
  - `docs/60-orchestration-run-lifecycle-events-design.md`：标记 schema 与 A+B 实现已落地。
  - `docs/10-cli-poc-usage.md`：更新 run commit 示例与边界说明，加入 `--events-file`。
- 硬约束保持：不执行真实 adapter、不访问网络、不发送消息、不写独立 Run storage、不引入 DB/service/UI。
- 安全边界：event metadata 只存安全摘要；不回显 input/target 原文、raw_ref、decision_ref、payload_refs、evidence descriptions、reason 原文、secret match；使用相对路径。
- 验证：
  - `python -m pytest tests/test_orchestration_run_commit.py tests/test_task_validation.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：仅 LF/CRLF 换行警告，无空白错误。
- 不引入 Windows 绝对路径、内部身份称谓、真实个人 / agent id、敏感信息。

## 2026-07-09（续）— Stage 15.9 收口：post-check 语义修正 + release notes

- 审查并修正 `agent_runtime/orchestration_run_commit.py` 的 B 侧 post-check：不再对最后一条 event 走“临时模拟追加”检查，而是直接验证**实际落盘后的** events ledger，覆盖 event schema validation、task/event ledger consistency 与 runtime ledger audit。
- 新增回归测试：`tests/test_orchestration_run_commit.py` 断言 post-check 使用正式 `events_file`，避免后续退回临时文件语义。
- 新增阶段收口文档：`docs/61-release-notes-orchestration-run-lifecycle-events.md`。
- 同步更新入口文档与路线图：`README.md`、`README.en.md`、`docs/00-index.md`、`docs/02-roadmap.md`，把 Stage 14/15.8/15.9 的 run commit 状态统一到当前 A+B 实现。
- smoke 验证：临时隔离 root 下跑 `orchestration run --dry-run` -> `orchestration run --commit --events-file ...`，确认成功写出 envelope draft，并追加 `run_planned` + `run_draft_exported` 两条 events。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。
- 当前阶段结论：Stage 15.9 已从 design gate 进入实现收口；`orchestration run --commit` 现为 A+B controlled write，但仍不执行真实 adapter、不访问网络、不引入独立 Run storage。

## 2026-07-09（续）— 下一步 design gate：Task Submit 受控写入

- 新增 `docs/62-orchestration-task-submit-controlled-write-design.md`，把 `orchestration task submit --dry-run / --commit` 固定为下一批更低风险的 orchestration 写入入口。
- 设计结论：先做 `task submit`，暂不直接进入 retry / fallback。原因是 task submit 属于 control plane 入口能力，且可薄包装现有 `runtime task create --dry-run / --commit`，风险明显低于恢复性自动化能力。
- 第一版边界：
  - 推荐只支持 `--file` / `--stdin` 的 candidate task JSON 输入。
  - `--dry-run` 只做 schema / duplicate id / secret-public scan / ledger consistency，不写任何 ledger。
  - `--commit` 只写 task ledger，不自动写 `created` event，不自动触发 route / preflight / run。
  - 输出面向 orchestration 语义，`next_action` 对齐 route preview / preflight / run 主线。
- 继续保持：不执行真实 adapter、不访问网络、不发送消息、不引入独立 Task queue / DB / service / UI。

## 2026-07-09（续）— Stage 16 前低风险实现：Orchestration Task Submit 第一版

- 新增 `agent_runtime/orchestration_task_submit.py`，把 `orchestration task submit --dry-run / --commit` 落成 control-plane-facing 薄包装，底层复用 `runtime task create` 的 schema 校验、scan、ledger consistency 与 rollback。
- 更新 `agent_runtime/cli.py`：新增 `orchestration task submit` 子命令，支持 `--file|--stdin`、`--dry-run|--commit`、`--tasks-file`、`--events-file`。
- 第一版边界保持保守：
  - `--dry-run` 不写任何 ledger；
  - `--commit` 只写 task ledger；
  - 不自动写 `created` event；
  - 不自动触发 route / preflight / run；
  - `next_action` 统一引导到 `orchestration route preview` / `orchestration preflight`。
- 新增测试 `tests/test_orchestration_task_submit.py`：覆盖 dry-run、commit、缺失 mode、CLI JSON 输出，以及 submit -> task list/get smoke。
- 更新 `docs/10-cli-poc-usage.md`：补充 orchestration task submit 示例与边界说明。
- 额外发现并确认一个产品化口径问题：仓库版本冻结 tag 目前仍停在 `v0.11.0-runtime-event-import`，后续 orchestration 阶段虽然持续新增 release notes（55/57/59/61/62），但没有继续打新 tag，也没有正式声明版本策略已切换到“阶段编号优先、semver/tag 暂停”。这意味着当前版本治理处于半迁移状态，需要单独补一份说明文档或路线图说明，避免后续新对话误判为“版本号忘做”还是“故意不打”。
- 已新增 `docs/64-versioning-governance.md`，正式把版本治理定为“阶段推进 + release notes 收口 + 里程碑打 tag”。当时决策为：不追补 55/57/59/61 的逐阶段 semver tag，不为 62 design gate 打 tag；待 orchestration task submit 完成实现收口后，再统一判断是否冻结新的 orchestration milestone tag（优先候选名：`v0.12.0-orchestration-foundation`）。后续已实际冻结为 commit `38b4b69` / tag `v0.12.0-orchestration-foundation`。
- 已新增 `docs/63-orchestration-task-submit-created-event-design.md`，把 `orchestration task submit --commit` 的下一拍 design gate 固定为 A+B：A 写 task ledger，B 写 `created` event，整体 all-or-nothing rollback，并以补齐 `TaskCollection.create` 语义与 task/event read model 一致性为目标。明确优先级仍是先补入口级 A+B，再进入 retry / fallback design gate 与实现。
- 已完成 `orchestration task submit --commit` A+B 实现收口：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_task_submit.py` 升级为事务协调层，成功时写 task ledger + `created` event，`--events-file` 在 commit 下必填，B 失败或 post-check 失败时回滚 task/events ledger 到原始 byte size；`agent_runtime/cli.py` 增加专用 summary 渲染；`tests/test_orchestration_task_submit.py` 增加 dry-run 预告、commit 双写、缺 events-file 不写、B 失败回滚、post-check 失败回滚与 CLI smoke 覆盖。
- 新增 `docs/65-release-notes-orchestration-task-submit-created-event.md`，记录 Stage 15.95 实现收口、验证结果与下一步建议。已复核：`python -m pytest tests/test_orchestration_task_submit.py -q`、`python -m pytest tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 已清理 Kimi Code 额外生成的 `docs/superpowers/` 与 D 盘根目录旧产物 `DRIVE:/news-aggregator-plan`，均送回收站；未动 `DRIVE:/Kimi` 与 `DRIVE:/kimi-workspace` 工作目录。
- 新增 `docs/66-orchestration-run-retry-fallback-design.md`，作为 retry / fallback 的 design gate：第一版建议只做 dry-run preview，要求新 request_id、显式 lineage、重新 route/preflight/dry-run，不自动复用旧 approval，不执行真实 adapter，不扩展 event schema enum；后续实现顺序建议为 retry dry-run、fallback dry-run、release notes，再讨论 commit 设计。
- 已完成 `orchestration run` retry / fallback dry-run preview 第一版：Kimi Code 负责主要编码，小黑负责审查与文档维护。核心变更为 `agent_runtime/orchestration_run_dry_run.py` 新增 lineage 字段、校验与 plan_hash 输入；`agent_runtime/cli.py` 新增 `--retry-of`、`--fallback-from`、`--fallback-to` 并在 human/json 输出展示安全 lineage；`tests/test_orchestration_run_dry_run.py` 增加 retry/fallback pass、参数互斥、request_id 冲突、不写 ledger/envelope、hash 差异、CLI smoke 与 direct-call fallback adapter 覆盖。
- 新增 `docs/67-release-notes-orchestration-run-retry-fallback.md`，记录 Stage 15.96 dry-run preview 实现收口。已复核：`python -m pytest tests/test_orchestration_run_dry_run.py tests/test_orchestration_task_submit.py tests/test_controlled_write_regression.py -q`、`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`git diff --check` 均通过；`git diff --check` 仅提示两个既有 Python 文件后续会按 Git 设置从 LF 转 CRLF。
- 新增 `docs/68-orchestration-foundation-milestone-freeze-checklist.md` 与 `docs/69-orchestration-foundation-freeze-execution-plan.md`，把 `v0.12.0-orchestration-foundation` 的候选冻结条件、验证证据、建议 commit/tag 文案与执行顺序整理为冻结前文档链路。后续已实际完成冻结：commit `38b4b69`、tag `v0.12.0-orchestration-foundation`、push 完成。

## 2026-07-11 — Stage 10 第一版：Adapter Capability Registry 内置落地

- 按 `docs/000-stage-digest.md` 优先方向进入 Stage 10 — Adapter Runtime Interface。
- 新增 `agent_runtime/adapter_registry.py`：
  - 结构化 adapter metadata 模型 `AdapterMetadata` + `TimeoutProfile`（frozen dataclass）。
  - 严格校验函数 `validate_adapter_metadata`，覆盖 `adapter_id` 格式、`adapter_type` 枚举、`risk_level` 枚举、`capabilities` 非空唯一、`timeout_profile` 边界、`input_schema_ref` / `output_schema_ref` 必填。
  - 确定性内置 registry `AdapterRegistry`，覆盖 5 个代表 adapter：`kimi-code-acp`、`qwenpaw-agent-api`、`shell-local`、`github-cli`、`lark-cli`。
  - 稳定排序、类型/风险/capability 过滤、`capability_index` 能力倒排索引。
- 新增 `agent_runtime/orchestration_adapter.py`：
  - 只读 read model `list_adapters` / `get_adapter`。
  - 未知 adapter_id 返回 `needs_input`，与现有 `orchestration task get` 等 CLI 错误语义一致。
  - 输出 compact、安全、不回显凭据或运行时状态。
- 更新 `agent_runtime/cli.py`：
  - 新增 `orchestration adapter list` 子命令，支持 `--type`、`--risk`、`--capability` 过滤与 `--json`。
  - 新增 `orchestration adapter inspect <adapter_id>` 子命令，支持 `--json`。
- 新增测试：
  - `tests/test_adapter_registry.py`：覆盖模型校验、内置 registry 加载、稳定排序、过滤、key 不匹配校验、非法 entry 校验、确定性 to_dict。
  - `tests/test_orchestration_adapter.py`：覆盖 JSON 结构、人类可读输出、稳定排序、type/risk/capability 过滤、inspect、未知 ID、不写文件。
- 更新文档：
  - `docs/48-adapter-runtime-interface.md`：新增"内置 Registry 实现"小节，说明模块、CLI、内置 5 个 adapter、与旧 registry 关系。
  - `docs/10-cli-poc-usage.md`：在 Orchestration Read-Model CLI 章节新增 `orchestration adapter list/inspect` 示例与边界说明。
  - `docs/000-stage-digest.md`：标记 Stage 10 第一版已落地，更新"现在已经能做什么"。
  - `docs/02-roadmap.md`：更新 Stage 10 状态为"第一版已落地，持续巩固"。
- 设计选择说明：
  - 保留 Stage 4 遗留的 `adapters/adapters.sample.json` 与 `adapters/adapter.schema.json`，不破坏现有 `adapters list` CLI。
  - 新 registry 是 Stage 10 的 backend-first read model，与旧 registry 并行；未来可评估合并。
  - `risk_level` 沿用仓库现有枚举 `local/external/destructive/privileged`，而非 Stage 10 示例中的 `medium`，以保持一致性。
  - `input_schema_ref` / `output_schema_ref` 使用指向 `adapters/schemas/` 的稳定引用字符串，当前阶段不强制对应文件存在。
- 验证：
  - `python -m pytest tests/test_adapter_registry.py tests/test_orchestration_adapter.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误。

## 2026-07-11（续）— Stage 10 返工：单一事实源 + 规范化投影

- 代码审查指出第一阶段实现存在双重事实源：硬编码 5 个 adapter 与现有 `adapters/adapters.sample.json` 并行，会导致 routing 与 registry 查询漂移；`input/output_schema_ref` 指向不存在的文件，制造虚假契约。
- 重构 `agent_runtime/adapter_registry.py`：
  - 删除硬编码内置 registry，改为从 `adapters/adapters.sample.json` 加载（复用 `loader.load_adapters`）。
  - 新增确定性投影层 `project_adapter(entry)`，把 legacy 字段映射为 Stage 10 元数据。
  - `adapter_type` 由 `kind` 映射：`qwenpaw_agent_api`/`acp_runner` → `agent`；`lark` → `service`；其余 → `tool`。
  - `supports_*` 与 `timeout_profile` 按规则 derived/defaulted，并在 `derived` 字段中记录来源。
  - `input_schema_ref` / `output_schema_ref` 改为指向真实存在的 `adapters/adapter.schema.json#/$defs/adapter/properties/input_schema|output_schema`。
  - `load_adapter_registry(root)` 统一处理：缺文件、非法 JSON、schema 不匹配、`adapters` 字段非列表、单条投影失败，均返回安全 findings 与 next_action，不 traceback。
- 更新 `agent_runtime/orchestration_adapter.py`：
  - `list_adapters` / `get_adapter` 改为从 root 加载投影 registry。
  - 加载失败返回 `error`，未知 ID 返回 `needs_input`，与现有 CLI 错误语义一致。
- 更新 `agent_runtime/cli.py`：
  - `orchestration adapter inspect` 人类输出新增 `derived:` 段落，清楚展示每个非源字段的推导说明。
- 重写测试：
  - `tests/test_adapter_registry.py`：覆盖从真实 root 加载、tmp root source mutation 反射、source IDs/capabilities/risk 与投影对齐、缺文件、非法 JSON、schema 失败、malformed adapters 字段、投影规则验证。
  - `tests/test_orchestration_adapter.py`：覆盖 JSON/人类输出、过滤、稳定排序、未知 ID、source mutation 反射、缺文件/非法 JSON、不写文件。
- 更新文档：
  - `docs/48-adapter-runtime-interface.md`：重写“内置 Registry 实现”小节，明确单一事实源、投影规则表、derived 字段、与 `adapters list` 的关系；删除“双 registry 并行/未来合并”表述。
  - `docs/000-stage-digest.md` / `docs/02-roadmap.md`：更新 Stage 10 描述，强调单一事实源与真实 schema ref。
- 设计选择说明：
  - 保留 `adapters/adapters.sample.json` 作为唯一事实源，不引入第二份 adapter 清单。
  - schema ref 不假装每个 adapter 有独立 schema 文件，而是引用真实存在的 `adapters/adapter.schema.json` 中 input_schema/output_schema 定义。
  - `derived` 字段让调用方清楚知道哪些值是原始字段、哪些是投影层推导/默认值。
- 验证：
  - `python -m pytest tests/test_adapter_registry.py tests/test_orchestration_adapter.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误（仅 Git LF/CRLF 转换提示）。

## 2026-07-11（续）— Stage 10 第二轮审查收口

- 审查反馈：CLI help / docs 仍残留旧实现的"built-in / 内置 / 5 个"表述；`input/output_schema_ref` 指向 `adapters/adapter.schema.json` 的元定义，不是具体 adapter 的真实 schema；需确认 disabled entry 不过滤。
- 修正 CLI help：`orchestration adapter list/inspect` 的 help 从 "built-in capability registry" 改为 "source-backed capability registry"。
- 修正 `agent_runtime/adapter_registry.py`：
  - `input_schema_ref` / `output_schema_ref` 改为真实 JSON Pointer：`adapters/adapters.sample.json#/adapters/<index>/input_schema` / `output_schema`。
  - projection 时传入 `source_index`，`AdapterMetadata` 增加 `source_index` 与 `enabled` 字段。
  - `derived` 文案改为 "pointer to adapters/adapters.sample.json entry N input_schema/output_schema"。
  - 投影层不再过滤 disabled entries，与 `loader.load_adapters` 同批条目语义一致；routing 等消费方自行过滤。
- 修正 `agent_runtime/orchestration_adapter.py`：list summary 增加 `enabled` 字段。
- 修正 `agent_runtime/cli.py`：list 人类输出增加 `enabled=` 列；inspect 人类输出继续显示 derived 段落。
- 更新文档：
  - `docs/48-adapter-runtime-interface.md`：标题改为 "Source-Backed Registry 投影"；删除"内置"和"5 个"表述；更新投影规则表说明 JSON Pointer 与 enabled 字段不过滤。
  - `docs/10-cli-poc-usage.md`：改为 "source-backed registry 投影"；删除"当前内置 5 个"；说明 JSON Pointer。
  - `docs/000-stage-digest.md`、`docs/02-roadmap.md`：同步更新表述。
- 更新测试：
  - `tests/test_adapter_registry.py`：新增 `test_schema_refs_point_to_source_entry_schemas` 解析 pointer 并比对 source entry 的 input/output schema；新增 `test_disabled_entries_are_not_filtered`；更新 `test_load_from_project_root_matches_sample` 与 loader 比对 IDs；修复因 schema ref 变化而失效的断言。
  - `tests/test_orchestration_adapter.py`：新增 `test_adapter_list_matches_loader_entries`、`test_adapter_inspect_schema_refs_resolve_to_source_schemas`、`test_adapter_list_includes_disabled_entries`；修复 schema ref 断言。
- 验证：
  - `python -m pytest tests/test_adapter_registry.py tests/test_orchestration_adapter.py -q`：通过。
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK public scan。
  - `git diff --check`：无空白错误（仅 Git LF/CRLF 设置提示）。

## 2026-07-11 — Stage 10 文档收口：route preview / preflight 接入 source-backed projection

- 代码侧已对齐：`agent_runtime/orchestration_route.py` 改为消费 `load_adapter_registry` 投影；`agent_runtime/orchestration_preflight.py` 在 `_needs_target` 等逻辑中使用 registry 投影元数据。
- 最小文档更新：
  - `docs/000-stage-digest.md`：Stage 10 新进落地与“现在已经能做什么”中说明 route preview / preflight 已消费同一 source-backed projection；下一步目标改为巩固 Stage 10 并为 Stage 11 做准备。
  - `docs/02-roadmap.md`：Stage 10 已落地能力新增“投影已被路由消费”；移除“与 route preview / preflight 打通”的仍后续项；Stage 11 目标补充“在 Stage 10 projection 基础上继续把 routing 抽象做扎实”。
  - `docs/48-adapter-runtime-interface.md`：在 Source-Backed Registry 投影小节说明 route preview / preflight 直接消费投影。
  - `docs/10-cli-poc-usage.md`：在 `orchestration route preview` 与 `orchestration preflight` 示例后补充说明其基于 source-backed registry 投影。
- 未新增文档、未修改 schema、未声称 Stage 11/14 完成。
- 验证：
  - `python tools/public_scan.py`：OK public scan。

## 2026-07-11 — Stage 11：Capability Routing Model 约束路由第一版文档更新

- 任务：Task 5 / 6，更新最小文档以反映路由约束第一版。
- 修改文件：
  - `docs/49-capability-routing-model.md`：在“三层路由模型”后新增“已实现的第一版约束路由（Stage 11）”小节，说明 capability match → constraint filter → preference rank 流程、已支持约束、未实现维度与示例输出形状。
  - `docs/02-roadmap.md`：Stage 11 增加“已落地能力”与“仍后续”，记录 constraint filter + preference rank 第一版与 CLI flags，保留 cost/latency/availability 打分后续。
  - `docs/000-stage-digest.md`：将“新进落地”更新为 Stage 11 约束路由第一版。
  - `docs/10-cli-poc-usage.md`：在 `orchestration route preview` / `orchestration preflight` 示例后补充带 `--preferred-adapter`、`--max-risk`、`--require-background` 的新示例。
  - `tasks/progress.md`：追加本条目。
- 明确未实现：cost / latency / availability / 在线状态 / 真实并发调度。
- 未新增文档、未修改 schema、未声称 Stage 11 全部完成。
- 验证：
  - `python tools/public_scan.py`：OK public scan。

## 2026-07-11 — Stage 11：路由决策解释 / decision trace 第一版

- 目标：在不破坏现有 route preview / preflight 默认输出的前提下，新增 `--explain` 结构化决策 trace，为 Stage 12 状态模型做准备。
- 设计要点：
  - 采用方案 A：`--explain` 显式开启；默认输出严格不变。
  - `decision_trace` 由 `preview_route` 内部真实中间结果构造，CLI 不复算；preflight 通过 `_route_summary` 复用同一份 trace。
  - trace 仅暴露 `adapter_id`、`source_index`、`risk_level`、`reason`，不泄露完整 schema 或敏感载荷。
- 修改文件：
  - `agent_runtime/orchestration_route.py`：新增 `CandidateRef`、`RejectedCandidate`、`SelectedCandidate`、`RouteDecisionTrace` dataclasses；`RoutePreviewResult` 新增 `decision_trace`；`preview_route` 增加 `explain` 参数并在所有分支填充 trace。
  - `agent_runtime/orchestration_preflight.py`：`check_preflight` 增加 `explain` 参数并透传；`_route_summary` 在存在 trace 时包含 `decision_trace`。
  - `agent_runtime/cli.py`：route preview / preflight parser 与命令函数增加 `--explain`；新增 `_render_decision_trace` 人类可读渲染；emit 函数在 `--explain` 时追加 trace 输出。
  - `tests/test_orchestration_route_decision_trace.py`：新增 13 个测试，覆盖默认无 trace、trace 结构、max_risk 拒绝、preferred 降级、显式 adapter 阻塞、无匹配 capability、preflight 复用、source mutation、无 schema dump、disabled 过滤、readonly、人类可读输出。
  - `docs/49-capability-routing-model.md`：新增“路由决策解释（Decision Trace）”小节。
  - `docs/000-stage-digest.md`：Stage 11 小节追加 `--explain` trace 说明。
  - `docs/10-cli-poc-usage.md`：route preview / preflight 示例追加 `--explain`。
  - `docs/02-roadmap.md`：Stage 11 已落地能力追加 decision trace。
  - `tasks/progress.md`：追加本条目。
- 未实现 / 仍后续：cost / latency / availability 在线打分；真实 runner 在线状态；自动 fallback / retry 执行。
- 未修改 schema；未进入 Stage 12 实现；未声称 Stage 11 全部完成。
- 临时产物：`.superpowers/specs/2026-07-11-route-decision-trace-design.md`、`.superpowers/plans/2026-07-11-route-decision-trace.md`，任务结束后按新规则迁移到项目外临时备份目录（`stage11-route-decision-trace-20260711` 子目录）。
- 验证：
  - `python -m pytest tests/test_orchestration_route_decision_trace.py -q`：通过。
  - 聚焦与全量测试、doctor、public_scan、diff check 结果见任务最终汇报。

## 2026-07-11 — Stage 12：Control Plane State Model 第一拍 — Routing Decision Snapshot

- 目标：把 Stage 11 route/preflight 决策投影为稳定、compact、只读的控制面状态对象 `RoutingDecisionSnapshot`，不写 ledger、不生成持久 Run、不执行真实 adapter。
- 设计要点：
  - `snapshot_id` 由 canonical safe payload 的 SHA-256 内容哈希确定性生成；无时间戳、随机数、进程状态。
  - snapshot 必须由真实 `preview_route` / `check_preflight` 结果投影，不得重算路由。
  - routing 状态与 guardrail 状态分层：`routing.status` vs `guardrail.status`（仅 preflight snapshot）。
  - 默认旧命令 `route preview` / `preflight` 输出严格不变。
- 修改文件：
  - `agent_runtime/orchestration_routing_snapshot.py`：新增 `RoutingDecisionSnapshot` dataclass、`_compute_snapshot_id`、`_canonical_json`、`build_routing_snapshot`、`build_preflight_snapshot`。
  - `agent_runtime/cli.py`：
    - 新增 `_build_route_constraints_from_args` 全局 helper。
    - 新增 `_emit_routing_snapshot` emitter。
    - 新增 `_cmd_orchestration_route_snapshot` 命令与 parser。
    - `orchestration preflight` 增加 `--request-id`、`--snapshot` flag；`_cmd_orchestration_preflight` 在 `--snapshot` 时输出 snapshot。
  - `tests/test_orchestration_routing_snapshot.py`：新增 15 个测试，覆盖结构、确定性、guardrail、blocked/needs_input、trace 可选、route/preflight 一致性、无敏感载荷、source mutation、readonly、人类可读输出、默认兼容。
  - `docs/50-control-plane-state-model.md`：新增 `RoutingDecisionSnapshot` 小节。
  - `docs/51-backend-first-api-boundary.md`：操作模型表增加 `routing_snapshot` / `preflight_snapshot`。
  - `docs/000-stage-digest.md`：新增 Stage 12 第一拍小节。
  - `docs/10-cli-poc-usage.md`：新增 snapshot 示例。
  - `docs/02-roadmap.md`：Stage 12 增加已落地第一拍与仍后续。
  - `tasks/progress.md`：追加本条目。
- 明确未实现：snapshot 与持久化 Run/Event 对象的衔接；Task/Run/Approval/Artifact/Evidence/Report 完整字段与生命周期。
- 未声称 Stage 12 完成；未修改 schema；未 commit/push。
- 临时产物：`.superpowers/specs/2026-07-11-routing-decision-snapshot-design.md`、`.superpowers/plans/2026-07-11-routing-decision-snapshot.md`，任务结束后迁移到项目外临时备份目录（`stage12-routing-decision-snapshot-20260711` 子目录）。
- 验证：
  - `python -m pytest tests/test_orchestration_routing_snapshot.py -q`：通过。
  - 聚焦与全量测试、doctor、public_scan、diff check 结果见任务最终汇报。

## 2026-07-11 — Stage 12：Routing Decision Snapshot 审查返工

- 修复点 1：`routing` 对象中稳定加入 `status` 字段，表达路由层自身状态；preflight snapshot 中顶层 `status`、routing.status、guardrail.status 三层正确分层。
- 修复点 2：`build_preflight_snapshot` 不再通过 `base.to_dict()` 携带中间 `snapshot_id` 计算最终哈希；改为直接构造最终 canonical payload（schema_version/status/routing/constraints/source/可选 trace/guardrail），再计算 `snapshot_id`。
- 修复点 3：新增测试覆盖：
  - `routing.status` 在 route snapshot / blocked route / preflight 三种场景正确。
  - routing pass + guardrail needs_approval/blocked 时三层状态分层正确。
  - route snapshot 与 preflight snapshot 的 `snapshot_id` 均等于最终 payload（去掉 `snapshot_id`）的 canonical SHA-256 哈希。
- 修改文件：
  - `agent_runtime/orchestration_routing_snapshot.py`：新增 `_build_payload` helper；`_routing_layer` 增加 `status`；`build_preflight_snapshot` 直接构造最终 payload。
  - `tests/test_orchestration_routing_snapshot.py`：新增 6 个测试。
- 验证：
  - 聚焦测试：`tests/test_orchestration_routing_snapshot.py` 22 passed。
  - 全量测试、doctor、public_scan、diff check 通过。

## 2026-07-11 — Stage 12：Routing Snapshot → Run Preview 安全引用第一拍

- 目标：在 `orchestration run --dry-run` 中加入对 Stage 12 `RoutingDecisionSnapshot` 的安全引用，保持只读、不持久化、不执行真实 adapter。
- 修改文件：
  - `agent_runtime/orchestration_run_dry_run.py`：
    - `RunDryRunResult` 新增 `routing_snapshot_id` 字段，条件输出。
    - `dry_run_run` 新增 `routing_snapshot_id` 参数，入口校验 `^sha256:[a-f0-9]{64}$`；非法返回 `needs_input`。
    - `_compute_plan_hash` 纳入 `routing_snapshot_id`；`_build_candidate_events_summary` 在 `run_planned` metadata keys 中追加；`_build_artifact_candidate_refs` 为每个 ref 追加。
  - `agent_runtime/orchestration_run_commit.py`：`commit_run` 新增 `routing_snapshot_id` 参数并透传给 `dry_run_run`，保证 commit 路径 plan hash 一致。[已撤回]
  - `agent_runtime/cli.py`：`orchestration run` parser 新增 `--routing-snapshot-id`；`_cmd_orchestration_run` 透传给 dry-run/commit；human 输出条件打印。
  - `tests/test_orchestration_run_dry_run.py`：新增 11 个测试，覆盖引用注入、默认兼容、plan hash 稳定与差异、非法格式/路径、retry/fallback 引用、CLI JSON/human 输出。
  - `docs/50-control-plane-state-model.md`：新增 Routing Decision Snapshot → Run Preview 安全引用小节。
  - `docs/52-minimal-orchestration-loop.md`：在 Adapter Dry-run / Commit 步骤说明 `--routing-snapshot-id` 引用语义。
  - `docs/10-cli-poc-usage.md`：Run dry-run preview 段增加带 snapshot id 的示例与说明。
  - `docs/000-stage-digest.md`：新增“Routing Snapshot → Run Preview 安全引用第一拍”小节，更新“现在已经能做什么”与“下一步做什么”。
  - `docs/02-roadmap.md`：Stage 12 已落地第一拍追加安全引用说明。
- 明确边界：
  - 只接受 `sha256:<64 lowercase hex>`，非法值返回 `needs_input`，不读取任意路径或 JSON。
  - 不校验 snapshot 磁盘存在性；它是 content-addressed reference contract，不是假装持久化。
  - 默认不传时旧输出与旧 `plan_hash` 兼容。
  - retry / fallback dry-run 同样支持引用，lineage 与 routing snapshot 各自独立。
- 未实现：snapshot 与持久化 Run/Event 对象的真实衔接；独立 Run storage；真实 adapter execution。
- 未声称 Stage 12 完成；未 commit/push。

## 2026-07-11 — Stage 12：Routing Snapshot → Run Preview 安全引用审查返工

- 返工点 1：严格限定 `--routing-snapshot-id` 仅支持 `--dry-run` preview。
  - 移除 `agent_runtime/orchestration_run_commit.py` 中的 `routing_snapshot_id` 参数与透传。
  - `agent_runtime/cli.py` 在 `--commit` 分支检测到 `--routing-snapshot-id` 时直接返回 `blocked`（rule_id=`routing-snapshot-id-not-supported-in-commit`），不进入 `commit_run`、不写 envelope/ledger。
  - 新增 CLI 测试 `test_cli_commit_with_routing_snapshot_id_blocked_and_no_writes`：验证返回 `blocked` 且 tasks/events/drafts 均无变化。
- 返工点 2：非法格式 finding 不再回显原始输入。
  - `agent_runtime/orchestration_run_dry_run.py` 中 `invalid-routing-snapshot-id` 的 message 改为固定文本 `--routing-snapshot-id must match 'sha256:<64 lowercase hex chars>'.`，不再包含 `received value`。
  - 新增测试 `test_dry_run_invalid_routing_snapshot_id_does_not_echo_raw_value`：使用类 token 字符串验证 JSON 输出中不包含原值。
- 返工点 3：文档口径校正。
  - `docs/50-control-plane-state-model.md`、`docs/52-minimal-orchestration-loop.md`、`docs/10-cli-poc-usage.md` 明确说明 `--commit` 传入该引用会被拒绝、本拍仅 `--dry-run` 支持。
  - `tasks/progress.md` 追加本返工条目，替换之前“commit 路径透传”的越界描述。
- 未修改其余设计；未 commit/push。

## 2026-07-11 — Stage 12：Run Preview → Event / Report 只读投影闭环

- 目标：在 `orchestration run --dry-run` 基础上新增 `--snapshot`，基于真实 `RunDryRunResult` 一次性构造 `OrchestrationReadLoopSnapshot` 只读闭环 snapshot，包含 Run Preview + candidate Event summaries + Report Preview；不写 ledger、不生成持久 Run/Event/Report、不执行 adapter。
- 设计要点：
  - 新增 `agent_runtime/orchestration_read_loop_snapshot.py`：定义 `OrchestrationReadLoopSnapshot`、`build_read_loop_snapshot`、`_canonical_json`、`_compute_snapshot_id`。
  - `snapshot_id` 直接 hash 最终安全 payload（去掉 `snapshot_id`），无时间戳/随机数/进程状态；相同输入 byte-equivalent。
  - Run 层：`pass` / `needs_approval` 时 `run.status` 映射为 `"planned"`，其余状态原样传播；包含 `plan_hash`、可选 `routing_snapshot_id`、lineage。
  - Event 层：从 `candidate_events_summary` 投影 `event_type`、`status=planned`、`metadata_keys`；不伪造 `event_id`/`timestamp`。
  - Report 层：`status=preview`，输出 candidate event/artifact 计数与类型分布、`requires_approval`、`next_action`、仅 `rule_ids` 的 finding 摘要；无 `report_id`。
  - 错误/阻断/需要输入状态仍生成 snapshot，但 candidate events 为空、report 计数为零。
- 修改文件：
  - `agent_runtime/orchestration_read_loop_snapshot.py`：新增 read-loop snapshot 模块。
  - `agent_runtime/cli.py`：`orchestration run` parser 新增 `--snapshot` flag；新增 `_emit_read_loop_snapshot`；`_cmd_orchestration_run` 在 dry-run 分支 `--snapshot` 时输出 snapshot，commit 分支 `--snapshot` 时返回 `blocked`。
  - `tests/test_orchestration_read_loop_snapshot.py`：新增 18 个测试，覆盖结构、needs_approval、blocked/needs_input、确定性、snapshot_id hash、source mutation、无敏感载荷、routing_snapshot_id、lineage、CLI JSON/human、默认兼容、commit 拒绝与无写入、round-trip 数据契约。
  - `docs/50-control-plane-state-model.md`：新增 Run Preview → Event / Report Read-Loop Snapshot 小节。
  - `docs/51-backend-first-api-boundary.md`：Task 操作表后说明 `--dry-run --snapshot` 产生 ephemeral read model。
  - `docs/52-minimal-orchestration-loop.md`：Adapter Dry-run / Commit 步骤补充 `--snapshot` 语义。
  - `docs/53-minimal-orchestration-loop-cli-draft.md`：`orchestration run --dry-run` 说明追加 `--snapshot`。
  - `docs/10-cli-poc-usage.md`：新增 run dry-run `--snapshot` 示例与说明。
  - `docs/000-stage-digest.md`：新增“Run Preview → Event / Report 只读投影闭环”小节；更新“现在已经能做什么”。
  - `docs/02-roadmap.md`：Stage 12 已落地第一拍追加 read-loop snapshot 闭环说明。
  - `tasks/progress.md`：追加本条目。
- 明确边界：
  - 默认 `--dry-run` 输出与 `plan_hash` 严格兼容；传入 `--snapshot` 仅新增 snapshot 字段。
  - `--commit` 模式下 `--snapshot` 与 `--routing-snapshot-id` 均被明确拒绝，不写任何文件/ledger。
  - 不持久化 snapshot，不写入 task/event/run ledger，不生成独立 Report 集合，不执行真实 adapter。
- 未实现：snapshot 与持久化 Run/Event 对象的真实衔接；独立 Run storage；真实 adapter execution。
- 未声称 Stage 12 完成；未 commit/push。
- 临时产物：任务结束后按规则迁移 `.superpowers/` 到项目外临时备份目录（`stage12-read-loop-snapshot-20260711` 子目录）。

## 2026-07-11 — Stage 12 第二拍沉淀审查返工

- 审查返工 1：`run.gate_status` / `report.gate_status` 稳定分层；`pass` → `ready`，`needs_approval` → `pending_approval`，其余状态原样传播；`report.status_summary` 同步输出。测试覆盖 needs_approval 不会被误判为 ready。
- 审查返工 2：candidate events 保持 `status=planned`，测试锁住无 `event_id` / `timestamp`；`approval_requested` 明确为候选预览。
- 审查返工 3：`tasks/progress.md` 中“`agent_runtime/orchestration_run_commit.py` 透传 `routing_snapshot_id`”的原条目已标记 `[已撤回]`。
- 审查返工 4：按 `docs/MAINTENANCE.md` 规则，将阶段收口 release notes 从 `docs/72-release-notes-read-loop-snapshot.md` 迁移到 `docs/archive/release-notes/72-release-notes-read-loop-snapshot.md`；更新 `docs/00-index.md`、`docs/000-stage-digest.md`、handoff 中所有引用路径；`docs/` 根目录不再保留 72 release notes。
- 审查返工 5：handoff 明确候选基线为当前 HEAD `bba0ced` + 本轮未提交变更。
- 审查返工 6：`docs/02-roadmap.md` Stage 12 标题更新为“read-only loop 第一版已落地，持续巩固”，不声称完整 Stage 12 完成。
- 建议 tag 保持候选：`v0.12.1-orchestration-read-loop-snapshot`，未打 tag。
- 验证：
  - `python -m pytest tests -q`：通过。
  - `python -m agent_runtime.cli doctor`：PASS。
  - `python tools/public_scan.py`：OK。
  - `bash .githooks/pre-commit`（临时 staging 后运行）：✅ docs maintenance check passed。
  - `git diff --check`：无空白错误（仅 Git LF/CRLF 设置提示）。
- 未 commit/push。

## 2026-07-11 — v0.12.1-orchestration-read-loop-snapshot 冻结完成（post-freeze 文档同步）

- 实际冻结 commit：`0419a04`。
- annotated tag：`v0.12.1-orchestration-read-loop-snapshot` 已创建并 push。
- 同步更新的文档：
  - `README.md` / `README.en.md`：最新里程碑基线改为 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`，保留 `v0.12.0-orchestration-foundation` / `38b4b69` 历史说明。
  - `AGENTS.md`：当前阶段改为 Stage 12 read-only loop 已冻结，基线同步。
  - `docs/000-stage-digest.md`：当前基线、当前阶段、下一步改为 recovery lineage aggregation read model。
  - `docs/02-roadmap.md`：顶部版本治理说明与 Stage 12 冻结状态补充。
  - `docs/64-versioning-governance.md`：追加 `v0.12.1` 实际冻结事实。
  - `docs/archive/release-notes/72-release-notes-read-loop-snapshot.md`：追加后续状态补充。
  - `tasks/handoff-2026-07-11-read-loop-snapshot-stage-acceptance.md`：更新为完成态，指向 `0419a04` 与已推送 tag。
  - `tasks/progress.md`：追加本条目。
  - `docs/00-index.md`：最新 milestone 文档指向归档 `72-release-notes-read-loop-snapshot.md`。
- 下一步：recovery lineage aggregation read model（post-freeze），入口 `docs/50-control-plane-state-model.md` / `docs/52-minimal-orchestration-loop.md` / 最新 handoff。
- 边界不变：只读、无网络、无凭据、无 UI/service/DB。
- 未 commit/push（由主控决定）。

## 2026-07-12 — Recovery Lineage Aggregation Read Model 第一版

- 新增 `docs/73-recovery-lineage-aggregation-read-model.md`，冻结 ledger-backed 数据源、确定性链解析、多 leaf 与异常语义、安全边界。
- 新增 `agent_runtime/orchestration_recovery.py`：聚合 `run_planned` / `run_draft_exported` / `run_blocked` metadata，输出 root/latest/leaves、attempt count、effective plan hash 与安全 request summaries。
- `orchestration run inspect` 新增显式 `--aggregate-lineage`；默认输出兼容，多 leaf 返回 `needs_input`，missing/cross-task parent、cycle 与重复 metadata 冲突返回 `validation_failed`。
- 新增 `tests/test_orchestration_recovery.py`，并扩展 `tests/test_orchestration_run_inspect.py` 的 JSON/human/default compatibility/validation failure 覆盖。
- 边界保持：只读、不扫描 drafts、不增加 event type、不写 ledger、不执行 adapter、不访问网络。

## 2026-07-12 — Recovery Lineage Aggregation 文档收口与下一轮上下文

- `README.md` / `README.en.md` 移除已过期的“下一步进入 retry/fallback commit”表述，更新为 aggregation stage acceptance。
- `docs/00-index.md` 的当前最重要文档改为 digest → 73 design → roadmap → CLI usage → 最新 handoff。
- `docs/73-recovery-lineage-aggregation-read-model.md` 吸收实现状态、commit、测试入口与下一轮验收清单，成为单一设计事实源。
- 删除已完成且内容已被 73 design / handoff 吸收的临时 implementation plan，减少重复文档。
- `tasks/handoff-2026-07-12-recovery-lineage-aggregation.md` 补实现 commit、恢复顺序与“不要重复实现”的边界。

## 2026-07-12 — Recovery Lineage Aggregation 阶段验收通过

- 按 `docs/73-recovery-lineage-aggregation-read-model.md` 的验收入口完成复核：duplicate lifecycle merge、branch / missing parent / cross-task parent / cycle、非法 lineage shape、JSON/human 脱敏、默认 inspect 兼容和 no-write 边界均符合契约。
- 验证：`python -m pytest tests -q`、`python -m agent_runtime.cli doctor`、`python tools/public_scan.py`、`python -m compileall -q agent_runtime tests`、`git diff --check` 均通过。
- 下一步从“实现聚合”转为“复用决策”：比较 `orchestration run list` / `report generate` 的价值与兼容成本，先定最小契约，不进入真实执行。


## 2026-07-12 — Recovery Lineage 复用到 Report Generate

- 比较 `run list` 与 `report generate` 后，选择低兼容成本的单 request report 入口；`run list` 保持 envelope-scoped。
- 新增 `orchestration report generate --aggregate-lineage`，复用 `control-plane/recovery-lineage/v1` 与既有 aggregation 模块。
- 显式 flag 下输出 `recovery_lineage` 并合并 aggregation 状态；默认 report 输出保持兼容，human 仅输出安全紧凑摘要。
- 新增 JSON、human、默认兼容、validation failure 状态提升和 no-write 测试。


## 2026-07-12 — Recovery Read Model Consolidation 验收

- 新增 inspect/report 跨入口契约测试，覆盖正常链、branch、missing focus/parent、cross-task parent、cycle、duplicate conflict、脱敏和 no-write。
- 提取 `merge_recovery_status()` 作为共享状态严重度合并规则，删除 inspect/report 中两份重复 precedence。
- 同一 lifecycle events 下两个入口返回完全一致的 `control-plane/recovery-lineage/v1` payload。
- 下一步转为集合级 lineage 需求评估；无明确消费者时不改造 `run list`。

## 2026-07-12 — Stage 12 Control Plane State Model 最终收口

- 对照 roadmap 与 50/51 设计文档完成最终审计：对象关系、顶层/附属分类、routing/read-loop snapshot、recovery lineage inspect/report、默认兼容、确定性、脱敏与 no-write 均具备验收证据。
- 将持久化 Run/Event/Report storage、snapshot 到持久对象衔接、协议、鉴权、service、DB、UI 和真实 adapter execution 正式延期，不再作为 Stage 12 悬挂项。
- 明确 collection-level lineage 暂无消费者，本阶段不实现 index，不改造 envelope-scoped `run list`。
- 新增 `docs/archive/release-notes/75-release-notes-stage12-control-plane-state-model.md`，作为 Stage 12 最终验收记录；最终验收 commit：`5e8df01`。
- 当前阶段切换为 Stage 13 — Backend-first API Boundary，第一拍为 Boundary Contract Reconciliation，事实源为 `docs/51-backend-first-api-boundary.md`。
- 稳定 semver 基线继续保持 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`，本轮不新增 tag。

## 2026-07-12 — Stage 12 收口后的文档一致性审查

- 审查 README、roadmap、Stage 13 事实源、stage digest、AGENTS、索引和最新 handoff；恢复入口与 Stage 12 验收事实保持一致。
- README 的项目现状改为“离线、可审计 CLI / Runtime 已可内部试用”，同时明确真实 adapter execution、持久化 service/DB、鉴权和 UI 仍未开放。
- 修正 roadmap 中 Stage 9 仍标为“当前阶段”、Stage 11 仍标为“下一步高优先级”的过期标签；Stage 13 保持唯一当前阶段。
- 将 51 文档的协议/UI 衔接标为长期方向，明确当前第一拍仍是 Boundary Contract Reconciliation。
- 未新增重复设计文档，未改变代码、schema、安全边界或 semver/tag。

## 2026-07-13 — Stage 13 首轮 Boundary Contract Reconciliation

- 对照真实 `orchestration` CLI help、现有 read-model 测试和 51 资源/操作模型完成首轮对账。
- 更新 `docs/51-backend-first-api-boundary.md`：修正真实命令名，区分 stable、受限 stable、preview 和 unavailable，并明确 run/report 的 envelope/request 边界。
- 确认当前可稳定复用的是受限 CLI/read model；独立 Run/Report collection、真实 adapter execution、service/auth/DB/UI 不伪装为已实现。
- 下一拍：为 stable/preview/unavailable 矩阵补字段、错误和默认兼容测试，不进入协议选型或服务化。
