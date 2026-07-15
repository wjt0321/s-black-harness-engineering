<!-- parents: 81-codex-desktop-read-only-adapter-implementation.md, archive/80-codex-desktop-read-only-adapter-design-gate.md -->
<!-- relates: 79-read-only-host-consumer-validation-boundary.md, 78-control-panel-host-integration-boundary.md -->

# 82 — Read-only Representation Read Design Gate

> 状态：**Stage 21 已收口：当前不开放 representation read**
> 日期：2026-07-15
> 前置事实源：`docs/81-codex-desktop-read-only-adapter-implementation.md`

## 1. 决策摘要

Stage 17 descriptor 已声明 snapshot / HTML representation，但 Stage 18 reference consumer 与 Stage 20 Codex Desktop adapter 都明确不读取 representation。当前仓库没有已冻结的 representation 消费者、用户动作或授权需求，因此 Stage 21 的设计结论是：

> **保持 validation-only；不新增 representation read contract，不执行 descriptor argv，不实现浏览器/文件/服务读取。**

这不是能力缺失，而是一个显式的安全冻结：Stage 20 的 `ready` 只表示 handoff descriptor 通过独立校验，不表示 snapshot 或 HTML 已加载。

## 2. 需求审计结论

现有能力已经覆盖：

- producer 生成确定性 `control-plane/control-panel-handoff/v1` descriptor；
- consumer 独立校验 schema、identity、representation metadata、argv shape 与 read-only boundary；
- host adapter 进行一次性 producer → consumer 调度，并输出 `control-plane/codex-desktop-read-only-adapter/v1`；
- descriptor 中的 representation argv 作为 opaque metadata 存在，但没有任何自动执行路径。

现阶段没有可以安全冻结的以下事实：

- 哪个宿主 UI 或任务动作需要读取 representation；
- 用户是否授权读取 HTML 或 snapshot；
- representation 应该以内存对象、stdout 文本还是浏览器页面呈现；
- 是否需要 envelope-scoped representation；
- representation 内容的脱敏、输出上限、保存和刷新策略。

在这些事实未确定前实现读取，会把“声明 representation”误扩展成“允许执行 argv”，违反当前 adapter contract。

## 3. 方案比较

### 方案 A — validation 后自动读取

不采用。它会让 `ready` 隐含执行权限，并把 descriptor argv 变成未经用户确认的操作入口。

### 方案 B — 新增 `control-panel consume` 命令

不采用。它会把 producer、consumer 和 representation reader 重新耦合，削弱 Stage 18 独立 drift validation 的价值，并扩大 CLI surface。

### 方案 C — 保持 validation-only（采用）

采用。当前 host adapter 只验证 handoff contract；representation 读取只有在出现明确消费者和用户动作后，才能进入新的独立 design gate。

## 4. 当前冻结边界

Stage 20 adapter v1 保持不变：

- 不执行 `snapshot.argv` / `render.argv`；
- 不读取 HTML 或 JSON representation；
- 不打开浏览器，不创建临时文件，不写 artifact；
- 不接受 URL、socket、任意 representation 文件路径或 shell 字符串；
- 不刷新、不轮询、不启动 server、HTTP、WebSocket 或 background process；
- 不把 `next_action` 转换为命令；
- 不改变 `ready`、`blocked`、`validation_failed`、`error` 的状态语义；
- 不新增 schema、identity、ledger event 或持久 collection。

当前唯一允许的 host 动作仍是：

```text
project root
  -> fixed handoff producer
  -> Stage 18 reference consumer
  -> safe validation result
```

## 5. 未来 representation read 的必要前置条件

只有同时满足以下条件，才可以启动 Stage 22：

1. 明确的真实消费者和用户场景；
2. 用户显式选择 representation 类型和读取动作；
3. representation argv allowlist，不接受 descriptor 中任意新增命令；
4. project-root 路径归一化和越界拒绝；
5. stdout / HTML / JSON 输出上限、UTF-8 解析和脱敏规则；
6. timeout、取消、关闭和不自动重试语义；
7. 是否允许内存展示、stdout 返回、浏览器展示或受控导出；
8. representation read 与原 handoff / validation result 的 identity 关联；
9. no-write、no-network、no-service、no-adapter-execution 回归证据；
10. 若要进入 UI，先冻结 UI action 与授权边界，不从 UI 事件直接推导执行权限。

在上述条件完成前，任何 representation read 请求都应返回 unavailable / needs_input，而不是尝试执行。

## 6. Stage 21 验收结论

Stage 21 以“拒绝未定义的 representation read contract”收口：

- 已审计当前 descriptor、consumer 和 adapter 的真实消费范围；
- 已确认当前不存在已冻结的 representation consumer 需求；
- 已比较自动读取、CLI consume 与 validation-only 三种方案；
- 已冻结 validation-only 为当前唯一允许的 host 行为；
- 已明确未来 Stage 22 的进入条件，不修改生产执行边界；
- 未新增 representation reader、浏览器控制、文件 export、service、网络访问或 UI 写操作。

下一阶段为 **Stage 22 — Host-specific Representation Read Implementation（条件启动）**。在获得明确消费者需求并完成新的 design gate 前，不启动该阶段。
