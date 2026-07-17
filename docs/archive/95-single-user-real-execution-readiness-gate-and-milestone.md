<!-- parents: archive/94-filtered-snapshot-validated-markdown-presentation-handoff-gate.md, 58-orchestration-run-controlled-execution-design.md -->
<!-- relates: 48-adapter-runtime-interface.md, 56-orchestration-controlled-write-boundary.md, 64-versioning-governance.md -->

# 95 — Single-user Real Execution Readiness Gate and Milestone

> 状态：**Stage 43 design、Stage 44 implementation、Stage 45 提交级 milestone closure 均已收口**
> 日期：2026-07-16
> 前置基线：`v0.17.0-filtered-snapshot-display-host-integration`
> 里程碑形态：Stage 45 提交级收口；本阶段不创建 tag

## 1. 目标

下一里程碑不直接执行外部命令，而是把“距离第一次真实执行还缺什么”变成版本化、确定性、可测试的只读门禁。它必须同时做到：

1. 固定单用户本地 operator 模型，不实现多用户身份与授权；
2. 保留 future `actor_context` 扩展点，不把单用户假设散落到 executor；
3. 选定唯一首个候选 adapter/action；
4. 冻结 exact argv、cwd、environment、timeout、I/O、network/write/retry 边界；
5. 冻结 approval → plan binding 与 execution audit contract；
6. 如实报告 executor、approval binding 与 audit writer 尚未实现；
7. 不启动进程、不探测 credential、不访问网络、不写 ledger。

readiness `blocked` 是当前预期结果，不表示 gate 失败，而表示 contract 已就绪、真实执行仍被实现缺口阻断。

## 2. 单用户身份边界

v1 固定：

```text
mode = single_user_local
actor = local-operator
multi_user_authorization = false
future_extension = actor_context
```

不实现 account、role、tenant、session、login、token、ACL 或权限数据库。future extension 只作为 contract 名称，不读取操作系统用户名，不伪造认证证明。所有未来 execution event 必须显式携带 actor，但 v1 actor 只能来自固定 readiness profile，不能接受任意 CLI 字符串覆盖。

## 3. 首个候选执行动作

唯一候选：

```text
adapter_id = shell-local
capability = git_status
operation = git_status
risk_level = local
requires_approval = false
argv = ["git", "status", "--short", "--branch"]
```

虽然 registry adapter 名称为 `shell-local`，future executor 不得启动 shell。必须使用 argv array、`shell=False`，cwd 固定为 project root。不得开放 `local_command`、任意 argv、任意 cwd、stdin script 或环境变量注入。

选 `git_status` 的原因：只读、可观察、无网络需求、输出有界、用户价值明确；同时通过 `GIT_OPTIONAL_LOCKS=0` 抑制 Git optional lock/write 行为。

## 4. 固定 process contract

- executable：`git`；实现阶段必须以安全方式解析固定 executable，不接受用户路径；
- argv：exact `git status --short --branch`；
- cwd：`project_root`；
- inherited env allowlist：`PATH`、`SYSTEMROOT`、`WINDIR`；
- fixed env：`GIT_OPTIONAL_LOCKS=0`；
- timeout：默认 10 秒，最大 30 秒；
- stdout/stderr：各 64 KiB；
- retry：0；
- network：禁止；
- project file write：禁止；
- stdin：关闭；
- background/session：禁止；
- cancel：future one-shot process terminate/kill，当前不实现。

readiness gate 不检查本机是否安装 Git，因为 executable probe 本身属于 implementation/preflight 层，且环境相关结果不能污染确定性设计 gate。

## 5. Approval → plan binding contract

即使首个 `git_status` 候选不要求 approval，扩展到任何 `requires_approval=true` adapter 前必须实现：

- approval decision 绑定 `task_id`、`request_id`、`plan_hash`；
- 绑定 `adapter_id`、`capability`、`operation`；
- target 只绑定 canonical digest，不在安全输出复制原值；
- executor 在 spawn 前重算 current plan hash；
- granted decision、bound fields 与 current plan 任一不一致均 blocked；
- retry/fallback 不复用旧 approval；
- 固定 `approval_resolved` 只表示 decision，不表示已执行。

Stage 44 只验证该 contract 已被 profile 声明，并明确报告 implementation blocked；不修改现有 approval writer。

## 6. Execution audit contract

future executor 必须使用受控 append/rollback 模式写入：

```text
execution_started
execution_succeeded
execution_failed
execution_cancelled
```

安全 event metadata 允许：request/task/plan/adapter/operation identity、exit code、duration bucket、bounded output digest 与 truncation flags。禁止 ledger 持久化 raw stdout、raw stderr、完整 argv、absolute cwd、完整 environment、target 原文或 secret。

