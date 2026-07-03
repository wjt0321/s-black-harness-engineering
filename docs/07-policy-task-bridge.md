# 07 — Policy 与 Task 状态衔接

## 这份文档解决什么问题

前面已经定义了三块基础能力：

- Policy Schema：规则如何表达。
- Task State Model：任务如何记录状态。
- Adapter Layer：工具如何被统一调用。

但还缺一个关键衔接：当 policy 命中时，任务状态应该怎么变化？

这份文档定义 policy 检查结果如何影响 task ledger，避免规则检查只停留在提示文本里。

## 基本原则

1. **Policy 不直接执行动作**
   Policy 只判断一个动作是否允许、是否需要授权、是否需要补检查。

2. **Task 记录后果**
   Policy 命中后的阻塞、等待授权、等待输入、验证失败，都应该落到 task 状态或事件流里。

3. **Adapter 服从 Policy**
   Adapter 在 preflight 未通过时不得继续执行。

4. **完成状态必须由 evidence 支撑**
   即使所有 policy 都通过，也不能在没有完成证据时进入 `finished`。

5. **用户授权只针对本次动作**
   授权语义默认收窄为“本次、此目标、此动作”，不能泛化成长期许可。

## Policy 检查结果格式

Policy 层建议统一返回：

```json
{
  "status": "blocked",
  "findings": [
    {
      "rule_id": "github-publish-preflight",
      "severity": "block",
      "action": "require_secret_scan",
      "message": "GitHub 发布前必须完成密钥扫描。"
    }
  ]
}
```

`status` 建议取值：

| status | 含义 |
|:---|:---|
| `pass` | 没有命中阻断或提醒 |
| `warn` | 有提醒，但不阻断 |
| `blocked` | 命中硬门禁，不能继续 |
| `needs_approval` | 需要用户明确授权 |
| `needs_input` | 缺少必要输入 |
| `error` | policy checker 自身失败 |

## 映射总表

| Policy 结果 | Task 状态 | blocked_reason | 说明 |
|:---|:---|:---|:---|
| `pass` | 不改变 | null | Adapter 可以继续执行 |
| `warn` | 不改变 | null | 记录 event，继续执行 |
| `blocked` + `deny` | `blocked` | `policy_blocked` | 硬阻断，不执行 Adapter |
| `blocked` + `require_secret_scan` | `blocked` | `policy_blocked` | 先补密钥扫描或脱敏 |
| `needs_approval` | `blocked` | `need_user_approval` | 等待用户明确授权 |
| `needs_input` | `blocked` | `need_user_input` | 等待补充输入 |
| `error` | `blocked` | `tool_failed` | checker 失败，不能假装通过 |

## action 到 Task 的映射

### deny

`deny` 表示动作不得继续。

任务处理：

- `status = blocked`
- `blocked_reason = policy_blocked`
- `next_action` 写明修正方式
- 追加 `blocked` event

示例：

```json
{
  "status": "blocked",
  "blocked_reason": "policy_blocked",
  "blocked_message": "目标路径属于只读区域，未经授权不得写入。",
  "next_action": "改用允许的输出目录，或请求用户明确授权。"
}
```

### require_user_approval

`require_user_approval` 表示动作可能可以执行，但必须先取得用户授权。

任务处理：

- `status = blocked`
- `blocked_reason = need_user_approval`
- `next_action` 写明需要用户确认的具体动作、目标和风险
- 追加 `blocked` event

授权恢复时：

- 追加 `unblocked` event
- 从 `blocked` 回到 `running`
- 记录 `approval_ref`

### require_secret_scan

`require_secret_scan` 表示必须先扫描待发布文本、diff、参数或附件。

如果未扫描：

- `status = blocked`
- `blocked_reason = policy_blocked`
- `next_action = run secret_scan`

如果扫描命中：

- 继续保持 `blocked`
- 不得在日志中回显完整密钥
- 要求脱敏或移除敏感内容

如果扫描通过：

- 追加 `evidence_added` event
- 可继续 preflight 的下一步

### require_postflight

`require_postflight` 表示动作执行后必须验证结果。

任务处理：

- Adapter 可以执行，但不能直接让 task 进入 `finished`
- 执行后必须追加 evidence
- postflight 失败时，任务回到 `running` 或进入 `blocked`

示例 postflight：

- `git_status_clean`
- `remote_status_verified`
- `artifact_exists`
- `proxy_restored`
- `json_valid`

