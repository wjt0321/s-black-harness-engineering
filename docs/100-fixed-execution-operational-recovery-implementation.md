<!-- parents: 99-fixed-execution-operational-recovery-design-gate.md, 98-fixed-git-status-executor-implementation-and-limited-enablement.md -->
<!-- relates: 97-execution-lifecycle-audit-writer-design-and-implementation.md, 64-versioning-governance.md -->

# 100 — Fixed Execution Operational Recovery Implementation

> 状态：**Stage 51 implementation 已完成并收口**
> 日期：2026-07-23
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`（已推送至 `origin`）
> 里程碑策略：Stage 51 形成 commit-level milestone；2026-07-25 按用户授权推送到 `origin/main`，不创建 tag

## 1. 阶段结论

Stage 51 按 `docs/99-fixed-execution-operational-recovery-design-gate.md` 实现 fixed execution operational recovery，没有扩大 Stage 49 的真实执行权限。唯一真实 operation 仍是 Windows 上显式 `--commit` 的 fixed `git status --short --branch`。

本阶段完成：

- fixed execution、trust first bind/rotation 与 recovery close 共用一个固定 machine-local exclusive lease；
- trust binding 的只读 inspection 与绑定旧 binding、新 executable identity、新 sanitized PATH identity 的 reviewed rotation；
- 对 locked execution ledger 的 bounded validation，以及 open attempt 的 list/inspect；
- 唯一 fixed outcome-unknown recovery close；
- Windows Job accounting 的 active-zero、direct-child reaped 与 containment closed release gate；
- 历史 `execution-audit/v1` 只读兼容，以及新 execution 使用 `execution-audit/v2`。

Stage 51 没有运行真实 fixed Git subprocess smoke。实现验收只使用 fake backend、临时 ledger 和完整自动化测试。

## 2. Shared machine-local execution lease

`agent_runtime/execution_lease.py` 实现固定 machine-local lease domain。生产调用方不能覆盖 lease path 或 backend。

状态改变操作共用同一 exclusive lease：

1. fixed Git status execution；
2. trust binding first commit；
3. trust binding reviewed rotation；
4. open-attempt recovery close commit。

lease file 持久存在，正常流程不 unlink/recreate。Windows backend 使用 non-inheritable handle、拒绝 write/delete sharing 的 open 与 bounded nonblocking exclusive lock；取得锁后核对 handle/path identity、single-link、权限和 project-root overlap。进程退出后 OS 释放 lock，但 persistent lease file 不代表 stale state。

read-only trust/recovery inspection 不取得 exclusive lease，也不创建或修改 lease file，只返回 value-safe lease state。

## 3. Trust inspection and identity-bound rotation

只读命令：

```text
orchestration execution trust inspect [--json]
```

固定状态为：

- `missing`
- `current`
- `drifted`
- `invalid`
- `candidate_unavailable`
- `platform_unavailable`

输出只包含 binding/executable/PATH identity digest、安全 checks/findings、lease state 与 next action；不输出 executable、binding 或 PATH 的绝对位置，也不输出 raw binding。

首次 bind 仍要求 reviewed SHA-256 与 Authenticode publisher thumbprint。`--replace --commit` rotation 还必须提供：

```text
--expected-binding-id sha256:<64hex>
--expected-executable-identity sha256:<64hex>
--expected-path-identity sha256:<64hex>
```

commit 在 shared lease 内重新读取 existing binding、重新发现 candidate，并把当前旧 binding 与新 executable/PATH identity 精确绑定到 operator 审阅值。任一漂移即 blocked。损坏 binding 不支持 `--force`、自动删除或静默覆盖，只返回 manual repair action。

## 4. Bounded locked ledger and open attempts

`agent_runtime/bounded_ledger.py` 为 execution audit 提供同一 bounded descriptor session：

- file 上限 16 MiB；
- physical lines/records 上限 50,000；
- 单行上限 64 KiB；
- JSON nesting depth 上限 32；
- strict UTF-8、duplicate-key/non-finite/oversized-integer rejection；
- regular、non-reparse、single-link 与 path/handle identity checks；
- read projection 使用 shared lock，writer authoritative preflight/append/post-check/rollback 使用 exclusive lock。

任一预算、schema、secret scan、task/event consistency 或 audit-chain validation 失败都 fail closed，不返回 partial state。

CLI surfaces：

```text
orchestration execution recovery list-open [--json]
orchestration execution recovery inspect --attempt-id <attempt-id> [--json]
```

`list-open` 只返回合法、恰有一个 started 且没有 terminal 的 attempt safe summaries，保持 ledger 顺序，最多 128 项。`inspect` 返回 `awaiting_terminal`、`closed_succeeded`、`closed_failed`、`closed_cancelled`、`missing` 或 `invalid`。

对 `awaiting_terminal`：

```text
historical_process_outcome = unknown
automatic_retry_allowed = false
result_release_allowed = false
```

## 5. Fixed outcome-unknown closure

受控写入命令：

```text
orchestration execution recovery close-open \
  --attempt-id <attempt-id> \
  --expected-started-event-id <event-id> \
  --expected-plan-hash sha256:<64hex> \
  [--commit] [--json]
