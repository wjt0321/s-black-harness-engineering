<!-- parents: ../95-single-user-real-execution-readiness-gate-and-milestone.md -->

# Release Notes 104 — Stage 44 Single-user Execution Readiness Gate

> 日期：2026-07-16
> 状态：实现与验收完成

## 新增能力

新增只读命令：

```text
python -m agent_runtime.cli orchestration execution readiness [--json]
```

命令读取固定 `execution-readiness` profile、adapter registry 和 event schema，输出版本化 `control-plane/single-user-execution-readiness/v1` 门禁结果。它不启动进程、不探测 Git、不读取凭据、不访问网络、不写文件或 ledger。

## 固定边界

- 身份模式固定为 `single_user_local` / `local-operator`，不实现多用户授权；
- future extension 仅声明 `actor_context`，不读取 OS 用户或伪造认证；
- 唯一候选为 `shell-local/git_status`，registry 必须保持 `requires_approval=false`；
- future argv 固定为 `git status --short --branch`，`shell=false`；
- cwd、环境白名单、10/30 秒 timeout、64 KiB stdout/stderr、no retry/network/write/background 已冻结；
- approval 必须绑定 plan/request/task/adapter/capability/operation/target digest；
- execution audit 必须 controlled append/rollback，禁止持久化 raw stdout/stderr。
- gate 会校验 event schema 自身，并确认 execution lifecycle event types 当前尚未进入 ledger enum。

## 结果语义

固定 13 项 checks。当前 10 项 design contract pass，以下 3 项 blocked：

- fixed executor 尚未实现；
- approval → canonical plan hash binding 尚未实现；
- execution lifecycle audit writer 尚未实现。

因此命令稳定返回 `blocked` / exit 2 / `design_ready_implementation_blocked`。该结果不授予任何执行权限。

v1 被永久冻结为 Stage 44 的 blocked snapshot；未来 executor 实现不得通过把 profile implementation 字段改成 `true` 来升级状态，必须引入 v2 或独立的真实 implementation gate。

## 验收

- 22 项专用 TDD 用例先 RED 后 GREEN；
- malformed profile/schema/registry/event schema、registry approval drift 与 value-safe failure 已覆盖；
- CLI surface、orchestration contract 与 registry consistency 相关回归通过；
- doctor 已纳入新 schema/sample；
- 真实外部命令执行仍 unavailable。
