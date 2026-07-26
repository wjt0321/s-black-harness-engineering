<!-- parents: 109-pi-adapter-discovery-capability-projection.md -->
<!-- relates: archive/96-fixed-git-status-executor-design-gate.md, 97-execution-lifecycle-audit-writer-design-and-implementation.md, 98-fixed-git-status-executor-implementation-and-limited-enablement.md, 101-pi-coding-agent-preflight-bridge.md, 108-pi-cli-mode-stabilization.md -->

# 110 — Pi Controlled Dry-run Adapter Contract (Stage 61, Design Only)

> 状态：**Stage 61 design gate 冻结；未授权任何实现**
> 日期：2026-07-25
> 前置：Stage 60 Pi adapter discovery 与 capability/readiness 只读投影已收口
> 本文档只是 contract：不实现 runner、不实现执行命令、不启动 subprocess、不做模型调用、不访问网络、不写 ledger、不启用 approval/postflight、不改 Pi 配置

## 1. 目标与边界

Stage 60 已把 Pi CLI 本地运行时以只读方式投影进 control-plane，`pi-cli` 条目的 preflight 目前收敛于两种结果：runtime 未就绪 `blocked`（fail closed）、就绪 `needs_approval`（`risk_level=external`）。下一步若要给出任何执行语义，必须先冻结本 contract。

本 design gate 冻结**唯一候选 operation `pi_cli_print`** 的受控 dry-run 执行契约。它与 Stage 46 的角色完全对应：先冻结 design contract，后续实现 stage（推荐 Stage 62）才在用户再次明确授权下按 TDD 落地。

明确边界：

- v1 **没有任何执行权限**；本文档不产生新 CLI、runner、schema、event type 或代码。
- 唯一真实 operation 仍是 Stage 49 Windows `git status --short --branch`，其权限不变。
- `pi_cli_print` 若实现，也必须显式 `--commit` 才允许启动 subprocess；缺少 `--commit` 固定返回 `blocked`，不写 audit、不启动进程（与 Stage 49 §2.2 同构）。
- `pi_cli_print` 是**真实模型调用**：prompt 会外发到第三方模型 API。dry-run 指「Harness 侧不做任何本地写操作」，不是「不调用模型」。是否允许真实模型调用必须由用户在实现 stage 启动时再次明确授权。

## 2. 方案比较

### 方案 A：直接给 `pi-cli` 开放通用 argv/subprocess

拒绝。Pi CLI 支持任意 flag、任意工具集、任意模型；开放 argv 等于开放通用 agent 执行，远超 Stage 49 级别的固定 operation 语义，也无法做有限输出解析。

### 方案 B：走 Pi RPC/SDK 长驻会话

拒绝。长驻进程等于 background service，违反「不启动服务」边界；一次性 stdin/stdout 语义已由 Stage 52 bridge 证明够用。

### 方案 C：固定 operator-owned 一次性 invocation + 有界 process tree + 有限输出协议（采用）

采用。唯一固定 identity：

```text
actor       = local-operator
adapter_id  = pi-cli
capability  = cli_agent_print
operation   = pi_cli_print
argv        = ["pi", "--print", "--no-session", "--no-tools", "<bounded prompt>"]
shell       = false
```

operator 唯一可控输入是 prompt 文本；不接受 caller-supplied flag、model、provider、agent dir、cwd、environment 或 tools 参数。与 Stage 46 的 fixed argv 模式一致，区别仅在 child 不是可绑定的单一 exe（见第 5 节信任缺口）。

## 3. 固定调用形状与严格限制

### 3.1 `--print --no-session --no-tools` 的取舍

v1 冻结 `--no-tools`：

- `--no-session`：不落 session 文件，不保留会话状态；child 结束后 Pi agent dir 不产生新的持久会话记录。
- `--no-tools`：模型输出只能是纯文本，Pi 不会执行 read/write/edit/bash 任何工具。这把「模型能力」限制为纯文本生成，是 v1 把外发调用纳入受控执行链的最小安全面。
- 不冻结 `--mode json`：json 事件流包含 tool/thinking 等结构性事件，有限解析协议更大；留给后续独立候选。
- 不冻结 `--tools read` 的 read roundtrip：它允许模型读取本地文件，需要额外的目标路径 containment 与 preflight 门禁复用设计，超出 v1 最小面。列为后续独立候选（第 13 节）。

因此 v1 的本地副作用面被压到最小：无 session 写入、无工具执行；唯一外部效应是模型 API 调用本身。

### 3.2 Prompt 输入限制

