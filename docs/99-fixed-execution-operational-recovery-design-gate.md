<!-- parents: 98-fixed-git-status-executor-implementation-and-limited-enablement.md, 97-execution-lifecycle-audit-writer-design-and-implementation.md -->
<!-- relates: archive/96-fixed-git-status-executor-design-gate.md, 64-versioning-governance.md -->

# 99 — Fixed Execution Operational Recovery Design Gate

> 状态：**Stage 50 design-only gate 已收口**
> 日期：2026-07-17
> 前置提交：`bf0b990`（Stage 49 fixed Git status executor）
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`
> 本阶段不新增 production CLI、schema、writer、subprocess 或真实 operation

## 1. 目标

Stage 49 已经能在 Windows 上执行唯一 fixed operation，但“执行失败以后如何安全恢复”仍只有内部原语和文字提示。Stage 50 冻结 operator recovery contract，使后续实现能够回答四个问题：

1. trust binding 缺失、有效、漂移或损坏时，operator 应该走哪条固定流程；
2. ledger 中存在 `awaiting_terminal` attempt 时，如何发现、检查并安全关闭；
3. 如何阻止 trust rotation、recovery close 与 fixed execution 并发；
4. 如何把 Windows Job Object 从 lifecycle containment 提升为可查询、可拒绝发布的 no-orphan evidence。

本 gate 的目标是恢复和收紧，不是扩权。任何 recovery action 都不得重新执行未知 attempt，也不得新增 command、argv、cwd、environment、adapter 或 network 能力。

## 2. 当前缺口

Stage 49 已具备：

- `verify_execution_trust()` 的 current binding verification；
- `create_execution_trust_binding(..., replace=True)` 的显式 rotation；
- `inspect_execution_attempt()` 的单 attempt 安全状态投影；
- terminal audit failure 后 `awaiting_terminal` 与 result withheld；
- Windows suspended create、Job assignment、tree terminate/kill、direct child wait 和 `KILL_ON_JOB_CLOSE`。

但仍缺少：

- 公开、只读、固定路径的 trust inspection；
- open attempts 的 bounded discovery；
- operator 可调用但不能伪造任意 reserved event 的 recovery close；
- 跨 execution、rotation、recovery 的 machine-local single-flight coordination；
- Job accounting 的 active-process-zero 查询与 audit evidence；
- 对“started 已写但 child 是否创建未知”的明确恢复语义。

`execution_attempt_started` 只表示 pre-spawn audit 已提交。进程崩溃后，ledger 无法证明 child 是否创建、是否完成或输出为何。因此任何 open attempt 都必须按 **outcome unknown** 处理。

## 3. 方案比较

### 方案 A：发现 open attempt 后自动重跑

拒绝。started 不证明 child 未运行，自动重跑可能把同一 logical request 执行两次，也会绕过新的 plan/trust/repository recheck。

### 方案 B：只增加 read-only inspect

不足。它能描述问题，却无法形成受控、可审计的 terminal closure，也不能阻止 active execution 与 rotation/recovery 并发。

### 方案 C：single-flight lease + safe inspection + unknown-outcome closure + Job accounting

采用。后续实现以一个固定 machine-local execution lease 串行化所有 state-changing execution operations；提供只读 trust/audit recovery projection；只允许一种 fixed recovery terminal；并在新执行结果释放前要求 Job accounting 证明 active process count 为零。

## 4. Machine-local execution lease

future implementation 必须新增固定、调用方不可覆盖的 machine-local lease。它与 trust binding 使用同一安全位置族，但使用独立文件名和独立 identity。

lease contract：

1. 路径由平台 API 解析，不接受 CLI path、environment override、project-local location 或 URL；
2. 全部现存父目录必须 direct、non-reparse，且与 project root 不重叠；
3. lease file 必须 bounded、regular、non-reparse、单链接，并使用当前 actor 的最小权限；
4. 首次创建使用 atomic create；后续只打开同一持久 lease file，正常流程不得 unlink、rename、truncate 或 recreate；
5. Windows 使用不可继承 handle、拒绝 write/delete sharing 的 `CreateFileW` 与 non-blocking/短超时 `LockFileEx` 等价语义；不得只依赖 pathname 或 PID file；
6. state-changing action 必须取得 OS-level exclusive lock，并在取得锁后核对 handle file identity、path file identity、link count 与 pre-open identity 完全一致；
7. lock handle 必须从 action preflight 前持有到 post-check 和 controlled write 完成；持锁期间 path replacement 或 identity drift 一律 error，不能继续或删除新对象；
8. process crash 后由 OS 释放 lock；persistent lease file 本身不是 stale state，不因 crash cleanup 删除；
9. lease、Job 与 trusted executable handle 必须不可继承，fixed child 和其 descendants 不得持有这些 handles；
10. 不把 PID、username、absolute path、lock bytes 或 OS handle 输出到公共结果；
11. lock acquisition 有固定短 timeout，不排队、不 background wait、不自动 retry。

以下 action 共用同一 exclusive lease：

- fixed Git status execution；
- trust binding first commit / replace rotation；
- open-attempt recovery close；
- future invalid-binding recovery（本 gate 暂不开放）。

preview 和 read-only inspect 不取得写 lease，但必须报告 `lease_state=available|active|unavailable`。read-only result 不得因为观察 lease 而创建或修改文件。

## 5. Trust recovery state model

future read-only command candidate：

```text
orchestration execution trust inspect [--json]
```

固定输出 schema candidate：

```text
control-plane/execution-trust-inspection/v1
```

只读取固定 machine-local binding，不接受 path、executable、PATH 或 actor override。状态固定为：

| state | 语义 | recovery action |
|:---|:---|:---|
| `missing` | binding 不存在 | reviewed initial bind |
| `current` | schema、location、binding digest、executable identity 与 sanitized PATH 均匹配 | none |
| `drifted` | binding 结构有效，但 executable 或 PATH identity 已变化 | reviewed replace rotation |
| `invalid` | location、UTF-8、JSON、schema、digest 或 file identity 不可信 | manual binding repair |
| `candidate_unavailable` | 当前没有满足 trust discovery contract 的 Git candidate | repair installation/PATH policy |
| `platform_unavailable` | 平台 backend 不支持 | keep execution unavailable |

安全输出只允许：

- binding id；
- executable identity digest；
- path identity digest；
- state、checks、safe findings、lease state 和 next action。

禁止输出 canonical executable path、approved root、publisher subject、PATH、binding absolute path、review timestamp 或 raw binding。

### 5.1 Rotation

现有 reviewed rotation 继续保留：

```text
orchestration execution trust bind
  --expected-sha256 ...
  --expected-publisher-thumbprint ...
  --expected-binding-id sha256:<64hex>
  --expected-executable-identity sha256:<64hex>
  --expected-path-identity sha256:<64hex>
  --replace --commit
