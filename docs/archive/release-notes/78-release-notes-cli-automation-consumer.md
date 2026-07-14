# Release Notes — Post-Stage 14 — CLI Automation Consumer

日期：2026-07-14

## 结论

post-Stage 14「CLI 自动化消费者」完成收口。本轮把 Stage 13/14 已冻结的真实 orchestration CLI 边界转化为可机器发现、协商、命名化、计划和重检的本地自动化契约；全过程保持只读 discovery / projection，不执行 workflow step、外部命令或真实 adapter。

## 已交付

### 1. Contract Discovery

- `orchestration contract inspect`
- 输出 `control-plane/orchestration-contract/v1`
- 确定性列出 stable、stable_limited、preview、unavailable、access、真实 command argv、关键 flag 与 boundary。

### 2. Requirement Gate

- `orchestration contract check`
- 输出 `control-plane/orchestration-contract-check/v1`
- 支持 requirement 去重排序、preview 显式 opt-in 与 access ceiling。
- unknown / preview 未授权返回 `needs_input`；unavailable / access 超限返回 `blocked`。

### 3. Source-backed Automation Profile

- `orchestration profile list/inspect/check`
- 固定读取 `automation/automation-profiles.sample.json`，由 JSON Schema 和 doctor 校验。
- 首批 profile：`ci-read-only`、`local-dry-run`、`local-controlled-write`。
- profile check 复用 Requirement Gate，不复制 capability table。

### 4. Read-only Workflow Plan

- `orchestration workflow plan --profile-id ...`
- 输出 `control-plane/automation-workflow-plan/v1`
- gate 通过后按固定 phase 投影 manifest-backed command、flag、availability、access 与 boundary。
- 每个 step 固定为 `planned` / `not_executed`。
- `plan_id` 使用 canonical safe projection 的 SHA-256 内容寻址。

### 5. Workflow Plan Re-check / Drift Validation

- `orchestration workflow check --profile-id ... --expected-plan-id ...`
- 输出 `control-plane/automation-workflow-check/v1`
- 严格校验 `sha256:[a-f0-9]{64}`；非法值在 registry 读取前返回 `needs_input`，不回显原始非法值。
- 当前 projection 与 reviewed plan id 相同返回 `pass`；不同时返回 `blocked` 与 `automation-workflow-plan-drift`。
- hash mismatch 只声明 canonical projection 发生变化，不伪造字段级原因；输出当前完整 plan 供调用方审查。

## 验收覆盖

- manifest shape、availability 计数、真实 argparse command path 与关键 flag 一致性；
- contract requirement 的 pass、unknown、unavailable、preview opt-in、access ceiling 与混合优先级；
- profile registry 的 ordering、missing/invalid schema、duplicate id 和 gate 复用；
- workflow plan 的 phase/order、manifest 复用、controlled-write not-executed、determinism、内容寻址和 no-write；
- workflow check 的 match、drift、invalid id、unknown profile propagation、deterministic CLI、human output 和 no-write；
- 既有 orchestration 默认输出、controlled-write rollback 与全量回归继续通过。

## 安全边界

- 不执行 manifest 或 workflow plan 中的 command；
- 不执行真实 adapter，不探测在线状态；
- 不写 task/event ledger，不持久化 plan 或 check；
- 不读取任意旧 plan 文件，不新增 plan registry/DB；
- 不访问网络、环境变量、credential、token 或 keyring；
- 不引入 service、HTTP/RPC、auth、UI、后台进程或模型代理；
- preview 能力不升级为 stable，controlled-write 仅作为显式候选边界呈现。

## 基线与后续

- 稳定 semver 基线继续保持 `v0.12.1-orchestration-read-loop-snapshot` / `0419a04`，本轮不创建新 tag。
- 增量提交包括：`a9be252`、`b11d1b2`、`330492a`、`0c4d2ba`，以及本次 drift validation / 阶段收口提交。
- CLI 自动化消费者阶段至此收口；当前无进行中的产品阶段。
- 不自动启动 Stage 16 UI / Control Panel，也不自动进入 workflow execution、service 或持久化。
- 后续只有在出现明确的新消费者、集成入口和授权边界后，才从本 release notes、`docs/75-cli-automation-contract-discovery.md` 与最新 handoff 恢复。
