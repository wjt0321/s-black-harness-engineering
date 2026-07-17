<!-- parents: 96-fixed-git-status-executor-design-gate.md, 97-execution-lifecycle-audit-writer-design-and-implementation.md -->
<!-- relates: archive/95-single-user-real-execution-readiness-gate-and-milestone.md, 58-orchestration-run-controlled-execution-design.md -->

# 98 — Fixed Git Status Executor Implementation and Limited Enablement

> 状态：**Stage 49 Windows limited enablement 已按 TDD 实现并收口**
> 日期：2026-07-17
> 前置提交：`1c33dbd`（Stage 47–48 execution audit writer）
> 稳定版本：`v0.17.0-filtered-snapshot-display-host-integration`
> 本阶段只允许一个真实 operation：`git status --short --branch`

## 1. 里程碑结论

Stage 49 已把 Stage 46 的 fixed executor contract 和 Stage 47–48 audit writer 接成第一条真实、有限、本地执行链：

```text
machine-local reviewed trust binding
  -> root / registry / repository guard
  -> canonical plan hash
  -> execution_attempt_started controlled append
  -> final trust + guard recheck
  -> Windows suspended process + Job Object
  -> bounded stdout/stderr
  -> finite porcelain-v1 parser
  -> post-run repository guard
  -> terminal execution audit
  -> safe summary release
```

本能力不是通用 shell，也不接受 caller-supplied command、argv、cwd、environment、executable path 或 actor。唯一固定 identity 为：

```text
actor = local-operator
adapter_id = shell-local
capability = git_status
operation = git_status
argv = ["git", "status", "--short", "--branch"]
shell = false
```

## 2. Public CLI

### 2.1 Machine-local trust binding

```bash
python -m agent_runtime.cli orchestration execution trust bind \
  --expected-sha256 <reviewed-lowercase-sha256> \
  --expected-publisher-thumbprint <reviewed-uppercase-thumbprint> \
  --json
```

默认只做 preview，不写文件。显式提交：

```bash
python -m agent_runtime.cli orchestration execution trust bind \
  --expected-sha256 <reviewed-lowercase-sha256> \
  --expected-publisher-thumbprint <reviewed-uppercase-thumbprint> \
  --commit \
  --json
```

已有 binding 默认拒绝覆盖。Git 升级或 PATH identity 变化后，只有显式 `--replace --commit` 才允许 rotation；旧 binding 必须先通过 strict validation。

binding 固定存储在 machine-local、非 project-local 位置，CLI 不接受 binding path 参数。Windows 使用 Known Folder API 解析 Local AppData，不信任 caller-supplied `LOCALAPPDATA`。binding 包含 canonical executable path、approved installation root、SHA-256、volume/file identity、Authenticode signer certificate thumbprint、sanitized PATH identity、review timestamp 与 reviewer provenance；公共结果只投影 binding/executable/PATH digest，不输出绝对路径。

binding path 的全部现存父目录必须是 direct non-reparse directory，且必须与 project root 不重叠。该 binding 是单用户 local-operator trust anchor，不声称抵抗同一 OS 用户已被攻陷后的任意篡改；同一用户的合法更新必须通过显式 review/rotation workflow，项目内容不能充当 binding。

### 2.2 Fixed Git status

```bash
python -m agent_runtime.cli orchestration execution git-status \
  --task-id <existing-task-id> \
  --request-id <bounded-request-id> \
  --commit \
  --json
```

可选 `--expected-plan-hash sha256:<64hex>` 用于 operator-reviewed plan binding；可选 `--timeout-seconds 1..30`，默认 10 秒。缺少 `--commit` 时不写 audit、不启动 subprocess，固定返回 blocked。

## 3. Executable trust 与 TOCTOU 收口

Windows production trust backend：

