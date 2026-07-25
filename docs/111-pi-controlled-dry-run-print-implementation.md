<!-- parents: 110-pi-controlled-dry-run-adapter-contract.md -->
<!-- relates: 109-pi-adapter-discovery-capability-projection.md, 98-fixed-git-status-executor-implementation-and-limited-enablement.md, 97-execution-lifecycle-audit-writer-design-and-implementation.md -->

# 111 — Pi Controlled Dry-run Print Implementation (Stage 62)

> 状态：**Stage 62 已按 TDD 实现并完成真实 smoke；lease/audit/Windows Job containment 与 DeepSeek 纯文本调用全部闭合**
> 日期：2026-07-25
> 前置：Stage 61 design gate（docs/110）已冻结；用户明确授权本实现与一次受控真实 DeepSeek smoke
> 本阶段新增第二个真实 operation：`pi_cli_print`（Windows-only，显式 `--commit`）

## 1. 交付内容

按 docs/110 contract 实现唯一固定 operation：

```text
actor      = local-operator
adapter_id = pi-cli
capability = cli_agent_print
operation  = pi_cli_print
argv       = ["pi", "--print", "--no-session", "--no-tools", "<bounded prompt>"]
shell      = false
```

> 2026-07-25 contract correction：初版 argv 含 standalone `--` 分隔符；已确认已安装 Pi 0.82.0 `parseArgs` 不支持 standalone `--`（视为 unknown flag 并吞掉 prompt），现冻结为上述无 `--` 形状。flag 注入防护改由 prompt 校验承担：首个非空白字符为 `-` 的 prompt 一律 `blocked`（固定 rule `pi-print-prompt-flag-like`），既有 4 KiB/控制字符/secret scan 边界不变。

- `agent_runtime/pi_print_runner.py`：复用 Stage 49 Windows Job Object containment（suspended spawn、`KILL_ON_JOB_CLOSE`、tree terminate/kill、no-orphan accounting），按 Pi 重定参数：每流 256 KiB、timeout 5..120s（默认 60s）、独立 duration bucket；不含 executable trust image 验证（docs/110 §5 信任缺口已声明）；POSIX 仍 unavailable，无退化实现。
- `agent_runtime/orchestration_pi_print_execution.py`：完整 release gate 链——`--commit` 门禁 → identity token → timeout 范围 → prompt 校验（非空、4 KiB UTF-8 byte、控制字符）→ prompt secret scan → machine-local lease → registry contract 对齐（`pi-cli`/`pi_cli`/external/`cli_agent_print`）→ readiness recheck → 环境 allowlist 重建 → 固定 basename executable 解析 → canonical plan hash（含 prompt SHA-256、runtime/executable/environment/path identity，secret 值以 `<withheld>` 占位）→ started audit（v2）→ pre-spawn readiness recheck → bounded runner → post-run readiness recheck → 输出协议（exit code、非空、UTF-8、NUL、4096 行、secret scan）→ terminal audit → safe summary release。
- 环境 allowlist：`PATH`（Stage 46 式 sanitized）、`SYSTEMROOT`/`COMSPEC`/`WINDIR`、`PI_CODING_AGENT_DIR`（project-local）、`AGENT_RUNTIME_ROOT`、被 models.json 引用的 API key 变量（仅 env 透传，永不回显；缺失 → `needs_input`）。proxy 与其他变量一律不透传。
- `agent_runtime/pi_runtime_discovery.py`：`PiRuntimeStatus` 新增 `api_key_env` 投影字段（仅变量名，值永不读取）。
- CLI：`orchestration execution pi-print --task-id --request-id --prompt --expected-plan-hash? --timeout-seconds 5..120 --commit --json`。缺 `--commit` 固定 `blocked`，不写 audit、不 spawn。
- contract manifest 新增 `pi_cli_print_execution`（stable_limited / controlled_write）；`external_execution_service_stack` 边界文案更新为「fixed Git status 与 fixed Pi dry-run print 是仅有的两个有限例外」。

## 2. 安全投影

ready 结果只包含：status、plan_hash、provider/model（settings 钉住值）、stdout SHA-256 与 byte counts、truncation flags、duration bucket、audit/job accounting 证据。始终 withheld：raw stdout/stderr、prompt 原文、API key、env 值、模型回答文本。`guarantees` 显式声明 `real_model_call=true`、`trusted_executable_chain=false`、`session_written=false`、`tools_enabled=false`。

## 3. 测试

- 新增 `tests/test_pi_print_execution.py`：**36 项**，覆盖 docs/110 验收矩阵：无 `--commit` 无副作用、identity/timeout/prompt 边界（空、4 KiB UTF-8 边界、控制字符、flag-like 起始 token `pi-print-prompt-flag-like`）、prompt/output secret scan 命中且值不回显、readiness 各类失败 fail-closed、API key env 缺失 `needs_input`、环境 allowlist（proxy/其他变量不进入 child env）、executable 解析（project-local 跳过、首选匹配）、固定 argv 精确形状、plan hash 确定性与 prompt 绑定、expected plan hash 匹配/不匹配、started 失败不 spawn、timeout/nonzero/UTF-8/NUL/行数/空输出 failure mapping（spawn/child/output_validation 相位）、pre-spawn 与 post-run readiness 漂移、terminal 失败 `audit_incomplete` 且 summary withheld、lease capability 门禁、runner 平台/timeout 门禁、CLI 无 `--commit` blocked。
- 契约冻结测试同步更新（30 entries、`pi-print` 子命令）。

