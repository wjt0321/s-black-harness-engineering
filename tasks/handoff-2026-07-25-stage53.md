# Handoff - 2026-07-25 - Stage 53 Pi Interactive Approval Roundtrip

> 状态：Stage 53 v1 已实现并完成本地验证
> 当前事实源：`docs/102-pi-interactive-approval-roundtrip.md`
> 稳定 tag：`v0.17.0-filtered-snapshot-display-host-integration`
> 下一候选：Stage 54 Pi Postflight Audit Design Gate

## 1. 已完成

- Stage 52 extension 已通过 OMP 17.0.8 同源 ExtensionAPI 真实加载 smoke：普通 read 放行、`.env` read 阻断、`git push origin main` 以 needs_approval 阻断。
- 本机没有独立 Pi CLI；没有把 OMP smoke 误写成 Pi 本体 smoke。
- Stage 53 增加默认关闭的 `AGENT_RUNTIME_APPROVAL_MODE=interactive`。
- v1 只允许同 cwd 的精确 `git push origin main` 进入一次性 UI 确认。
- 用户确认后从当前 event input 重新归一化、重跑 bridge，并匹配 request_id/request_hash/tool/target_hash。
- 无 UI、print/json、拒绝、超时、输入漂移、bridge 漂移、blocked/invalid 均 fail closed。
- 批准不写磁盘、不缓存、不复用；Harness 不执行 host 工具。

## 2. 验证

- `integrations/pi/test/preflight-bridge.test.ts`：18 项通过。
- 真实 OMP smoke 没有执行任何 git push，没有修改 Pi/OMP 持久配置。
- 后续仍需全量 pytest、doctor、public scan、docs context 和 diff check 收口。

## 3. 重要边界

- Pi/OMP 允许排序更后的 extension 替换整个 `event.input`，宿主没有 final-handler 证明；deep freeze 只能阻止常规原地改参。
- 因此 Stage 53 是有限本地 host approval，不是通用 approval authority。
- 扩大命令范围前必须先解决 final-arguments binding，或由 Harness 接管执行。
- 不开放 approval ledger、远程审批、跨会话批准、第二个 operation、通用 shell/network execution。

## 4. 恢复顺序

1. `docs/000-stage-digest.md`
2. `docs/102-pi-interactive-approval-roundtrip.md`
3. `docs/101-pi-coding-agent-preflight-bridge.md`
4. `docs/100-fixed-execution-operational-recovery-implementation.md`
5. `tasks/handoff-2026-07-25-stage53.md`

## 5. 下一阶段停止线

Stage 54 只允许设计 Pi/OMP postflight audit：final arguments identity、脱敏结果投影、失败/取消映射与 ledger 边界。未经独立授权不得实现持久 audit writer、通用 approval、Harness execution authority 或第二个 command。