1. 从当前 PATH 构造候选目录，但删除空项、相对项、不存在目录、project-local 目录、symlink/reparse chain、重复项和当前 actor 可写目录；
2. 只接受第一个固定 basename `git.exe`；
3. executable、approved root 与全部父目录必须是 direct non-reparse path，且当前 actor 不能取得 write/delete access；
4. 通过 `CreateFileW` 以 read-only、仅 share-read 打开 executable，禁止 write/delete replacement，并保持 handle 到 process image validation 完成；
5. 通过 handle 计算 SHA-256 和 volume/file identity；
6. `WinVerifyTrust` 使用 no-UI、cache-only 模式验证 Authenticode；
7. `CryptQueryObject` / signer certificate store 提取唯一 signer certificate thumbprint；
8. 当前 executable identity、reviewed binding、sanitized PATH identity 任一漂移即 blocked；
9. spawn 后、resume 前通过 process handle 查询 actual image path，并重新核对 file identity 和 digest。

因此 production 不是“PATH 找到 git 就执行”，也不是“本次自算 digest 后自信任”。operator-reviewed binding 是独立、持久、显式的 trust anchor；open handle 与 suspended image check 用于闭合 hash-to-spawn replacement window。

## 4. Repository guard

`agent_runtime/git_repository_guard.py` 在任何 Git spawn 前后构建 bounded lstat-first manifest，并把 no-follow/read-only/share-read handles 持有到 child 与 post-run guard 完成：

- root 必须是 direct directory，并包含 direct `pyproject.toml` 与 `agent_runtime/`；
- `.git` 必须是 direct directory，不接受 linked worktree `.git` file；
- critical file 的每一级父目录都必须 direct、non-symlink、non-reparse；
- metadata file 必须 regular、link count=1；
- bounded traversal 覆盖 refs、objects、pack、config、HEAD、index、packed refs、info 与 logs；
- `.git/commondir`、object alternates、submodule surface、gitlink、known lock、symlink/reparse/hardlink、entry/depth/path/content bound 超限均 blocked；
- repository config 使用有限 scanner，拒绝 include、credential、alias、pager、filter/diff/merge command、fsmonitor、hooks、worktree、external excludes/attributes 等 surface；
- pre-spawn recheck 与 post-run guard 必须和初始 manifest 完全一致。

guard finding 只返回固定 rule id/message，不输出 filename、target 或 config value。

## 5. Windows process-tree runner

`agent_runtime/fixed_process_runner.py` 使用：

- `subprocess.Popen`；
- `CREATE_SUSPENDED`；
- `KILL_ON_JOB_CLOSE` Job Object；
- assign-to-job 后 actual image validation；
- `NtResumeProcess`；
- stdin closed、stdout/stderr binary pipes；
- 每流 64 KiB hard limit；
- 默认 10 秒、最大 30 秒；
- no retry、no background。

stdout/stderr 由独立 reader thread 并发读取。overflow 即使发生在 direct child 已退出之后，也会在 reader join 后再次检查并 withheld。timeout、overflow、cancel 和 image mismatch 使用 tree terminate、grace、tree kill、direct-child wait；Job Object close 是最终 no-orphan containment。

POSIX 本阶段明确 unavailable。没有实现符合 Stage 46 image identity 与 process-group 全合同的 POSIX backend，因此不会退化成普通 `subprocess.run` 或 direct-child-only cleanup。

## 6. Finite porcelain parser

`agent_runtime/git_status_porcelain.py` 只接受 Stage 46 冻结的：

- 八类 branch header；
- canonical ahead/behind 正整数；
- 完整 porcelain-v1 XY allowlist；
- conflict / ordinary / untracked 唯一计数映射；
- LF-only、exact final newline、UTF-8、NUL/control、line count、line byte 与 stream byte bounds。

parser 从不解析或投影 filename。branch/upstream token 只做 grammar validation 后丢弃。ready summary 只包含：

- dirty；
- entry/staged/unstaged/untracked/conflicted counts；
- detached/ahead/behind；
- stdout/stderr byte counts；
- stdout SHA-256；
- truncation flags。

raw stdout/stderr、branch、path、absolute cwd、resolved executable、PATH/environment 与 config value 始终 withheld。

## 7. Audit release gate

`agent_runtime/orchestration_git_status_execution.py` 固定顺序：

1. direct root guard；
2. adapter registry alignment；
3. first executable trust；
4. canonical plan hash；
5. `execution_attempt_started` commit；
6. final trust + repository guard recheck；
7. fixed runner；
8. post-run repository guard，即使 child timeout/nonzero/output failure 也必须运行；
9. output protocol validation；
10. exactly one terminal audit；
11. terminal commit 成功后才释放 ready summary。