- 单条 prompt 文本，经 argv 传入（**不走 stdin**，stdin 直接关闭，避免模型/CLI 从 stdin 读取额外内容）。
- 长度上限：4 KiB（UTF-8 byte）；拒绝 NUL 与控制字符（允许 `\n`、`\t`）；必须是合法 UTF-8。
- 先经现有 policy 检查管线（`check_text` 语义）与 secret/public scan：prompt 内容若命中 secret 规则，`blocked`，且不输出命中值。
- prompt 不进入公开 result 投影；只以 SHA-256 digest 进入 plan/audit 绑定（第 8 节）。
- prompt 作为唯一位置参数直接跟在固定 flag 之后；**不使用 standalone `--` 分隔符**（已实现 Pi 0.82.0 `parseArgs` 不支持 standalone `--`，会把它当 unknown flag 并吞掉 prompt）。作为替代的 flag 注入防护：首个非空白字符为 `-` 的 prompt 一律 `blocked`（固定 rule `pi-print-prompt-flag-like`）。

## 4. 环境 allowlist 与 secret 处理

child 环境使用**显式 allowlist 重建**，不继承父进程环境（与 Stage 46 sanitized PATH 同一思路，但范围收紧到整个环境）：

| 变量 | 来源 | 说明 |
|:---|:---|:---|
| `PI_CODING_AGENT_DIR` | 固定为 `<root>/.runtime/pi-agent`（项目本地） | 与 Stage 60 discovery 的 containment 检查一致，拒绝外部目录 |
| `AGENT_RUNTIME_ROOT` | 固定为 `<root>` | preflight extension 需要 |
| `DEEPSEEK_API_KEY` | 从当前 operator 环境透传 | 唯一被透传的 secret；**绝不写入 audit/result/log，绝不回显** |
| `SYSTEMROOT`、`COMSPEC`（Windows） | 系统值 | Node/进程基础设施所需 |
| `PATH` | Stage 46 式 sanitized PATH | 删除空项、相对项、不存在、project-local、reparse、重复与当前 actor 可写目录；仅用于解析固定 basename `pi`/`node` |
| `PI_OFFLINE` | 不设 | 见第 5 节：v1 明确是真实模型调用，不假装离线 |

禁止透传：其他一切 env（包括 `HTTP_PROXY`/`HTTPS_PROXY`/任意 `*_KEY`、`*_TOKEN`、`*_SECRET`）。proxy 变量不透传意味着 v1 只支持直连可达的网络环境；这是有意的收窄而非缺陷。

secret 处理硬规则：

- `DEEPSEEK_API_KEY` 只经环境变量传递，永不进入 argv（argv 在 OS 进程表中可见）。
- stdout/stderr 在解析前先经 secret/public scan；命中即 `blocked` 且命中值不进入任何输出。
- audit、result、finding、log 中出现的只能是 digest、byte count、truncation flag 与固定 failure code。

## 5. Trust / Identity 限制

诚实降级声明：Stage 49 的 executable trust binding（SHA-256 + Authenticode signer + volume/file identity）**不能直接适用于 Pi**。

- `pi` 是 npm 包：真实入口是 `node <prefix>/node_modules/@earendil-works/pi-coding-agent/dist/cli.js`，Windows 上还存在 `pi.cmd` shim 层。要闭合的 identity 是「node 运行时 + 固定 npm 包入口文件」的组合，而不是单个可绑定 exe。
- npm 包更新不经 operator review workflow，Authenticode 对 cli.js 不适用；项目 local runtime 目录本身又是 operator 可写的。

因此 v1 的信任模型为：

1. **固定 agent dir containment**：`PI_CODING_AGENT_DIR` 必须解析在 `<root>/.runtime/` 内（Stage 60 检查 2），拒绝外部/逃逸目录。
2. **运行前 readiness recheck**：spawn 前重跑 `pi_runtime_discovery` 7 项检查，任何一项漂移（settings 钉住解除、models 漂移、apiKey 变明文引用之外的形式）即 `blocked`。
3. **固定 argv + sanitized PATH + 环境 allowlist**：child 只能以冻结形状启动。
4. **npm 安装完整性是显式信任缺口**：本 contract 不声称能检测 `node_modules` 被同一 OS 用户篡改。把「node runtime 与 npm 包入口的 identity binding（例如 binding 到 cli.js 的 digest + node.exe 的 Stage 46 式 trust）」列为 stop-line 级别的后续设计项，在闭合前不得把 v1 宣传为 trusted executable chain。

这弱于 Stage 49 trust chain 是事实，不是措辞问题；接受它的理由仅为：v1 child 无工具、无 session 写入、副作用面收敛到外发 API 调用。任何扩大（工具、session、json 模式）都必须先补 identity binding 设计。

