<!-- parents: ../../../docs/96-fixed-git-status-executor-design-gate.md -->

# Release Notes 106 — Stage 46 Fixed Git Status Executor Design Gate

> 日期：2026-07-16
> 状态：design-only gate 已收口

## 阶段结论

Stage 46 已把 `shell-local/git_status` readiness candidate 细化为 fixed executor implementation contract，但没有新增 production executor、CLI、schema 或 event type，也没有执行 Git。

## 冻结内容

- 唯一 operation 仍为 `git status --short --branch`，argv array、`shell=false`；
- project root 必须是当前 agent-runtime repo，v1 只接受直接 `.git/` directory；
- PATH 只负责候选发现；production 必须匹配 operator-reviewed trust binding、publisher/owner/ACL、digest/file identity，并解决 image binding / TOCTOU；
- child PATH 精确使用 canonical sanitized PATH，且与 executable/plan/audit identity 绑定；
- child environment 禁用 optional locks、prompt、system/global config、fsmonitor、untracked cache、maintenance 与 color drift；
- repository-local config 使用有限语法和完整 command/path-bearing key denylist 做 value-safe scan；`core.worktree`、external excludes/attributes、`commondir`、object alternates 与 submodule surface 在 v1 blocked；
- `.git/index/HEAD/packed-refs/refs/objects/pack` 统一采用 lstat-first、never-follow containment；symlink/junction/reparse/hardlink/root escape 在读取或 hash 前 blocked；
- future runner 使用 bounded `Popen` + POSIX process group / Windows Job Object，10/30 秒 timeout、64 KiB stdout/stderr、tree terminate → kill → wait、no retry；
- short-status 使用有限 branch grammar、完整 XY allowlist 与唯一计数映射，未知输出一律 validation failure；
- raw stdout/stderr、file paths、branch name、resolved executable path 和 environment 默认 withheld；
- future result 只释放 dirty/count/ahead-behind/digest 等安全摘要；
- no-write 诚实区分 contract controls、bounded guard evidence 与不存在的 OS-level filesystem proof；
- `execution_attempt_started` 成功写入前不得 spawn，其语义不宣称 child 已创建；terminal audit 与 post-run guard 成功前不得释放 result；
- execution event 只能由专用 writer 写入，通用 append/import 必须拒绝 reserved event type。

## 方案取舍

- 拒绝通用 shell/任意 argv；
- 拒绝以简单 `subprocess.run` 作为 production collector；
- 采用 trusted executable binding + bounded one-shot process-tree runner；
- linked worktree、path reveal、OS sandbox、multi-user auth、network/service/DB/UI 继续延期。

## 文档维护

- 新增 `docs/96-fixed-git-status-executor-design-gate.md`；
- 旧 Stage 14 CLI draft 完整归档为 `docs/archive/53-minimal-orchestration-loop-cli-draft.md`；
- 同步 digest、index、roadmap、README、AGENTS、versioning、handoff 与 progress；
- 活跃 docs 保持 50 个；
- 本阶段不创建 tag、不 push，稳定版本仍为已推送的 v0.17.0。

## 后续入口

下一阶段为 **Stage 47 — Execution Lifecycle Audit Writer Design Gate（条件启动）**。先冻结 reserved event schema、专用 writer provenance、通用 append/import 拒绝、controlled append/rollback 与 attempt-started/terminal recovery，再进入 writer 实现。只有 writer、executable trust/image binding、sanitized child PATH、process-tree containment 和有限 porcelain parser 全部就绪，且用户再次明确授权真实 subprocess 后，才允许 fixed Git status executor implementation。