### suggest_route

`suggest_route` 只给路由建议，不阻断。

任务处理：

- 状态不变
- 追加 `progress` event
- 路由层可以把建议作为参考

### log_only

`log_only` 只记录，不影响执行。

任务处理：

- 状态不变
- 追加普通 event 或不追加，由实现决定

## Completion Rules 与 finished

任务进入 `finished` 前必须满足 completion rules。

最小要求：

- 至少有一种 evidence。
- evidence 与任务目标相关。
- 如果有 postflight 要求，postflight 必须完成。
- 如果有公开发布动作，必须完成 secret scan 和 target confirmation。

如果 evidence 不足：

- 不允许进入 `finished`
- 保持 `running` 或进入 `blocked`
- 追加 event 说明缺少什么证据

## Preflight 流程

建议流程：

```text
Task running
  -> Adapter prepares action descriptor
  -> Policy preflight
  -> pass / warn: Adapter executes
  -> blocked / needs_approval / needs_input: Task blocked
  -> Adapter result
  -> Postflight
  -> Evidence added
  -> Completion check
  -> finished or continue
```

## Action Descriptor

Adapter 执行前应生成可被 policy 检查的 action descriptor。

```json
{
  "task_id": "task-20260703-001",
  "adapter_id": "github-cli",
  "operation": "git_push",
  "risk_level": "external",
  "target": "origin/main",
  "payload_refs": ["git_diff", "commit_message"],
  "requires_approval": true
}
```

Policy checker 不需要知道 Adapter 内部如何实现，只需要检查这个 descriptor。

## Event 写入规则

Policy 命中应写入事件流，建议事件格式：

```json
{
  "event_id": "evt-20260703-001",
  "task_id": "task-20260703-001",
  "timestamp": "2026-07-03T10:00:00+08:00",
  "actor": "policy-checker",
  "event_type": "blocked",
  "from_status": "running",
  "to_status": "blocked",
  "message": "GitHub push requires user approval and secret scan.",
  "artifacts": [],
  "metadata": {
    "rule_id": "git-push",
    "blocked_reason": "need_user_approval"
  }
}
```

## 用户授权恢复流程

当用户明确授权后：

1. 记录授权引用，例如消息 id、时间、授权文本摘要。
2. 追加 `unblocked` event。
3. task 从 `blocked` 回到 `running`。
4. 重新运行必要 preflight。
5. Adapter 执行。

注意：授权不应跨任务复用。

## 常见场景

### GitHub push

```text
Adapter: github-cli / git_push
Policy: require_secret_scan + require_user_approval
Task: blocked / need_user_approval
恢复: 用户授权 + secret scan passed
Postflight: remote_status_verified + git_status_clean
Evidence: remote URL or push output
```

### 飞书消息发送

```text
Adapter: lark-cli / send_message
Policy: target_confirmed + user_approval
Task: blocked / need_user_approval
Postflight: external_confirmation
Evidence: message id or send result
```

### 写入只读目录

```text
Adapter: shell-local / write_file
Policy: deny
Task: blocked / policy_blocked
恢复: 改目标路径，或用户明确授权后重新检查
```

### 缺少完成证据

```text
Adapter: any
Policy: completion_evidence_required
Task: running or blocked
原因: 不能进入 finished
恢复: 补 test output / artifact path / blocker report
```

## 与 Adapter Layer 的关系

Adapter 负责：

- 准备 action descriptor。
- 等待 policy preflight 结果。
- 执行动作。
- 返回结构化结果。
- 产出 postflight evidence。

Adapter 不负责：

- 擅自忽略 policy。
- 自己决定最终 finished。
- 吞掉失败。

## 与 Task Ledger 的关系

Task ledger 负责：

- 保存 task 当前状态。
- 追加 policy 命中事件。
- 记录 blocked reason。
- 保存 evidence。
- 保留恢复路径。

## 第一版落地范围

Stage 4 衔接补充交付物：

1. `docs/07-policy-task-bridge.md`：Policy 与 Task 状态衔接说明。

后续可以再补：

- `tasks/policy-event.examples.jsonl`
- 最小 policy checker POC
- `agent-runtime check action` 命令设计

## 暂不解决的问题

- 不实现真实 checker。
- 不接入真实 Adapter 执行链路。
- 不自动解析所有 shell 命令语义。
- 不做权限系统 UI。
- 不持久化用户授权数据库。
