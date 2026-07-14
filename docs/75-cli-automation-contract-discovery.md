<!-- parents: 51-backend-first-api-boundary.md, 52-minimal-orchestration-loop.md -->
<!-- relates: 02-roadmap.md, 10-cli-poc-usage.md -->

# 75 — CLI 自动化契约发现与 Requirement Gate

## 定位

本增量把 Stage 13 已冻结、Stage 14 已验证的 `stable` / `stable_limited` / `preview` / `unavailable` 边界投影为机器可读的本地 CLI manifest，供脚本、CI 和未来宿主在调用 orchestration 命令前做能力发现。

它不是 HTTP discovery endpoint，不新增服务、数据库、鉴权或持久资源，也不改变任何既有命令的默认输出。

## 方案选择

候选方案：

1. 新增显式只读契约发现命令；
2. 给所有既有 JSON 输出追加统一版本字段；
3. 新增自动串联 routing / preflight / run / report 的批处理命令。

选择方案 1。原因是它不破坏默认输出兼容，不复制编排计算，并能以最小增量为 CLI 自动化提供稳定的 capability negotiation 入口。

## CLI 边界

新增：

```bash
python -m agent_runtime.cli orchestration contract inspect --json
```

人类可读模式输出契约版本、条目数量和每个条目的 availability/access/command 摘要；`--json` 输出完整 manifest。

命令只读取代码内冻结的安全元数据，不读取 ledger、adapter registry、环境变量或凭据，不写文件，不访问网络。

## Manifest v1

顶层字段：

- `status`: 固定为 `pass`；
- `schema_version`: `control-plane/orchestration-contract/v1`；
- `consumer`: `cli-automation`；
- `entries`: 按 `contract_id` 确定性排序的契约条目；
- `summary`: 各 availability 分类计数；
- `guarantees`: no-write、no-network、no-adapter-execution 和 deterministic 声明。

每个条目字段：

- `contract_id`: 稳定机器标识；
- `availability`: `stable`、`stable_limited`、`preview` 或 `unavailable`；
- `access`: `read_only`、`controlled_write` 或 `unavailable`；
- `commands`: 可用入口的 argv 片段列表；不可用能力必须为空列表；
- `key_flags`: 影响 preview、commit、lineage、replay 等边界的关键 flag；
- `boundary`: 简短安全边界，不包含路径、payload、secret 或运行时数据。

v1 覆盖 `docs/51-backend-first-api-boundary.md` 的首轮契约矩阵，不声称存在独立 Run/Report collection、orchestration Artifact export 或真实 adapter execution。

## 实现约束

- 新模块只定义 immutable source entries 和确定性 projection；
- production manifest 不通过解析 argparse help 动态生成，避免把展示文案误当事实源；
- 契约测试反向校验所有非 unavailable command path 都真实存在于 argparse surface，防止 manifest 与 CLI 漂移；
- 新命令是显式新增 surface，既有命令与默认 JSON 保持不变；
- 不新增 JSON Schema 文件，`schema_version` 仅作为 DTO 版本标识。

## TDD 与验收

1. 先增加失败测试，冻结 manifest 字段、排序、分类计数和 unavailable 空命令约束；
2. 增加 CLI JSON / human-readable / determinism / no-write 测试；
3. 更新 Stage 13 surface contract 测试并验证新增 `contract inspect`；
4. 最小实现 `agent_runtime/orchestration_contract.py` 与 CLI wiring；
5. 更新 `docs/00-index.md`、`docs/10-cli-poc-usage.md`、`docs/000-stage-digest.md` 和 roadmap；
6. 运行全量 pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check 与 pre-commit。

## 明确不做

- 不自动执行 manifest 中的命令；
- 不新增 batch workflow；
- 不读取在线 availability；
- 不把 preview 升级为 stable；
- 不引入服务协议、UI、数据库、鉴权或真实 adapter execution。

## 第二拍：Requirement Gate

### 目标

在 discovery 之上增加一个真正消费 v1 manifest 的只读 requirement gate，让脚本或 CI 在执行任何 orchestration 操作前判断所需契约是否可用，而不是自行解释 availability/access 字段。

新增入口：

```bash
python -m agent_runtime.cli orchestration contract check \
  --require task_read \
  --require routing_preflight \
  --require run_plan \
  --json
```

### 输入约束

- `--require <contract-id>`：可重复且至少出现一次；实现按 contract id 去重并排序。
- `--allow-preview`：默认关闭；未显式允许时，preview requirement 返回 `needs_input`。
- `--max-access read_only|controlled_write`：默认 `controlled_write`；调用方可显式收紧为 `read_only`。

该 gate 只评估 manifest，不执行被声明的 command，不读取 ledger/registry，不写文件，不访问网络。

### 结果模型

使用 `control-plane/orchestration-contract-check/v1`：

- `status`：`pass`、`needs_input` 或 `blocked`；
- `constraints`：回显规范化后的 `allow_preview` 与 `max_access`；
- `requirements`：逐项输出 `satisfied`、`unknown`、`unavailable`、`preview_not_allowed` 或 `access_exceeded`；
- `summary`：总数、满足数、不满足数；
- `next_action.code`：稳定的机器动作码。

状态规则：

1. 空 requirement 集合：`needs_input` / `provide_requirements`；
2. 已知 stable/stable_limited 且 access 不超限：`satisfied`；
3. preview 未显式允许：`preview_not_allowed`，总体至少为 `needs_input`；
4. 未知 contract id：`unknown`，总体至少为 `needs_input`；
5. manifest 明确 unavailable：`unavailable`，总体为 `blocked`；
6. access 超过 `--max-access`：`access_exceeded`，总体为 `blocked`；
7. 多问题并存时，`blocked` 高于 `needs_input`，但逐项结果完整保留。