```

无 `--commit` 时只做 preview。commit 在 shared execution lease 内重新打开并完整验证 bounded ledger，要求 attempt 仍只有 matching started、没有 terminal，且 expected started event id 与 plan hash 精确匹配。

唯一可写 terminal 由 dedicated writer 内部固定构造：

```text
event_type = execution_failed
phase = audit
failure_code = execution.recovery_outcome_unknown
guard_status = not_run
```

调用方不能覆盖 event type、phase、failure code、actor、message、evidence 或 ledger path。closure 只关闭 audit lifecycle；它不证明 child 未运行，不恢复历史输出，不释放旧 summary，也不允许复用旧 attempt。后续人工决定再次执行时必须使用新的 attempt，并重新经过完整 trust/repository/plan/audit gate；系统不自动 retry。

## 6. Windows Job accounting release gate

Windows fixed runner 在 direct child wait、reader join 和 cleanup 后、关闭 Job containment 前同步查询 Job accounting。ready release 必须同时满足：

- `job_accounting_passed=true`；
- `job_active_processes=0`；
- `direct_child_reaped=true`；
- `containment_closed=true`；
- total/terminated/active counters 满足平台结构约束。

active 非零时执行既有 terminate/kill/requery 流程。query failure、active 仍非零、direct child 未 reap、reader 未闭合或 containment close failure 均返回 error 并 withheld output。`KILL_ON_JOB_CLOSE` 继续作为最终 containment。

这些 evidence 证明 process containment closure，不证明 filesystem 未写；`filesystem_write_proof` 继续为 false。

## 7. Audit v1/v2 compatibility

历史 `execution-audit/v1` schema 与记录保持不变、可读、不迁移。合法 open v1 attempt 可以由 fixed recovery closure 关闭。

Stage 51 新 fixed execution 的 started 与 terminal 使用 `execution-audit/v2`。v2 terminal 承载 bounded Job evidence；v2 success 必须满足 accounting pass、active zero、direct child reaped 与 containment closed。validator 同时接受完整 v1 chain 和完整 v2 chain，但拒绝 cross-version chain、partial v2 evidence，以及缺少 required Job evidence 的 v2 success。

generic event append/import 继续拒绝 reserved execution lifecycle events。

## 8. CLI contract

Stage 51 增加的 exact public surfaces：

```text
orchestration execution trust inspect [--json]
orchestration execution recovery list-open [--json]
orchestration execution recovery inspect --attempt-id <attempt-id> [--json]
orchestration execution recovery close-open --attempt-id <attempt-id> --expected-started-event-id <event-id> --expected-plan-hash sha256:<64hex> [--commit] [--json]
```

已有 trust rotation surface 增加 reviewed identity binding flags：

```text
orchestration execution trust bind --expected-sha256 <sha256> --expected-publisher-thumbprint <thumbprint> --replace --expected-binding-id sha256:<64hex> --expected-executable-identity sha256:<64hex> --expected-path-identity sha256:<64hex> --commit [--json]
```

没有增加 command/argv/cwd/environment/path/actor override。

## 9. Verification and smoke boundary

Stage 51 production implementation 与本轮文档收口后的 full test suite 均通过；本文件不固化易过期的测试数量。最终文档闭合使用：

```text
python -m agent_runtime.cli docs context --json
python -m agent_runtime.cli doctor
python tools/public_scan.py
bash .githooks/pre-commit
git diff --check
```

本阶段没有设置 `AGENT_RUNTIME_RUN_REAL_GIT_STATUS_SMOKE=1`，没有真实 Git status smoke。Windows lifecycle 与 Job accounting 由 fake backend 覆盖；controlled writes 使用临时 ledger，不修改仓库真实 ledger。

## 10. 明确不做

- 不自动 retry open attempt；
- 不允许 invalid trust binding force overwrite；
- 不支持 POSIX execution；
- 不新增第二个 operation、任意 argv、shell 或 network adapter；
- 不引入 service、DB、queue、daemon、background worker 或 UI；
- 不把 Job accounting 声称为 filesystem write proof；
- 不创建 tag、不 merge；2026-07-25 按用户授权推送到 `origin/main`。

## 11. Stage 51 milestone conclusion

Stage 51 以 commit-level milestone 收口。稳定 semver/tag 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`，本阶段不创建或推送新 tag。

下一候选仅为 **Stage 52 — Fixed Execution Next-decision Design Gate（条件启动）**。Stage 52 没有 implementation authority；候选范围只允许审计 Stage 51 后的 remaining risks、consumer/operator need 与下一项是否值得设计。POSIX、第二个 operation、shell/network/service/UI 或 filesystem proof 均不能由该候选名称自动获得授权。

<!-- stage51-implementation-status: closed -->
<!-- milestone-kind: commit-level-only -->
<!-- stable-tag: v0.17.0-filtered-snapshot-display-host-integration -->
<!-- next-stage: stage52-conditional-design-gate -->
