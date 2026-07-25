<!-- parents: 108-pi-cli-mode-stabilization.md -->
<!-- relates: 101-pi-coding-agent-preflight-bridge.md, 107-pi-project-local-runtime-integration.md, 48-adapter-runtime-interface.md, 49-capability-routing-model.md -->

# 109 - Pi Adapter Discovery & Capability Projection (Stage 60)

> 状态：Stage 60 已完成并收口
> 日期：2026-07-25
> 授权范围：只读。把已工作的 Pi CLI Layer 1 本地运行时表示进 control-plane adapter registry / routing / snapshot；不调用 Pi、不做模型调用、不执行外部进程、不访问网络、不写 ledger、不启用 approval/postflight、不改 Pi extension

## 1. 目标与最小集成面

Pi CLI Layer 1 在项目本地 ignored runtime 已可用（Stage 58/59），但 control-plane 的 adapter registry / routing / snapshot 里没有它的表示。本阶段以**最小集成面**补齐：

1. source-backed registry 新条目 `pi-cli`（`adapters/adapters.sample.json`，**追加在数组末尾**，既有条目 source_index 不变）；
2. 只读本地运行时 discovery 模块 `agent_runtime/pi_runtime_discovery.py`；
3. 确定性 readiness 投影接入 `orchestration adapter inspect`（仅 pi-cli 附加 `local_runtime` 块）与 `orchestration preflight`（fail-closed 门禁）；
4. control-panel snapshot 经既有 `list_adapters` 消费自动包含新条目，无新代码。

## 2. Registry 条目设计

- `id: pi-cli`，`kind: pi_cli`（新 kind，schema enum 与 `KIND_TO_ADAPTER_TYPE` 同步，`pi_cli → agent`）。
- capabilities 全部为**新且唯一**的名字：`cli_agent_print`、`cli_agent_json_events`、`cli_agent_tui`、`preflight_gated_read`；不与任何既有 capability 重叠，既有 route/preflight 输出逐字节不变（兼容性硬约束）。
- `risk_level: external`（提示词会外发到模型 API），`requires_approval: false`；guardrail 按既有 external 语义给出 `require_user_approval` finding，因此 preflight 即使 runtime ready 也是 `needs_approval` —— 本阶段不授予任何执行权限。
- `preflight_checks: ["policy_check", "local_runtime_ready"]`；`local_runtime_ready` 即第 3 节 discovery 门禁的声明。
- 与 `pi-host`（host 侧 preflight 门禁）和 `omp-acp`（ACP 委派）显式区分。

## 3. 本地运行时 Discovery（`pi_runtime_discovery`）

`discover_pi_runtime(root, env=None)` 返回确定性 `PiRuntimeStatus`（相同文件系统/环境输入 → 相同输出；无时间戳、无随机数；`env` 可注入便于测试）。固定顺序 7 项检查，fail closed（invalid > unavailable > needs_input > ready）：

1. `PI_CODING_AGENT_DIR` 已设置（缺失 → needs_input）；
2. agent dir 必须解析在 `<root>/.runtime/` 内（逃逸 → invalid，拒绝检查外部目录）；
3. agent dir 存在（缺失 → unavailable）；
4. `settings.json` 钉住 `defaultProvider`/`defaultModel`（未钉住 → invalid；防止 Stage 59 诊断出的解析漂移）；
5. `models.json` 含钉住的 provider/model（缺失 → invalid）；
6. provider `apiKey` 必须是 `$ENV_VAR` 引用形式（明文 → invalid，**值永不回显**）；
7. 被引用 env var 存在（只报告存在性布尔，缺失 → needs_input）；extension `extensions/pi-preflight-bridge/index.ts` 存在（缺失 → unavailable）。

硬边界：

- 只读 `settings.json` / `models.json`，单文件 64 KiB 上限，读取前经 `loader.is_safe_to_read` 过滤；
- **绝不读取** `auth.json`、`sessions/`、`.env*` 或任何凭据文件（测试用 canary 文件证明内容不出现在输出）；
- 不执行进程、不访问网络、不写任何文件；因此无法探测 `pi --version`（已知限制，见第 6 节）。

## 4. 表面接入行为

- `orchestration adapter list` / control-panel snapshot：自动包含 `pi-cli`（adapter_type=agent，risk=external）；adapter 总数 9 → 10。
- `orchestration adapter inspect pi-cli [--json]`：附加 `local_runtime` 块（status、agent_dir、default provider/model、7 项 checks、findings、next_action）；其他 adapter 输出不变。
- `orchestration preflight --capability cli_agent_print --operation ...`：
  - runtime 未就绪 → `blocked`，guardrail 携带 `local_runtime` 明细与 `pi-runtime-*` findings（fail closed）；
  - runtime 就绪 → 继续既有 policy guardrail，因 external risk 得 `needs_approval`（无执行权限）。
- `orchestration route preview`：新 capability 选中 `pi-cli`；既有 capability（如 `local_command`）选择不变。

## 5. 验证

- 新增 `tests/test_pi_runtime_discovery.py`：**19 项**（ready/确定性/秘密安全、6 类 fail-closed 失败模式、明文 apiKey 不回显、auth/session canary 不读取、超大 config 拒绝、registry 投影、inspect/preflight/route CLI 集成、既有路由不受影响）。
- 全量 `pytest`：**1390 passed, 8 skipped（均为既有 skip）**，0 failed。
- `doctor` PASS；`tools/public_scan.py` OK；`git diff --check` 干净（仅全仓既有 LF→CRLF 警告）。
- 真实表面手测：无 env → inspect `needs_input`、preflight `blocked`；有 env → inspect `ready`（7/7 checks）、preflight `needs_approval`；`local_command` 仍选中 `shell-local`。

## 6. 边界与限制

- 只读投影，不授予执行权限；不调用 Pi、不做模型调用、不执行外部进程、不访问网络、不写 ledger。
- 无法探测 Pi 版本（需要进程执行，本阶段禁止）；`agent_dir` 为本地路径，非凭据，可回显。
- readiness 依赖调用时的环境变量（`PI_CODING_AGENT_DIR`、被引用的 API key var）；CI/无 env 环境下 preflight 对 pi-cli 一律 fail closed，这是设计行为。
- control-panel snapshot 的 adapter 计数与 snapshot identity 随 registry 源变化（预期内，源驱动）。
- 不启用 approval/postflight；不改 `integrations/pi/`；`.runtime/` 内容只做存在性/形状检查，不进入 Git。

## 7. 下一候选

- 真实终端人工 TUI 会话验收（Stage 59 遗留 operator 步骤）。
- 若未来要为 pi-cli 开放任何 dry-run/commit 执行语义，必须独立设计 stage 并由用户明确授权（含 policy 规则、bounded runner、audit 链）。

<!-- stage60-status: pi-adapter-discovery-projection-complete -->
<!-- route: pi-first-layered -->
<!-- next-stage: pi-tui-operator-acceptance -->