稳定 next-action code：

- `provide_requirements`
- `requirements_satisfied`
- `provide_known_contract_ids`
- `allow_preview_or_choose_stable`
- `choose_available_contract`
- `raise_max_access_or_choose_read_only`

### 实现与测试边界

- 新建独立 requirement evaluation 模块，复用 `build_contract_manifest()`，不维护第二份 capability table；
- manifest 增加自描述的 `contract_requirement_gate` stable 条目；
- 测试覆盖 pass、去重排序、unknown、unavailable、preview opt-in、access ceiling、混合问题优先级、CLI 退出码、determinism、no-write 与 argparse command/flag 漂移；
- 既有 `contract inspect` schema_version 与字段保持兼容，仅新增一个排序后的 entry 和相应 summary 计数。

## 第三拍：Automation Profile

### 目标与方案

Requirement Gate 已能判断一组临时 `--require`，第三拍把 requirement 集合与约束命名化为项目内可版本控制的 Automation Profile，供 CI、本地只读审计和受控写入准备复用。

选择 source-backed JSON registry，而不是把 profile 硬编码在 CLI 或立即引入 workflow runner：

- source of truth：`automation/automation-profiles.sample.json`；
- schema：`automation/automation-profiles.schema.json`；
- 固定从项目 root 读取，不提供任意 `--profiles-file`，避免扩大文件读取范围；
- profile check 直接调用 `check_contract_requirements()`，不复制 requirement 计算；
- 不执行 profile 中声明的 command，不生成 workflow plan，不写 ledger。

### Profile v1

registry 顶层：

- `schema_version`: `control-plane/automation-profiles/v1`；
- `profiles`: profile 数组，`profile_id` 必须唯一。

单个 profile：

- `profile_id`: 小写短横线 id；
- `description`: 安全、简短说明；
- `required_contracts`: 至少一个 contract id，元素唯一；
- `allow_preview`: 是否显式接受 preview；
- `max_access`: `read_only` 或 `controlled_write`。

首批样例：

- `ci-read-only`：只消费 stable/stable_limited read models；
- `local-dry-run`：显式接受 run/read-loop preview，但限制为 read-only；
- `local-controlled-write`：允许 controlled-write requirement，但 gate 本身仍不执行写操作。

### CLI

```bash
python -m agent_runtime.cli orchestration profile list --json
python -m agent_runtime.cli orchestration profile inspect --profile-id ci-read-only --json
python -m agent_runtime.cli orchestration profile check --profile-id local-dry-run --json
```

输出版本：

- list：`control-plane/automation-profile-list/v1`；
- inspect：`control-plane/automation-profile/v1`；
- check：`control-plane/automation-profile-check/v1`，内嵌原始 `contract_check` projection。

未知 profile 返回 `needs_input`；registry 缺失、JSON/schema 错误、重复 profile id 返回结构化 `validation_failed`，不得 traceback 或回显敏感内容。

### 安全与兼容

- list/inspect/check 均只读、确定性、no-network、no-command-execution；
- list 按 profile id 排序，required contracts 在 projection 中去重排序；
- doctor 纳入 automation schema/sample 校验；
- manifest 增加 `automation_profile_read` 与 `automation_profile_check` stable 条目；
- 既有 contract discovery/check 默认字段保持兼容，仅 manifest entries/summary 追加新能力；
- 不支持自定义任意文件路径、profile 继承、变量替换、条件表达式或 workflow execution。

## 第四拍：Read-only Workflow Plan Projection

### 目标与方案

Automation Profile 已冻结一组命名化 requirements 与边界约束，第四拍只把通过 Requirement Gate 的 profile 投影为可审计的工作流步骤，不执行任何步骤。

- CLI：`orchestration workflow plan --profile-id <id>`；
- 输出 schema：`control-plane/automation-workflow-plan/v1`；
- profile 仍从固定 `automation/automation-profiles.sample.json` 读取；
- 先复用 `check_automation_profile()`，只有 gate 为 `pass` 时才生成步骤；
- 每个步骤的 command、flag、availability、access 与 boundary 直接来自 `build_contract_manifest()`，不维护第二份 capability table；
- planner 只维护稳定的阶段分组与顺序：`discovery`、`inspect`、`decide`、`prepare`、`controlled_write`、`observe`，未映射能力落入 `capability`；
- `plan_id` 对不含自身的规范化 JSON projection 做 SHA-256 内容寻址，同一输入产生相同 id 与相同输出；
- gate 未通过、未知 profile 或 registry 校验失败时保留原状态/findings/next_action，步骤为空。

### Step v1

每个步骤包含：

- `step_id`：`<phase>:<contract_id>`；
- `phase` 与 `contract_id`；
- `availability`、`access`、`boundary`；
- `candidate_commands`：manifest 声明的真实 CLI command 数组；
- `required_flags`：manifest 声明的关键显式边界 flag；
- `status=planned`、`execution=not_executed`。

步骤按固定 phase 顺序、再按 contract id 排序。summary 汇总总步骤数、各 phase 数量、preview 数量和 controlled-write 数量。

### 安全与兼容

- projection 是 ephemeral read model，不写文件/ledger、不执行 command/adapter、不访问网络；
- controlled-write requirement 只会生成带 `--commit` 等显式 flag 的候选步骤，不会触发写入；
- manifest 增加 `automation_workflow_plan` preview/read-only 条目；
- 不支持 workflow execution、变量替换、条件分支、后台服务或任意 profile 路径；
- 既有 profile/contract 默认输出保持兼容，仅 manifest entries/summary 追加能力。
