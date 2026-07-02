# 03 — 通用 Policy Schema

## 这份文档解决什么问题

Agent Runtime 需要把“提示词里的注意事项”变成可检查、可复用、可审计的规则。

Policy Schema 的目标不是让 Agent 完全自治，而是在执行高风险动作前，先用机械规则做一层门禁：

- 路径是否放错
- 是否写入只读区域
- 文本是否可能包含密钥
- 命令是否属于高风险动作
- 外发前是否完成必要检查
- 任务完成前是否有验证证据

第一版只定义规则格式和判断语义，不急着接入真实执行链路。

## 设计原则

1. **规则小而硬**
   第一版只覆盖稳定、明确、容易误伤低的规则，不把所有偏好都塞进硬门禁。

2. **硬门禁和提醒分开**
   有些规则必须阻止继续执行，例如发现密钥、写入只读目录；有些只是提醒，例如模型成本较高。

3. **先检查，再执行**
   对外发送、删除、push、代理修改、权限变更等动作，必须先检查，再等待明确授权或进入人工确认。

4. **不把成本策略放进硬门禁**
   模型价格、额度、窗口期适合作为调度参考，不适合在底层门禁里直接阻断。

5. **结果要可解释**
   每条规则命中后必须返回：规则 id、严重级别、处理动作、解释信息。

## Policy 文件顶层结构

建议使用 JSON 或 YAML。早期为了方便程序处理，可以先用 JSON；等规则复杂后再考虑 YAML。

```json
{
  "version": 1,
  "name": "s-black-default-policy",
  "description": "Orchestrator工作区默认规则门禁",
  "owners": ["s-black"],
  "path_rules": [],
  "secret_patterns": [],
  "command_rules": [],
  "publish_rules": [],
  "completion_rules": []
}
```

## 通用字段

每条规则都建议包含这些字段：

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `id` | string | 是 | 稳定唯一 id，便于日志追踪 |
| `title` | string | 是 | 人类可读名称 |
| `description` | string | 否 | 规则解释 |
| `severity` | string | 是 | `block`、`warn`、`info` |
| `action` | string | 是 | 命中后的建议动作 |
| `message` | string | 是 | 展示给 Agent 或用户的提示 |
| `enabled` | boolean | 否 | 默认 `true` |

## 严重级别

| 级别 | 含义 | 默认处理 |
|:---|:---|:---|
| `block` | 硬阻断 | 停止执行，等待修正或用户明确授权 |
| `warn` | 风险提醒 | 可以继续，但必须在日志中记录 |
| `info` | 信息提示 | 不影响执行，仅用于解释和审计 |

## 动作类型

| action | 含义 |
|:---|:---|
| `deny` | 禁止继续执行 |
| `require_user_approval` | 需要用户明确授权 |
| `require_secret_scan` | 需要先做密钥扫描 |
| `require_postflight` | 执行后必须做验证 |
| `suggest_route` | 给出路由建议，不阻断 |
| `log_only` | 只记录 |

## 路径规则 path_rules

用于判断文件是否放错位置，或是否触碰只读区域。

```json
{
  "id": "competition-notes-readonly",
  "title": "比赛目录只读",
  "severity": "block",
  "action": "deny",
  "match": {
    "path_prefix": "D:/competition_notes/"
  },
  "constraints": {
    "readonly": true
  },
  "message": "D:/competition_notes 当前是只读审核区，未经用户明确同意不得写入。"
}
```

常见匹配字段：

| 字段 | 说明 |
|:---|:---|
| `path_prefix` | 路径前缀匹配 |
| `path_contains` | 路径包含关键词 |
| `name_patterns` | 文件名 glob 匹配，如 `*.md` |
| `extensions` | 文件扩展名白名单或黑名单 |
| `keywords_deny` | 路径中禁止出现的关键词 |

常见约束字段：

| 字段 | 说明 |
|:---|:---|
| `readonly` | 是否只读 |
| `deny_directories` | 是否禁止目录 |
| `allow_extensions` | 允许的扩展名 |
| `deny_extensions` | 禁止的扩展名 |

## 密钥规则 secret_patterns

用于扫描准备发布、记录或外发的文本。

```json
{
  "id": "github-token",
  "title": "GitHub Token 模式",
  "severity": "block",
  "action": "deny",
  "regex": "ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}",
  "message": "文本中疑似包含 GitHub Token，必须脱敏后再继续。"
}
```

