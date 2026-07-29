export type DeckAgent = {
  id: string
  name_zh: string
  role_zh: string
  integration_status: string
  status: string
  status_label_zh: string
  safe_summary_zh: string
  readiness_status?: string
}

export type DeckTask = {
  task_id: string
  title_zh: string
  status: string
  status_label_zh: string
  assignee_label_zh: string
  updated_at: string
}

export type AgentDeckSnapshot = {
  schema_version: "agent-deck/read-model/v1"
  source_mode: "runtime" | "fixture"
  project: { id: string; name_zh: string }
  agents: DeckAgent[]
  registered_work: Array<{ card_id: string; title_zh: string; summary_zh: string; topology: string[] }>
  task_queue?: DeckTask[]
  timeline: Array<{ chain_id: string; status: string; status_label_zh?: string; safe_summary_zh?: string }>
  delivery: { summary_zh: string }
  guarantees: { read_only: boolean; ui_dispatch: boolean }
}

export function isAgentDeckSnapshot(value: unknown): value is AgentDeckSnapshot {
  return Boolean(
    value &&
      typeof value === "object" &&
      (value as { schema_version?: unknown }).schema_version === "agent-deck/read-model/v1" &&
      Array.isArray((value as { agents?: unknown }).agents),
  )
}