## 4. 真实 smoke（一次授权；未消耗模型调用）

2026-07-25 执行一次受控 smoke：隔离临时 project root（复制 pyproject/adapters/policies/tasks schema + 独立 smoke task/created event + `.runtime/pi-agent` 的 settings/models/extension，不复制 auth/sessions），真实 `pi --print --no-session --no-tools`，60s timeout。

**结果：`error` / `execution-lease-invalid`，fail-closed 在 lease 门禁处。** 证据：

- 初次观察到 `%LOCALAPPDATA%\agent-runtime\execution-lease-v1.lock` 为 0 字节普通文件（mtime 2026-07-22 19:35）。经 operator 授权后，仅删除该文件并重新尝试；当前终端未继承 User-scope `DEEPSEEK_API_KEY` 的预检先行中止，未进入执行链。随后仅从 Windows User 环境在内存中注入该变量并执行一次实际 smoke，lease acquire 重新创建普通 0 字节锁文件后仍返回 `execution-lease-invalid`。
- 只读 ACL 诊断确定根因：新锁文件 `permissions_minimal=true`，其既有父目录 `%LOCALAPPDATA%\agent-runtime` 为 `permissions_minimal=false`。lease 合同要求父目录与锁文件均满足最小权限，因此按设计 fail-closed；问题不是单纯 stale 文件。
- 两次执行链结果均在 plan/audit/spawn 前终止：`plan_hash=null`、process 投影为空；**未 spawn 子进程、未写 started/terminal audit、未发起任何模型调用、未接触真实 ledger**。真实模型调用次数仍为 0。
- 安全 smoke 结果存于 gitignored `.runtime/stage62-smoke/result.json`；可重复脚本 `.runtime/stage62-smoke/run_smoke.py`（gitignored，含 credential 回显防护）。

后续 operator 已独立授权并完成父目录 ACL 修复，父目录与锁文件均通过 lease backend 最小权限验证。修复后的第一次 smoke 越过 lease，但隔离 fixture 的 task/event ID 不符合数字后缀 schema，在 started audit 前 fail-closed；修正后 127 项离线回归通过。再次授权的 smoke 又发现 task snapshot=`running` 与 created event `to_status=planned` 不一致，在 started audit 前以 `snapshot-status-mismatch` fail-closed；修正后 ledger consistency、audit writer 与 Stage 62 共 138 项离线回归通过。

最新一次授权 smoke 已越过全部前置门禁并真实 spawn 固定 Pi 进程：plan hash 生成，started/terminal audit 完整闭合（attempt `attempt-20260725-001`，`audit_incomplete=false`），Windows Job accounting 通过（3 个进程、direct child reaped、containment closed）。child 以 exit 1 返回，stdout 0 bytes、stderr 26 bytes，raw 按合同 withheld。只读检查已安装 Pi 0.82.0 `dist/cli/args.js` 确认 standalone `--` 不受支持：它被解析为 unknown extension flag 并吞掉后续 prompt；因此该失败发生在 CLI 参数解析、模型调用之前，模型调用次数仍为 0。

契约与实现现已移除 standalone `--`，固定 argv 为 `pi --print --no-session --no-tools <prompt>`；新增 `pi-print-prompt-flag-like` 门禁拒绝首个非空白字符为 `-` 的 prompt。专项测试 36 项通过。

经 operator 最终授权，修正后 smoke **成功**：status=`ready`、lifecycle=`closed`、child exit 0；provider=`deepseek-compat`、model=`deepseek-v4-flash`；stdout 17 bytes（仅 digest 投影，raw withheld）、stderr 0、无截断、duration bucket=`lt-5s`。started/terminal audit 以 `attempt-20260725-001` 闭合为 `closed_succeeded`，`audit_incomplete=false`；Windows Job accounting 通过（3 个进程、direct child reaped、containment closed）。这证明唯一固定 `pi_cli_print` 的真实 DeepSeek 纯文本调用链端到端可用。

## 5. 验证

- 聚焦测试 36 项通过；相关回归（pi discovery、contract、boundary contract、controlled-write regression、preflight bridge）通过；全量 pytest 通过（0 failed，skip 均为既有）。
- `doctor` PASS；`tools/public_scan.py` OK（测试中的 fake Windows 路径已改为动态拼接）；`git diff --check` 干净；`.githooks/pre-commit` rc=0；`docs context` rc=0。

## 6. 边界与限制

- 不开放 read 工具 roundtrip、`--mode json`、TUI、多轮会话或任何第三个 operation；approval/postflight 保持关闭；未改 Pi extension 与 `.runtime/` 运行配置。
- npm/node 安装完整性是声明的信任缺口（docs/110 §5）：v1 不是 trusted executable chain。
- POSIX unavailable；不做无 process-group 合同的退化实现。
- 真实 smoke 已证明 lease、started/terminal audit、Windows Job containment 与 DeepSeek 模型响应链端到端可闭合；公开投影仍仅包含 digest/计数，不释放 prompt 或模型原文。
- 未 commit/push/tag。

## 7. 下一候选

1. 真实终端人工 TUI 会话验收（Stage 59 遗留 operator 步骤）；
2. read 工具 roundtrip / npm identity binding / canonical approval binding 均需独立 design gate 与用户明确授权；
3. Stage 62 代码与文档提交/push 需独立外部发布授权。

<!-- stage62-implementation-status: complete -->
<!-- execution-status: windows-fixed-git-status-and-pi-print-only -->
<!-- stage62-smoke-status: passed-real-deepseek-print -->