注意：

- 扫描结果不得回显完整密钥。
- 日志中最多展示命中的规则 id 和密钥前缀类型，不能展示原文。
- GitHub Issue、PR、评论、push 前必须跑这一类检查。

## 命令规则 command_rules

用于判断 shell 命令是否危险。

```json
{
  "id": "git-push",
  "title": "Git Push 外部发布",
  "severity": "block",
  "action": "require_user_approval",
  "regex": "\\bgit\\s+push\\b",
  "message": "git push 会离开本地，必须先确认目标、扫描正文/差异，并取得用户授权。"
}
```

第一批建议覆盖：

- 删除目录：`rm -rf`、`rmdir /s`
- GitHub 发布：`git push`
- GitHub 发文：`gh issue create/comment/edit`、`gh pr create`
- 代理变更：`reg add ... ProxyEnable`、`netsh winhttp`
- 强杀进程：`taskkill /f`
- 定时任务修改：cron create/delete/pause/resume

## 外发规则 publish_rules

用于公开发布、飞书发送、邮件发送、GitHub Issue/PR 等动作前的组合检查。

```json
{
  "id": "github-publish-preflight",
  "title": "GitHub 发文前检查",
  "severity": "block",
  "action": "require_secret_scan",
  "applies_to": ["gh_issue", "gh_pr", "git_push"],
  "required_checks": ["secret_scan", "markdown_format", "target_confirmed"],
  "message": "GitHub 发文前必须扫描密钥，并确认正文是标准 Markdown。"
}
```

可复用检查项：

| 检查项 | 含义 |
|:---|:---|
| `secret_scan` | 密钥扫描 |
| `markdown_format` | Markdown 格式检查 |
| `target_confirmed` | 目标仓库、目标会话或目标收件人已确认 |
| `user_approval` | 用户明确授权 |
| `diff_review` | 已审查差异 |

## 完成验证规则 completion_rules

用于避免“说完成但没有证据”。

```json
{
  "id": "completion-evidence-required",
  "title": "完成必须有证据",
  "severity": "warn",
  "action": "require_postflight",
  "required_evidence": ["file_written", "test_output", "diff_review", "blocker_report"],
  "message": "交付前必须至少提供一种完成证据：落盘文件、测试输出、差异审查或明确 blocker。"
}
```

证据类型建议：

| evidence | 说明 |
|:---|:---|
| `file_written` | 文件已落盘 |
| `test_output` | 测试或脚本输出 |
| `diff_review` | 已审查关键 diff |
| `screenshot` | 截图或网页快照 |
| `blocker_report` | 明确说明卡点和后续路径 |

## 检查结果格式

无论检查的是路径、文本还是命令，输出都应统一成列表。

```json
{
  "status": "blocked",
  "findings": [
    {
      "rule_id": "github-token",
      "severity": "block",
      "action": "deny",
      "message": "文本中疑似包含 GitHub Token，必须脱敏后再继续。"
    }
  ]
}
```

状态建议：

| status | 含义 |
|:---|:---|
| `pass` | 没有命中规则 |
| `warn` | 有提醒，但不阻断 |
| `blocked` | 命中硬门禁，不能继续 |
| `error` | 检查器自身失败 |

## 第一版落地范围

Stage 1 已落地这些：

1. 通用 policy schema 文档：`docs/03-policy-schema.md`。
2. 一份 JSON Schema 草案：`policies/policy.schema.json`。
3. Orchestrator样例 policy：`policies/s-black.sample.policy.json`。
4. Media Agent样例 policy：`policies/wangcai.sample.policy.json`。
5. Memory Agent样例 policy：`policies/dabai.sample.policy.json`。

三份样例 policy 已通过 JSON 语法检查，并已通过 `policy.schema.json` 的 schema 校验。

## 暂不解决的问题

- 不做完整权限系统。
- 不接管 QwenPaw 内置工具调用。
- 不自动执行外部发布。
- 不做 UI。
- 不把模型成本、窗口期额度写成硬阻断。

## 和现有 harness POC 的关系

现有 `./workspaces/orchestrator\tools\harness\policy.json` 是Orchestrator工作区的轻量 POC，已经验证了三类规则：

- 路径规则
- 密钥扫描
- 危险命令

Agent Runtime 的 policy schema 是对这份 POC 的上提抽象。后续可以让 POC 检查器读取新格式，也可以在 Runtime 中单独实现新的检查器。