started append 失败时 runner invocation count 必须为 0。terminal append 失败时保留 started，返回 `audit_incomplete=true`，summary withheld。通用 `runtime event append/import` 仍不能伪造 reserved lifecycle event。

## 8. No-write 语义

ready 结果固定声明：

```text
no_write_contract = true
guard_evidence_passed = true
filesystem_write_proof = false
```

这表示 exact read-oriented argv、Git lock/config controls、trusted executable、bounded process tree 与 pre/post critical metadata fingerprint 均通过；不表示存在 container、read-only mount、filesystem virtualization 或 OS-enforced 全项目写保护。

## 9. Real integration smoke

2026-07-17 已在 Windows 上完成一次显式授权 smoke：

- 使用 reviewed system Git SHA-256 与 Authenticode signer thumbprint 创建并 rotation machine-local binding；
- sanitized child PATH 删除 actor-writable directories；
- 在 pytest `tmp_path` 内构造 direct `.git/` 最小仓库、临时 task/event ledger 与所需 schema/policy；
- 通过真实 CLI `orchestration execution git-status --commit --json` 启动唯一 fixed subprocess；
- result=`ready` / exit 0；
- audit ledger 从 created 增加 started + succeeded，共三行；
- post-run guard pass；
- output 不包含临时 root、filename、branch ref、PATH 或 raw status；
- smoke 结束后临时目录由 pytest 清理，项目真实 ledger 未修改。

smoke 测试默认 skip，只有显式设置：

```text
AGENT_RUNTIME_RUN_REAL_GIT_STATUS_SMOKE=1
```

才运行，避免 CI 或未 provision binding 的机器意外启动 subprocess。

## 10. Compatibility

- Stage 44 `control-plane/single-user-execution-readiness/v1` 永久保持历史 10 pass / 3 blocked，不被回改成 runtime detector；
- 新 capability 通过独立 `control-plane/fixed-git-status-execution/v1` 与 contract manifest entries 暴露；
- generic `external_execution_service_stack` 继续 unavailable；
- existing run commit 仍只写 envelope/lifecycle，不执行 adapter；
- no network、credential、`.env`、keyring、service、DB、UI 或 background worker；
- 不支持 linked worktree、submodule、alternate object store、custom external excludes/attributes；
- 不创建 tag，不 push。

## 11. Verification

提交前必须通过：

```bash
python -m pytest tests -q
python -m agent_runtime.cli doctor
python tools/public_scan.py
python -m pytest tests/test_controlled_write_regression.py -q
python -m compileall -q agent_runtime tests tools
python -m agent_runtime.cli docs context --json
git diff --check
bash .githooks/pre-commit
```

真实 smoke 单独运行：

```bash
AGENT_RUNTIME_RUN_REAL_GIT_STATUS_SMOKE=1 \
python -m pytest tests/test_stage49_real_git_status_smoke.py -q
```

提交前独立安全复审曾发现 repository pathname reopen/无界读取、Job assignment 前清理、Windows access-right fail-open、terminal state、binding location 与默认 real-writer regression 六项 Important。实现已补齐 locked/no-follow handle lifetime、pre-read bounds、direct child fallback、close failure withheld、independent fail-closed rights、`awaiting_terminal`、binding parent/project gate 与真实 writer 回归；第二轮复审确认无剩余 Critical/Important。

## 12. 后续停止线

Stage 49 完成不授权第二个 command。下一阶段必须重新设计和授权，候选优先级为：

1. execution trust rotation / open-attempt recovery 的 operator workflow；
2. Windows Job accounting 与更强 no-orphan verification；
3. POSIX executable image + process-group 等价实现；
4. OS-enforced read-only filesystem proof；
5. approval-required adapter 的 canonical approval binding。

在这些边界单独冻结前，不得增加任意 argv、shell、network adapter 或第二个真实 operation。

<!-- stage49-implementation-status: complete -->
<!-- execution-status: windows-fixed-git-status-only -->