## 6. Bounded process-tree containment

复用 Stage 49 `fixed_process_runner` 的 Windows 后端语义，参数按 Pi 特性重定：

- `subprocess.Popen` + `CREATE_SUSPENDED` + `KILL_ON_JOB_CLOSE` Job Object；POSIX 明确 unavailable（与 Stage 49 相同，不做退化实现）。
- stdin 关闭；stdout/stderr binary pipes，独立 reader thread。
- 每流 **256 KiB hard limit**（模型文本输出大于 git porcelain，但仍必须有界）；overflow 即 terminate tree 并 withheld。
- timeout：默认 **60 秒**（与 Stage 59 smoke 一致），上限 **120 秒**，下限 5 秒；模型调用延迟高于本地命令，但不允许无界等待。
- no retry、no background、tree terminate → grace → tree kill → direct-child wait；Job close 是最终 no-orphan containment。
- child 可能派生 Node helper 进程，进程树 containment 必须覆盖整棵树（Stage 59 smoke 已验证 kill_tree 语义在 Git Bash 下可行）。

## 7. stdout / stderr / result 处理

有限输出协议（对应 Stage 46 finite porcelain parser 的角色，但 v1 只能做到「有界文本 + 安全检查」，不是语法级 parser）：

- stdout 期望是纯文本回答；接受前检查：UTF-8 合法、byte bound、行数 bound（≤ 4096 行）、无 NUL。
- stderr 只用于诊断；非空 stderr 不自动失败，但进入 digest/count。
- stdout/stderr 先做 secret/public scan，再投影。
- exit code 0 且 stdout 非空 → `ready`；其余见第 9 节 failure mapping。

公开 result 只包含：

```text
status, plan_hash, attempt/audit ids,
stdout/stderr byte counts, stdout SHA-256,
truncation flags, timeout flag, duration bucket,
model/provider identity（来自 settings 钉住值，非运行时探测）
```

始终 withheld：raw stdout/stderr、prompt 原文、env、PATH、agent dir 之外的绝对路径、`DEEPSEEK_API_KEY` 及任何 scan 命中值。模型回答文本**不进入** Harness 公开投影——它是外发模型生成的不可信内容，只能由 operator 在 terminal 直接查看；Harness 只承诺其 digest 与边界证据。

## 8. Plan / Approval / Audit 绑定

完整复用 Stage 47–49 的链：

1. `pi_runtime_discovery` readiness recheck（fail closed）；
2. canonical plan hash：覆盖 actor、adapter_id、capability、operation、固定 argv 形状、prompt SHA-256、settings 钉住的 provider/model identity；不含 prompt 原文与 secret；
3. `execution_attempt_started` controlled append（Stage 47–48 专用 writer，`adapter_id=pi-cli`）；append 失败 runner invocation count 必须为 0；
4. final readiness + guard recheck；
5. bounded runner spawn（第 6 节）；
6. output protocol validation + secret scan（第 7 节）；
7. exactly one terminal audit（`execution_succeeded` / `execution_failed` / `execution_cancelled`），evidence 仅允许 exit code、duration bucket、output digest/byte counts、truncation flags 与固定 failure code；
8. terminal commit 成功后才释放 safe summary；terminal 失败保留 started、`audit_incomplete=true`、summary withheld，走 Stage 50–51 recovery 路径。

approval 语义：`pi_cli_print` 在 policy 上保持 `needs_approval`（external risk）。v1 不实现 canonical approval binding（与 Stage 49 相同立场：`--expected-plan-hash` 可选，operator review 是人工前置步骤）；「approval-required adapter 的 canonical approval binding」仍是 Stage 49 停止线清单中的独立设计项，本 contract 不抢占。

## 9. Failure mapping

| 条件 | status | 说明 |
|:---|:---|:---|
| 缺 `--commit` | `blocked` | 不写 audit、不 spawn（dry-run preview 只返回 would-be plan） |
| runtime readiness 任一检查失败 | `blocked` | 携带 `pi-runtime-*` finding，不回显敏感值 |
| prompt 超限/非法字符/secret scan 命中 | `blocked` | 固定 rule id，不回显命中值 |
| started append 失败 | `error`/`blocked` | runner 不得启动 |
| spawn/timeout/overflow/nonzero exit | terminal `execution_failed` | phase ∈ `spawn`/`child`/`output_validation` |
| stdout 非法 UTF-8 / bound 超限 / scan 命中 | terminal `execution_failed` | phase=`output_validation`，raw withheld |
| 环境 allowlist 重建失败（如缺 `DEEPSEEK_API_KEY`） | `needs_input` | 只报告变量名存在性，不报告值 |
| terminal append 失败 | `error`，`audit_incomplete=true` | 保留 started，走 recovery |