```

implementation 必须增加：

1. commit 前取得 execution lease；
2. lease 内重新读取 existing binding 和 current candidate；
3. `--replace` 必须同时提供 preview/review 时看到的 `--expected-binding-id`，lease 内 existing binding id 不匹配即 blocked；
4. current candidate 必须同时匹配本次 expected digest/thumbprint、`--expected-executable-identity` 与 `--expected-path-identity`；完整 candidate digest 覆盖 approved root、file identity、owner policy、publisher 与 SHA-256，PATH digest 覆盖 canonical sanitized PATH；
5. new candidate 允许与 existing binding 的 executable/PATH identity 不同，因为这正是 reviewed rotation 的目标；但它必须与 operator 刚审阅的 preview 完全一致；
6. preview 后 current candidate、review values 或 existing binding id 再次漂移即 blocked；
7. atomic replace、post-write strict reload 与 rollback 保持 Stage 49 语义；
8. rotation 期间 fixed execution 和 recovery close 均不能启动。

损坏的 binding 不允许使用 `--force`、自动删除或静默覆盖。v1 recovery 只返回 `manual_binding_repair`，要求先在 machine-local trust root 外部完成独立取证/修复，再重新运行 reviewed initial bind。future 若要自动化 invalid-binding recovery，必须另行设计 exact old-file digest、quarantine、retention 和 rollback，不得塞入 Stage 51。

## 6. Open attempt discovery and inspection

future read-only command candidates：

```text
orchestration execution recovery list-open [--json]
orchestration execution recovery inspect --attempt-id <attempt-id> [--json]
```

固定输出 schema candidate：

```text
control-plane/fixed-execution-recovery/v1
```

`list-open` 必须：

1. 任何完整读取前先以 lstat/fstat 验证 regular、non-reparse、single-link identity，并应用固定输入预算：16 MiB file、50,000 physical lines/records、64 KiB per line、JSON nesting depth 32；
2. byte/line/record/depth 任一超限即 fail closed，不解析 remainder、不返回 partial state，并要求独立 ledger archival/compaction design；
3. 在预算内对同一次 locked/snapshot-bound ledger 完成 strict UTF-8、duplicate key、shared schema、dedicated schema、secret scan 和 audit-chain validation；不得先加载完整无界 records 再检查数量；
4. 只返回合法、恰有一个 started 且没有 terminal 的 attempts；
5. 按 started event 在 ledger 中的顺序确定性排序；
6. 最多返回 128 个 safe summaries；超过上限时 fail closed，不返回 partial list；
7. 每项只包含 attempt/start/task/request/plan ids、phase 和 fixed recovery action；
8. 不输出 timestamp、message、append token、path、raw metadata 或 ledger content。

`inspect` 复用同一 validator，并保持现有状态：

```text
awaiting_terminal
closed_succeeded
closed_failed
closed_cancelled
missing
invalid
```

新增 projection 必须显式声明：

```text
historical_process_outcome = unknown   # only for awaiting_terminal
automatic_retry_allowed = false
result_release_allowed = false
```

## 7. Fixed recovery close

future controlled-write command candidate：

```text
orchestration execution recovery close-open \
  --attempt-id <attempt-id> \
  --expected-started-event-id <event-id> \
  --expected-plan-hash sha256:<64hex> \
  --commit \
  [--json]