Stage 44 不扩展 event schema、不写 event；它必须检测上述 event types 和 writer 尚未实现，并保持 readiness blocked。

readiness gate 会验证 `tasks/event.schema.json` 自身是合法 JSON Schema，并确认上述 execution lifecycle event types 当前尚未进入 `event_type.enum`。event schema 结构漂移会阻断 `audit_contract`；schema 本身非法则返回固定、脱敏的 `validation_failed`。

> Stage 46 后续校正：pre-spawn 事实名改为 `execution_attempt_started`，明确表示“尝试已受控提交、child 可能尚未创建”；reserved execution event 必须由专用 writer 写入，通用 append/import 必须拒绝。Stage 44 readiness v1 保持历史 blocked snapshot，不回改为执行权限。

## 7. Source-backed readiness profile

新增固定文件：

- `adapters/execution-readiness.schema.json`
- `adapters/execution-readiness.sample.json`

profile 使用 `additionalProperties=false`，由 doctor 校验。readiness command 只读取固定 project-relative profile、adapter registry 与 event schema，不接受 file/path/URL 参数。

## 8. Stage 44 CLI contract

新增：

```text
python -m agent_runtime.cli orchestration execution readiness [--json]
```

固定输出 schema：

```text
control-plane/single-user-execution-readiness/v1
```

输出包含 status、schema/gate id、source placeholders、scope、process/approval/audit contracts、ordered checks、summary、safe findings、guarantees 与 next action。不得输出 absolute path、credential、环境值、raw ledger 或 traceback。

固定 13 项 checks：

1. `profile_schema`
2. `single_user_identity`
3. `candidate_registry_alignment`
4. `fixed_argv`
5. `working_directory`
6. `environment_allowlist`
7. `bounded_process`
8. `side_effect_boundary`
9. `approval_binding_contract`
10. `audit_contract`
11. `executor_implementation`
12. `approval_binding_implementation`
13. `audit_writer_implementation`

当前仓库前 10 项应 pass，后 3 项应 blocked；最终 status=`blocked`、readiness=`design_ready_implementation_blocked`、exit=2。

### 8.1 v1 是永久 blocked 的阶段快照

`control-plane/single-user-execution-readiness/v1` 不是实时探测 executor 模块的 capability detector。v1 profile 将 `executor`、`approval_binding`、`audit_writer` 固定为 `false`，用于永久记录 Stage 44 时点的三个已知实现缺口：

- 后续不得直接把 v1 profile 字段改成 `true` 来宣称真实执行就绪；
- 即使 Stage 46 之后实现 fixed executor，v1 仍保持 backward-compatible blocked snapshot；
- future implementation readiness 必须使用新的 v2 schema/gate，或独立、可验证的 implementation gate；
- 任何 future `pass` 都必须来自真实 module/schema/writer capability 检测，不能由 profile 自报；
- v1 的 10 项 pass 只表示设计契约和 pre-execution ledger state 对齐，不授予 subprocess 权限。

## 9. TDD 验收矩阵

Stage 44 RED tests 至少覆盖：

1. CLI surface 与 v1 exact wrapper；
2. 单用户 boundary 与 future extension；
3. registry candidate/capability/risk/`requires_approval=false` alignment；
4. fixed argv、shell false、cwd/env/bounds/no network/no write/no retry；
5. approval binding exact fields；
6. audit event contract 与 no raw output；
7. ordered 13 checks、10 pass/3 blocked；
8. deterministic、read-only、value-safe；
9. malformed profile/schema/registry/event schema safe failure；
10. orchestration contract manifest 增加 preview/read-only readiness，真实 execution 仍 unavailable；
11. doctor 校验新增 schema/sample；
12. source 不导入 subprocess/socket/requests，不调用 write/unlink/rename。

## 10. 明确延期

本里程碑不实现：

- subprocess spawn、Git executable probe 或真实 `git status`；
- 通用 shell/local command；
- approval writer plan binding；
- execution event schema/writer；
- credential、keyring、`.env` 或 Git auth；
- network/external adapter；
- multi-user identity/auth/role/tenant/ACL；
- service、DB、queue、background worker；
- UI write、browser、file export。

## 11. Stage 45 文档维护与提交级冻结

Stage 44 验收后统一执行：

- 更新 digest、index、roadmap、CLI usage、README/README.en、AGENTS、versioning、handoff、progress；
- 归档已冻结的旧活跃文档，保持 docs 根目录规模；
- 新增 Stage 44/45 release notes 104/105；
- 全量 pytest、doctor、public scan、docs hook、diff check；
- 创建本地提交前完成全量验收；
- 未经用户明确要求不创建 tag、不 push。

<!-- gate-status: passed-stage43 -->
<!-- implementation-status: completed-stage44 -->
<!-- milestone-status: closed-stage45-commit-level -->