## 10. 明确 stop-lines

以下任何一条在本 contract 下都禁止，需要独立 design gate + 用户明确授权才可改变：

1. 不实现任何 runner/CLI/代码（本 stage 是 design-only）。
2. 不冻结第二个 operation：read 工具 roundtrip、`--mode json`、TUI 自动化、多轮会话均为独立候选。
3. 不开放任意 argv/flag/model/provider/cwd/env override；prompt 是唯一可控输入。
4. 不授权通用 approval binding、远程批准、持久 approval ledger。
5. 不把 v1 宣传为 trusted executable chain；npm 安装完整性缺口未闭合前不得扩大工具/session 面。
6. POSIX 仍 unavailable；不做无 image identity / process-group 合同的退化实现。
7. 不访问 `auth.json`、`sessions/`、`.env*` 或任何凭据文件；不输出任何 secret 值。
8. 不引入 service、DB、daemon、UI、background worker；child 一次性生命周期。
9. 不改 Pi 上游、不改 `integrations/pi/` extension、不改 `.runtime/` 运行配置（实现 stage 若需要 settings 变化，必须重新授权并备份）。
10. 不 commit/push/tag 由 agent 自动执行。

## 11. 验收矩阵（实现 stage 的 TDD 下限）

实现 stage 至少覆盖：

1. 无 `--commit` 固定 `blocked`，audit 与 spawn 计数均为 0；
2. readiness 7 项检查每类失败各一用例（fail closed）；
3. prompt 边界：空、4 KiB 边界、超限、NUL/控制字符、非 UTF-8、secret 命中（值不出现）；
4. 环境 allowlist：非 allowlist 变量不进入 child env；`DEEPSEEK_API_KEY` 缺失 → `needs_input`；值不出现在任何输出；
5. argv 固定性：prompt 作为唯一位置参数进入 argv（无 standalone `--`）；首个非空白字符为 `-` 的 prompt 被 `pi-print-prompt-flag-like` 拒绝；任何其他注入 flag 尝试被 prompt 校验拒绝；
6. runner：timeout tree kill、stdout/stderr overflow withheld、nonzero exit、no orphan（Job accounting）；
7. 输出协议：非法 UTF-8、行数超限、scan 命中 → `execution_failed/output_validation`；raw 不进入 result/audit/log；
8. audit 链：started → terminal 唯一、plan hash 一致、prompt 只有 digest；terminal 失败 `audit_incomplete=true` 且 summary withheld；open attempt recovery 可读；
9. result 投影确定性：相同输入相同 plan hash；无时间戳/随机数泄漏进 plan；
10. controlled-write regression 与全量 pytest、doctor、public scan、diff check、pre-commit hook 全绿；
11. source 不 import socket/requests，不新增网络代码路径；
12. 真实 smoke 默认 skip，需显式环境变量 + 用户授权才运行（同 Stage 49 §9 模式），且 smoke 证据不落 secret。

## 12. 推荐的下一实现 stage

推荐 **Stage 62 — Pi Controlled Dry-run Print Implementation（条件启动）**：

1. 启动前提：用户再次明确授权「允许一次受控真实模型调用」与「允许新增第二个真实 operation」；
2. 按第 11 节验收矩阵 TDD 实现 `pi_cli_print`：复用 `fixed_process_runner`（Windows 后端）、`execution_audit_writer`、`pi_runtime_discovery`、policy/scan 管线；
3. 真实 smoke 走 Stage 49 同款显式 skip 模式，证据写入 gitignored `.runtime`；
4. 完成后仍不开放：read 工具 roundtrip、json 模式、approval binding、POSIX、第三个 operation。

若 Stage 62 之前需要先闭合第 5 节的 npm identity binding 缺口，则先做一个独立 design gate（node runtime + cli.js digest binding），再启动 Stage 62；顺序由用户在启动时决定。

## 13. 后续独立候选（本 contract 不冻结）

按建议优先级：

1. `pi_cli_read_roundtrip`：`--tools read` 单工具 roundtrip，目标路径 containment + 复用 Stage 52 preflight 判定；
2. npm/node identity binding design gate（第 5 节缺口）；
3. `--mode json` 有限事件流 parser；
4. canonical approval binding（Stage 49 停止线既有项，适用于全部 external-risk adapter）；
5. POSIX backend。

<!-- stage61-gate-status: frozen -->
<!-- execution-status: design-only-no-implementation -->