```

默认无 `--commit` 只做 preview，不写 ledger。该 command 不接受 event type、phase、failure code、message、actor、evidence、file、stdin 或 path override。

固定 closure 为：

```text
event_type = execution_failed
phase = audit
failure_code = execution.recovery_outcome_unknown
guard_status = not_run
```

不得附加 exit code、duration、output digest、stdout/stderr count 或 truncation claim。

commit 顺序：

1. resolve project root 与固定 ledgers；
2. 在取得全局 lease 前只做 lstat/stat 与 16 MiB/line-count cheap bound precheck；超限立即 fail closed；
3. 取得 machine-local exclusive execution lease；
4. 在 lease 内重新核对 ledger identity/size，并以第 6 节同一 byte/line/record/depth 预算完成 streaming/bounded validation；
5. 要求 attempt 恰有一个 matching started、无 terminal；
6. 要求 started event id 与 expected plan hash 精确匹配；
7. 使用 dedicated writer 内部构造固定 terminal event；writer 的 preflight/post-check 也必须消费同一 bounded snapshot contract，不能退回 Stage 48 的无界 loader；
8. 使用 Stage 48 同一 file descriptor、append token、identity/size ownership 与 rollback；
9. post-check 后释放 lease；
10. 返回 `closed_failed`，并明确 historical outcome 仍 unknown。

该 closure 只修复 audit lifecycle，不证明 child 未运行、不证明 repository 未变化、不释放被 withheld 的历史 summary，也不允许复用旧 attempt。operator 后续如需再次执行，必须生成新的 attempt id，重新完成 trust、repository guard、plan hash 和 started audit。

## 8. Windows Job accounting and no-orphan evidence

Stage 49 的 `KILL_ON_JOB_CLOSE` 是 containment control，但 ready result 尚未记录 Job accounting。future Windows runner 必须在 direct child wait、reader join 和 post-run cleanup 后、关闭 Job handle 前查询 Job accounting：

1. 查询必须成功；
2. `ActiveProcesses` 必须为 0；
3. `TotalProcesses`、`TotalTerminatedProcesses` 与 active count 必须满足平台结构约束；
4. active count 非零时先 tree terminate、grace、tree kill、direct-child wait，再重新查询；
5. 查询失败、重新查询仍非零、Job close 失败或 direct child 未 reap 时返回 error；
6. 任一失败都 withheld raw output 和 safe summary；
7. `KILL_ON_JOB_CLOSE` 继续作为最终 containment，不被 accounting query 替代。

Job handle、lease handle 与 trusted executable handle 必须显式不可继承；fixed child 只能继承其标准流所需 handles。否则 parent crash 后 descendant 可能延长 lease 或 containment lifetime，不能形成可恢复语义。

安全 evidence 只允许：

```text
job_accounting_passed
job_total_processes
job_active_processes
job_terminated_processes
direct_child_reaped
containment_closed
```

ready 必须满足 `job_active_processes=0`、`direct_child_reaped=true`、`containment_closed=true`。这些 count 不证明 filesystem read-only；`filesystem_write_proof` 继续为 false。

Windows Job completion-port notification 不作为唯一 no-orphan 证明。implementation 可以使用它辅助等待，但最终 release gate 必须基于同步 accounting query、direct-child reap 和成功关闭 containment handle。

## 9. Audit versioning

历史 `execution-audit/v1` 保持可读，不回写或迁移。open v1 attempt 可以使用第 7 节固定 recovery terminal 关闭，因为现有 v1 schema 已允许 `phase=audit`、fixed failure code 和 `guard_status=not_run`。

Job accounting evidence 不静默塞入 v1。future implementation 必须新增 `execution-audit/v2`：

- started 与 terminal 必须使用相同 writer schema version；
- v2 terminal 增加第 8 节 bounded Job evidence；
- v2 succeeded 必须要求 accounting pass、active zero、direct child reaped 与 containment closed；
- validator 同时接受完整 v1 chain 和完整 v2 chain；
- cross-version started/terminal、partial v2 evidence 或 v2 succeeded 缺少 accounting 均 invalid；
- generic append/import 继续拒绝所有 reserved execution event。

## 10. Failure mapping

| condition | status | release |
|:---|:---|:---|
| trust/audit inspection valid | `pass` | safe state only |
| binding/executable drift | `blocked` | no execution |
| lease active | `blocked` | no state-changing action |
| open attempt preview valid | `pass` | no write |
| fixed recovery terminal committed | `pass` | audit state only; historical result remains withheld |
| missing attempt / expected id mismatch | `needs_input` or `blocked` | no write |
| invalid audit chain / corrupt binding | `validation_failed` | manual review |
| append/rollback/lease/Job query internal failure | `error` | withheld |
| Job active count nonzero after cleanup | `error` | withheld |

所有 finding 必须使用固定 rule id/message，不回显 exception、path、PID、username、PATH、binding bytes、ledger line 或 raw child output。

## 11. Future TDD acceptance matrix

Stage 51 implementation 必须先写 RED tests，至少覆盖：

1. fixed lease path、atomic create、persistent no-unlink、project overlap、reparse、hardlink、path/handle replacement、permission、exclusive contention、non-inheritance 与 crash release；
2. execution、rotation、recovery close 使用同一 lease；
3. trust inspect 的 missing/current/drifted/invalid/candidate/platform states；
4. trust inspect value-safe output 与 no-write；
5. normal reviewed rotation 的 expected old binding id、full new executable/PATH identity 与 lease 内 recheck；
6. invalid binding 无 force overwrite；
7. list-open normal、empty、multiple、closed filtering、invalid chain、16 MiB/50,000 line-record/64 KiB line/depth-32/128-result bounds 与 determinism；
8. inspect awaiting/closed/missing/invalid 与 outcome-unknown projection；
9. close-open preview no-write；
10. close-open expected started id / plan hash stale binding；
11. close-open fixed failed/audit/failure-code shape，拒绝 caller overrides；
12. close-open pre-lease cheap bound、lease 内 bounded snapshot、append/post-check/rollback/concurrent drift；
13. close-open 后旧 summary 仍 withheld，新执行必须新 attempt；
14. Job accounting query pass/active-zero；
15. active nonzero 的 terminate/kill/requery；
16. query failure、close failure、direct child unreaped 与 reader alive；
17. v1/v2 audit compatibility、cross-version rejection 与 v2 required evidence；
18. generic append/import 仍不能伪造 recovery terminal；
19. CLI/contract/doctor/default-output compatibility；
20. full controlled-write regression、public scan、compileall 和 Windows fake-backend coverage。

真实 subprocess smoke 不因 Stage 50 自动运行。Stage 51 若修改 fixed runner，只能在用户明确授权后复用唯一 Git status smoke；不得新增第二个 real command。

## 12. 明确不做

- 不自动重跑 open attempt；
- 不恢复或释放历史 raw stdout/stderr；
- 不新增任意 terminal event writer；
- 不开放 invalid binding force overwrite；
- 不支持 POSIX executor；
- 不支持 linked worktree、submodule 或 alternate object store；
- 不新增第二个 command、任意 argv、shell 或 network adapter；
- 不引入 service、DB、queue、daemon、background worker 或 UI；
- 不声称 Job accounting 是 filesystem write proof；
- 不创建 tag，不 push。

## 13. Stage 50 milestone conclusion

Stage 50 以 design-only 阶段收口。它冻结 operational recovery 的最小安全闭环，但不改变 Stage 49 的 production 行为或 public CLI。

下一阶段候选为 **Stage 51 — Fixed Execution Operational Recovery Implementation（条件启动）**。Stage 51 只能实现本文件冻结的 lease、inspection、fixed closure、Job accounting 和 audit v2；任何 POSIX、第二个 operation、approval-required execution 或 stronger filesystem isolation 必须另开设计并由用户明确授权。

稳定 semver 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`。

<!-- stage50-gate-status: frozen -->
<!-- production-behavior-change: none -->
<!-- next-stage: stage51-conditional-implementation -->
