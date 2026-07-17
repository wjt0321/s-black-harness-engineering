# Release Notes 108 — Stage 49 Fixed Git Status Executor

> 日期：2026-07-17
> 形态：本地提交级里程碑，不创建 tag，不 push

## 完成

- 新增 strict machine-local execution trust binding schema；
- 新增 PATH sanitization、actor-writable directory removal、reviewed SHA-256/file-id/Authenticode signer binding；
- 新增 non-shareable executable handle、suspended spawn actual image recheck；
- 新增 lstat-first repository/config/submodule/lock containment 与 pre/post guard；
- 新增 Windows `KILL_ON_JOB_CLOSE` Job Object bounded runner；
- 新增 64 KiB 双流 hard stop、10/30 秒 timeout、no retry/no background；
- 新增 finite porcelain-v1 branch/XY grammar 与 path-free safe summary；
- 新增 `orchestration execution trust bind` preview/commit/replace；
- 新增 `orchestration execution git-status --commit`；
- 接入 Stage 48 started/terminal audit release gate；
- 新增默认 skip、显式授权运行的真实 Windows integration smoke；
- 独立安全复审闭合 repository reopen race、无界 metadata read、pre-assignment orphan、writable-check fail-open、terminal state 与 binding location 六项 Important，二次复审无剩余 Critical/Important；
- Stage 44 readiness v1 保持历史 blocked snapshot；
- generic external execution、POSIX、linked worktree、submodule、network/service/DB/UI 继续 unavailable。

## 安全口径

ready 只证明：

```text
no_write_contract = true
guard_evidence_passed = true
filesystem_write_proof = false
```

不输出 raw stdout/stderr、filename、branch、absolute root、executable path、PATH/environment 或 config value。

## 验证

Stage 49 收口要求 full pytest、doctor、public scan、controlled-write regression、compileall、docs context、diff check、Git Bash pre-commit 和显式真实 smoke 全部通过。

## 版本

本能力为 Windows-only、machine-local limited enablement，仍缺 OS-enforced filesystem proof 与 POSIX 等价实现，因此不创建 `v0.18.0`。稳定 tag 继续为已推送的 `v0.17.0-filtered-snapshot-display-host-integration`。
