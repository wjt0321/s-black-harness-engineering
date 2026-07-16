<!-- parents: 95-single-user-real-execution-readiness-gate-and-milestone.md, 58-orchestration-run-controlled-execution-design.md -->
<!-- relates: 48-adapter-runtime-interface.md, 56-orchestration-controlled-write-boundary.md, 64-versioning-governance.md -->

# 96 — Fixed Git Status Executor Design Gate

> 状态：**Stage 46 design-only gate 已收口**
> 日期：2026-07-16
> 前置提交：`49a517b`（Stage 43–45 single-user execution readiness）
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`
> 本阶段不新增 executor、CLI、schema、event type，不执行 Git

## 1. 目标

Stage 46 把 `shell-local/git_status` 从“readiness 中的候选动作”细化为可进入实现评审的 fixed executor contract。设计必须解决：

1. 固定 executable 如何发现、建立信任并绑定到实际 spawn image，避免 project-root/PATH hijack；
2. child process 如何 one-shot spawn、timeout、cancel 和强制收口；
3. stdout/stderr 如何在内存中有界采集并做协议校验；
4. 如何给出诚实的 no-write evidence，而不把 contract controls 伪装成 OS 级写保护；
5. 何时允许释放安全结果，何时必须 withheld；
6. approval 与 execution audit 在第一次真实 spawn 前如何衔接。

本阶段只冻结设计。仓库中仍没有 production executor，也没有任何新入口会调用 `subprocess`。

## 2. 方案比较

### 方案 A：通用 shell / 任意 argv executor

拒绝。它会立即扩大到 command injection、任意 cwd/env、脚本 stdin、网络工具和破坏性命令，与 Stage 43 的唯一候选边界冲突。

### 方案 B：固定 argv + `subprocess.run`

拒绝作为 production 方案。虽然实现简单，但默认 `communicate()` 会先完整收集 child 输出，无法在越过 64 KiB 时立即取消；cancel/process-group/no-orphan 语义也不够清楚。

### 方案 C：可信 executable binding + bounded process-tree runner

采用。PATH 只用于候选发现，不能单独构成执行授权；production runner 必须先完成平台相关的 executable trust binding。它只服务一个 operation：

```text
adapter_id = shell-local
capability = git_status
operation = git_status
requires_approval = false
argv = ["git", "status", "--short", "--branch"]
shell = false
```

runner 不接受 command、argv、cwd、environment、actor 或 executable path 覆盖。future implementation 可以内部依赖注入 fake runner 以测试，但 production path 的 argv 所有权必须在模块内。

## 3. 单用户与授权边界

- actor 固定为 `local-operator`；
- mode 固定为 `single_user_local`；
- 不实现 account、role、tenant、login、session、token、ACL；
- 保留 future `actor_context` 名称，但 v1 executor 不接受外部 actor 值；
- `shell-local` registry 必须保持 enabled、kind=`shell`、risk=`local`、capability 包含 `git_status`、`requires_approval=false`；
- 任一 registry drift 都在 spawn 前 blocked；
- 如果 future candidate 改成 `requires_approval=true`，必须先完成 approval → canonical plan binding，不能复用本 gate。

本 operation 不要求 approval，因此 approval binding 缺口不阻断它的设计；但它仍不能绕过 execution audit。

## 4. Project root 与 repository preflight

future executor 只接受 CLI 已解析的 project root，不新增任意 repository path 参数。spawn 前必须：

1. `Path.resolve()` 成功；
2. root 是目录；
3. root 内存在 `pyproject.toml` 与 `agent_runtime/`；
4. root 内存在直接 `.git/` 目录；
5. v1 不接受指向外部 common directory 的 `.git` 文件/worktree indirection；
6. `.git/commondir` 不得存在，避免 direct `.git/` 内再次重定向 common directory；
7. cwd 精确为 resolved project root，不向父目录搜索 repository；
8. 不跟随用户传入 symlink repository selector。

限制 `.git` 为目录会暂时排除 Git linked worktree。这是有意的 v1 安全收缩；未来若要支持 worktree，必须单独设计 gitdir/common-dir containment。

### 4.1 Git metadata 统一 containment

任何 config scan、secret scan、hash 或目录 fingerprint 之前，必须先做 **lstat-first、never-follow** 的 metadata containment。至少覆盖：

```text
.git/
.git/index
.git/HEAD
.git/packed-refs
.git/refs/
.git/objects/
.git/objects/pack/
.git/logs/HEAD
.git/config
.git/config.worktree
.git/info/exclude
.git/info/attributes
```

统一规则：

1. 从 resolved project root 到目标的每一级父链都必须 root-contained；
2. `.git`、`refs`、`objects`、`objects/pack` 等目录必须是真实目录，拒绝 symlink、junction、mount escape 和任何 reparse point；
3. `index`、`HEAD`、`packed-refs`、config、info、ref、loose-object、pack/index 等文件必须是 regular file，拒绝 symlink/reparse point，v1 要求 link count=1；
4. `refs/`、`objects/` 与 `objects/pack/` 使用 bounded `lstat` traversal，逐项拒绝 symlink/reparse point、非预期类型与 root escape；不得先 `resolve()`、open、read 或 hash 再判断；
5. containment traversal 必须有 entry/depth/path-byte 上限；无法完整证明时 blocked，不做部分放行；
6. fingerprint 只能在 containment pass 后读取已验证 regular file；finding 只包含固定 rule id、project-relative logical location 与类型提示，不输出外部 target；
7. post-run 使用同一 lstat-first manifest 复核；类型、file identity、link count、entry set 或 containment 任一漂移都 withheld。

因此 fingerprint 中的 `type` 不是“记录后继续”的信息，而是 precondition：类型不符合即停止，绝不能跟随目标。对使用 local clone hardlink object store、junction object store 或外部 refs 的仓库，v1 会保守 blocked；未来支持需要独立设计。

## 5. Fixed executable discovery、trust anchor 与 spawn binding

executable 名称永久固定为 `git`，不接受用户路径。discovery contract：

1. 只从当前进程的 `PATH` 构造候选目录；
2. 删除空项、`.`、相对路径、不存在目录、非目录项和重复项；
3. 删除 project root 及其后代目录，避免仓库内 `git`/`git.exe` 劫持；
4. 每个目录必须 `resolve(strict=True)`，拒绝 symlink/reparse-point directory chain；
5. Windows 使用规范化 drive/UNC 语义和 case-insensitive 去重；POSIX 使用 case-sensitive 去重；
6. 仅在剩余 canonical absolute directories 中解析；
7. candidate 必须 `resolve(strict=True)`、是 regular file、不是 symlink，且 link count / file identity 可读取；
8. Windows 只接受 basename `git.exe`；POSIX 只接受 basename `git` 且具有 executable bit；
9. 不接受 `.cmd`、`.bat`、PowerShell script、alias、function 或 shell builtin；
10. resolved absolute path 只在进程内使用，不写入 ledger、不进入 JSON/human output；
11. executable unavailable 返回 fixed safe finding，不回显 PATH 或候选路径；
12. 不通过执行 `git --version` 做 probe；第一次允许的 child argv 只能是 frozen status argv。

PATH discovery 只回答“候选在哪里”，不能回答“它是否可信”。production enablement 还必须匹配一个**调用方不可覆盖、非 project-local、operator-reviewed 的 trust binding**，至少绑定：

- platform 与 canonical executable identity；
- expected SHA-256；
- expected file identity（Windows volume/file id；POSIX device/inode）；
- approved installation root；
- executable 与全部父目录的 owner/ACL/mode policy；
- Windows Authenticode publisher allowlist，或 POSIX root-owned 且 group/world 不可写的等价 policy；
- trust binding 自身的 schema version、content digest 与 reviewer provenance。

任一父目录对当前普通 actor 可写、任一 symlink/reparse-point chain、digest/file identity/publisher/owner drift，均在 spawn 前 blocked。不能使用仅由 basename、regular-file 属性或“本次算出的 digest”组成的自签名信任。

preflight 完成后必须立即再次打开并核对 executable identity；spawn 后还必须通过平台能力核对实际 process image identity。Windows 若不能在受信任目录约束下完成 image/publisher/file-id 绑定，POSIX 若不能核对 `/proc`/平台等价 image identity，均不得返回 `ready`。无法消除的 hash-to-spawn TOCTOU 是 **Stage 49 硬阻塞项**，不能用“immutable path/value”宣称已经解决。

canonical executable identity、sanitized PATH identity、trust-binding identity 与 canonical execution plan 必须共同进入内部 plan hash 和安全 digest；任何一步漂移都不得继续或释放结果。

## 6. Minimal environment 与 repository config containment

child 不继承完整环境。允许提供：

```text
PATH=<resolver 使用的 canonical sanitized PATH>
SYSTEMROOT
WINDIR
```

future executor 额外设置固定值：

```text
GIT_OPTIONAL_LOCKS=0
GIT_TERMINAL_PROMPT=0
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=<platform null device>
```

并通过 Git 的 `GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_n` / `GIT_CONFIG_VALUE_n` 固定覆盖：

```text
core.fsmonitor=false
core.untrackedCache=false
maintenance.auto=false
color.status=false
status.showUntrackedFiles=all
core.quotePath=true
```

child `PATH` 必须与 discovery 使用的目录列表逐项一致，并使用平台 `pathsep` 做确定性序列化；禁止复制父进程原始 PATH。PATH identity digest 必须同时进入 executable evidence、plan 与 audit metadata。Windows 大小写去重、drive/UNC 归一化和 POSIX case-sensitive 规则必须与第 5 节相同。

这些控制用于抑制 optional lock、外部 fsmonitor、自动维护、颜色和用户级配置漂移。它们不能被调用方覆盖，也不能输出环境值。

Git 仍会读取 repository-local config。spawn 前必须用 value-safe scanner 检查 `.git/config` 和存在时的 `.git/config.worktree`：

- config 文件必须是 root-contained regular file，拒绝 symlink/reparse point、hardlink（link count 不为 1）、超过 256 KiB、NUL、非法 UTF-8、continuation/multiline 与 scanner 不支持的语法；
- section/key 按 Git 的 ASCII case-insensitive 语义 canonicalize；危险 key 重复出现时，无论最终覆盖顺序如何都 blocked；
- 完整拒绝 `[include]` / `[includeIf]` 及 `include.path` / `includeIf.*` indirection；
- 完整拒绝 `alias.*`、`pager.*`、`credential.*`、`filter.*.clean`、`filter.*.smudge`、`filter.*.process`、`diff.external`、`diff.*.command`、`merge.*.driver`、`interactive.diffFilter`；
- 完整拒绝 `core.fsmonitor`、`core.hooksPath`、`core.sshCommand`、`core.pager`、`core.alternateRefsCommand`；
- 完整拒绝可把读取范围带出 project root 的 `core.worktree`、`core.excludesFile`、`core.attributesFile`；不尝试解析或信任其 value；
- secret 命中只返回 rule id、文件内行号与固定提示，不回显 value；
- scanner 失败或文件在 scan 后漂移，一律 blocked；
- 不读取 system/global credential store、`.env`、keyring 或任意 credential file。

repository metadata 还必须满足：

- `.git/objects/info/alternates` 与 `.git/objects/info/http-alternates` 不得存在，避免 object read 逃逸到外部目录或 URL；
- `.git/info/exclude` 与 `.git/info/attributes` 如存在，必须是 root-contained、非 symlink/reparse-point、link count=1、bounded regular file，并纳入 pre/post fingerprint；
- 任何 config path value、绝对路径、`..` 逃逸、symlink/reparse-point 或敏感文件指向都使用 fixed value-safe finding 阻断，不能回显原路径/value；
- v1 必须拒绝 submodule surface：存在 `.gitmodules`、`.git/modules/`，或 bounded index scan 发现 mode `160000` gitlink 时 blocked。

这些规则是有限 allowlist contract；future Git 版本若新增 status 可消费的 external path/helper config，而 scanner 尚未认识，必须 conservative blocked，不能默认放行。未来若要支持 alternate object store、custom excludes/attributes、submodule 或 worktree，必须另开设计。

## 7. Spawn、process-tree containment、bounded I/O 与 cancel

future runner 使用 `subprocess.Popen` 配合平台 process-tree containment，固定：

- `shell=False`；
- argv array 为 resolved executable + `status --short --branch`；
- cwd 为 project root；
- stdin=`DEVNULL`；
- stdout/stderr=`PIPE`，binary mode；
- default timeout 10 秒，hard max 30 秒；
- retry=0；
- background/session=false；
- child stdout/stderr 各 64 KiB hard limit。

仅回收直接 child 不足以宣称 no-orphan。平台 contract：

- POSIX：child 必须在独立 session/process group 中启动；cancel/timeout/overflow 对整个 process group 先 `SIGTERM`，grace 后 `SIGKILL`，最后 wait direct child；
- Windows：必须使用带 `KILL_ON_JOB_CLOSE` 的 Job Object，并通过 suspended-create → assign-to-job → resume 消除 assign race；不能只对直接 PID 调用 terminate；
- process-tree containment 初始化失败时不得运行 operation；
- Stage 49 若不能可靠实现对应平台机制，该平台保持 unavailable。

runner 必须并发读取 stdout/stderr，不能在 child 退出后才检查大小。任一 stream 即将超过 hard limit时：

1. 停止继续保留 raw bytes；
2. terminate 整个受控 process tree；
3. 在固定 1 秒 grace period 后仍有存活成员则 kill 整个受控 process tree；
4. 完成 direct-child wait/reap，并关闭/验证 process-tree containment；
5. 返回 fixed output-too-large finding；
6. 不释放 partial stdout/stderr。

timeout、`KeyboardInterrupt` 或 future internal cancel token 使用同一 tree terminate → grace → tree kill → wait 收口路径。不能验证 descendants 已被 containment 收口时返回 `error`，不得宣称 no-orphan。v1 不自动 retry。

## 8. Output validation 与安全投影

raw stdout/stderr 仅在当前进程内短暂存在，不写文件、ledger、draft、cache 或 report。

成功候选必须满足：

1. child exit code = 0；
2. stderr 为空；
3. stdout 严格 UTF-8；
4. 总量不超过 64 KiB；
5. 只接受 LF，拒绝 CR/CRLF；输出必须恰好以一个 LF 结束，禁止空行；
6. 第一行是唯一 branch header，并符合下述有限 grammar；
7. 后续每行必须符合下述 porcelain-v1 status grammar；
8. 不认识的 header、XY pair、重复 branch metadata 或额外 token 一律 protocol validation failure；
9. rename/copy/conflict/submodule 状态只按冻结规则分类，不解析或输出 filename；
10. 单行不超过 4096 bytes；
11. 行数不超过 2000；
12. 不包含 NUL；
13. parser 不解析或执行 filename 内容。

上述边界与 grammar 条件同时生效。有限 branch-header grammar：

```text
## HEAD (no branch)
## No commits yet on <ref-token>
## Initial commit on <ref-token>
## <ref-token>
## <ref-token>...<upstream-token>
## <ref-token>...<upstream-token> [ahead N]
## <ref-token>...<upstream-token> [behind N]
## <ref-token>...<upstream-token> [ahead N, behind M]
```

`ref-token` / `upstream-token` 必须为非空、无 ASCII control/space 的 UTF-8 token；`N/M` 为 canonical 十进制正整数，最大 `2^31-1`，不得有前导零或重复字段。header 中的 branch/upstream token 只用于 grammar 校验，随后立即丢弃。

有限 status grammar 为 `XY SP opaque-path`。`opaque-path` 必须非空、无 NUL/control；parser 不拆分 `old -> new`，rename/copy 仍计一个 entry。允许：

- untracked：`??`；
- conflict：`DD`、`AU`、`UD`、`UA`、`DU`、`AA`、`UU`；
- ordinary：`X ∈ {SP,M,T,A,D,R,C}`、`Y ∈ {SP,M,T,D}`，但 `SP/SP` 禁止，且 conflict pair 不重复归入 ordinary；
- `!!` 与任何其他 pair 均拒绝；
- v1 已在 preflight 拒绝 submodule，因此不得出现 submodule 特有状态。

计数映射唯一固定为：

1. `entry_count` 每个 status record +1；
2. `??` 只增加 `untracked`；
3. conflict pair 只增加 `conflicted`，不重复增加 staged/unstaged；
4. ordinary 中 `X != SP` 增加 `staged`，`Y != SP` 增加 `unstaged`；
5. rename/copy record 按其 XY 映射，只计一个 entry；
6. detached 仅由 `HEAD (no branch)` 得出；ahead/behind 仅由有限 header suffix 得出。

exit code 为 0 但 stderr 非空、未知 XY/header、line-ending/final-newline 不符，统一为 `validation_failed` / exit 5 / `execution.output_protocol_invalid`。child nonzero 统一为 `blocked` / exit 2 / `execution.child_nonzero`；stderr 始终 withheld。

future result 默认只允许安全摘要：

- `dirty`；
- `entry_count`；
- staged / unstaged / untracked / conflicted counts；
- detached / ahead / behind flags；
- stdout/stderr byte counts；
- stdout SHA-256；
- truncation flags（成功必须为 false）；
- executable identity digest；
- no-write evidence 状态。

禁止默认输出：

- raw stdout/stderr；
- file paths；
- branch name；
- resolved executable path；
- absolute cwd；
- PATH/environment；
- `.git/config` value；
- secret scan match；
- 完整 argv 字符串。

如 future consumer 确实需要路径列表，必须另开显式 reveal contract；不得静默扩大本安全投影。

## 9. No-write evidence：控制、证据与非证明

本 gate 区分三层语义：

### A. Contract controls（必须）

- exact read-oriented argv；
- `GIT_OPTIONAL_LOCKS=0`；
- fsmonitor/untracked-cache/maintenance disabled；
- no stdin、no retry、no remote/network operation；
- exact local-config denylist 与 submodule preflight；
- trusted executable binding 和 bounded process-tree containment。

### B. Bounded guard evidence（必须）

spawn 前后对以下 critical Git paths 做 bounded fingerprint：

- `.git/index`
- `.git/config`
- `.git/config.worktree`（如存在）
- `.git/info/exclude`（如存在）
- `.git/info/attributes`（如存在）
- `.git/HEAD`
- `.git/packed-refs`
- `.git/refs/`
- `.git/objects/`
- `.git/objects/pack/`
- `.git/logs/HEAD`
- known lock files（必须前后均不存在）

fingerprint 必须复用第 4.1 节已通过的 lstat manifest，不能自行 follow/resolve target。它只保留 project-relative identity、type、file identity、link count、size、mtime_ns 和 bounded SHA-256；目录枚举必须有 entry/depth/path-byte/content-byte 上限。任何 drift、lock artifact、无法完成 containment/fingerprint 或 scan-to-spawn drift 都 blocked，result withheld。

### C. OS-enforced filesystem proof（当前不存在）

Stage 46 不引入 container、sandbox、read-only mount 或 filesystem virtualization。Windows Job Object / POSIX process group 只用于 process-tree lifecycle containment，不提供 filesystem read-only proof。因此 future result 只能声明：

```text
no_write_contract = true
guard_evidence_passed = true|false
filesystem_write_proof = false
```

不得把 A+B 表述为“绝对证明 child 没有写任何 project file”。这是当前距离强隔离生产执行仍存在的明确差距。

## 10. Execution audit release gate 与 writer 来源隔离

第一次真实 spawn 前，execution lifecycle controlled writer 必须存在。固定顺序：

1. 完成 root/registry/profile/config/executable/no-write preflight；
2. 生成 canonical execution plan hash；
3. 受控追加 `execution_attempt_started`；写入失败则不 spawn；
4. 最后一次 executable/config/guard identity check；
5. 执行 fixed child；若 spawn 前漂移或 `Popen` 失败，仍写唯一 terminal failure；
6. 完成 output validation 与 post-run guard evidence；
7. 受控追加唯一 terminal event；
8. terminal event 和 post-check 成功后才释放安全 result。

`execution_attempt_started` 的语义固定为“执行尝试已通过门禁并受控提交，child 尚可能未成功创建”，不得被 reader 解释为“进程已经运行”。是否成功 spawn 必须由 terminal event 的 `phase` / outcome 表达。

terminal event：

```text
execution_succeeded
execution_failed
execution_cancelled
```

每次 append 使用现有 byte-size rollback 语义。已成功写入的 `execution_attempt_started` 不因后续 terminal append 失败而删除；删除它会破坏审计事实。terminal writer 失败时 result withheld，返回 audit-incomplete error，后续通过恢复流程处理。

event metadata 只允许 actor、task/request/plan/adapter/operation identity、exit code、duration bucket、output digest/count、guard status 和 truncation flags；禁止 raw output、path、branch、environment、config value。

execution lifecycle event 是 reserved event type，必须满足：

- 只能由专用 execution audit writer 写入；
- 现有通用 `runtime event append/import --commit` 必须在 schema 校验之外显式拒绝全部 reserved execution event type；
- writer 必须写入固定 `writer_origin`、schema/version、attempt id、canonical plan hash 与前序 event identity；
- started 对同一 attempt 唯一；terminal 对同一 attempt 唯一；terminal 必须引用已存在且 plan hash 一致的 started；
- 不能通过只扩展共享 `tasks/event.schema.json` enum 来开放 event；
- Stage 47 必须冻结独立 schema/provenance discriminator 与通用入口负向门禁；Stage 48 必须先用 controlled-write RED tests 证明不能伪造。

## 11. 状态与 failure mapping

| 条件 | future status | exit | content |
|:---|:---|:---:|:---|
| 全部 pre/post gate、child、audit 通过 | `ready` | 0 | safe summary |
| registry/config/trust/guard drift、nonzero child、output too large、cancel | `blocked` | 2 | withheld |
| root/profile/protocol/UTF-8/porcelain grammar 非法、exit 0 但 stderr 非空 | `validation_failed` | 5 | withheld |
| executable binding/spawn/timeout/process-tree containment/audit writer 内部失败 | `error` | 1 | withheld |

所有 failure finding 使用固定 rule id/message，不复制 exception、stderr、PATH、config、filename 或 child output。

## 12. Future result contract 候选

Stage 46 不新增 schema；future implementation 必须使用新版本，例如：

```text
control-plane/fixed-git-status-execution/v1
```

候选顶层字段：

```text
status
schema_version
executor
source
lifecycle
scope
plan
process
summary
audit
no_write_evidence
findings
guarantees
next_action
```

任何 `ready` result 必须同时满足 lifecycle closed、audit complete、guard evidence pass、raw output withheld。`blocked` / `validation_failed` / `error` 的 summary 必须为 null 或 withheld。

## 13. Future TDD 验收矩阵

进入 implementation 前必须先写 RED tests，至少覆盖：

1. no CLI / module 时预期 RED；
2. exact argv ownership，拒绝 command/argv/path/env override；
3. PATH 空项、relative/nonexistent/symlink entry、project-local fake git、`.cmd/.bat` hijack；
4. sanitized PATH deterministic serialization、child PATH exact equality 与 digest binding；
5. fake external `git.exe`/`git`、writable parent、publisher/owner/digest/file-id drift 和 hash-to-spawn TOCTOU；
6. Windows trusted image/Job Object、POSIX trusted image/process group；不支持的平台保持 unavailable；
7. root 与 `.git` directory boundary；
8. `.git/index` / `HEAD` / `packed-refs` symlink、reparse point、hardlink blocking；
9. `.git/refs` 目录及内部 ref entry 的 symlink/junction/root-escape blocking；
10. `.git/objects` / `objects/pack` 的 junction/reparse/external symlink/hardlink blocking；
11. containment failure 只做 lstat + fixed finding，不读取/hash 外部 target；
12. bounded metadata traversal 的 entry/depth/path-byte 上限和 determinism；
13. config file type/size/grammar、exact command/path-bearing key denylist、duplicate key 与 secret-safe blocking；
14. `core.worktree` / `core.excludesFile` / `core.attributesFile` 的绝对路径、`..`、symlink 与敏感文件负向用例；
15. `.git/commondir`、object alternates、`.gitmodules` / `.git/modules` / index gitlink blocking；
16. exact minimal environment；
17. stdout/stderr 64 KiB hard stop，不保留 partial output；
18. timeout/cancel 对 process tree terminate → kill → wait；
19. exit/status/rule-id mapping；
20. LF/final-newline、有限 branch header、完整 XY allowlist、rename/copy/conflict/count mapping；
21. safe summary determinism，不含 path/branch/raw output/env；
22. critical-path fingerprint drift 和 lock artifact；
23. pre-spawn audit failure prevents runner invocation；
24. spawn failure 形成 terminal failure，terminal audit failure withholds result but preserves attempt-started fact；
25. 通用 event append/import 无法伪造 reserved execution events；
26. no retry/no remote/network operation/no background；
27. injected fake runner 全覆盖；
28. 只有用户明确授权后才运行一个真实 local Git integration smoke。

涉及 event schema/writer 时必须额外运行 controlled-write regression。

## 14. 明确不做

- 不新增 production subprocess 模块；
- 不新增 `orchestration execution git-status` CLI；
- 不执行 `git status`、`git --version` 或任何 external command；
- 不支持任意 shell/argv/cwd/env；
- 不支持 linked worktree；
- 不输出 file paths/branch name/raw stdout/stderr；
- 不访问网络、remote、credential helper、keyring；
- 不实现 multi-user auth；
- 不引入 service、DB、queue、background worker、UI；
- 不创建 tag，不 push。

## 15. Stage 46 结论与后续顺序

Stage 46 设计门通过，但真实 execution 仍 unavailable。合理后续顺序：

1. **Stage 47 — Execution Lifecycle Audit Writer Design Gate**：先冻结 reserved event schema、专用 writer provenance、通用 append/import 拒绝、append/rollback、attempt-started/terminal recovery；
2. **Stage 48 — Execution Lifecycle Audit Writer Implementation**：按 controlled-write TDD 落地，并证明 execution audit 不能由通用入口伪造；
3. **Stage 49 — Fixed Git Status Executor Implementation and Limited Enablement**：只有 executable trust/image binding、sanitized child PATH、process-tree containment、有限 porcelain grammar 全部可实现，且用户再次明确授权真实 subprocess 后才允许启动。

approval plan binding 对 `requires_approval=false` 的 `git_status` 不构成 Stage 49 前置，但仍是任何 future approval-required adapter 的硬门禁。

<!-- gate-status: passed-stage46-design-only -->
<!-- execution-status: unavailable -->
