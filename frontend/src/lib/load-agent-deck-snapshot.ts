import { type AgentDeckSnapshot, isAgentDeckSnapshot } from "./agent-deck-types"

export type RuntimeState =
  | { kind: "loading" }
  | { kind: "live"; snapshot: AgentDeckSnapshot }
  | { kind: "unavailable"; message: string }
  | { kind: "invalid"; message: string }

function hasRuntimeSource(value: AgentDeckSnapshot): boolean {
  return value.source_mode === "runtime"
}

function hasSafeGuarantees(value: AgentDeckSnapshot): boolean {
  return value.guarantees.read_only === true && value.guarantees.ui_dispatch === false
}

export async function loadAgentDeckSnapshot(): Promise<RuntimeState> {
  try {
    const response = await fetch("/agent-deck.snapshot.json", { cache: "no-store" })
    if (!response.ok) {
      return { kind: "unavailable", message: "尚未生成 Agent Deck 安全快照。" }
    }

    const value: unknown = await response.json()
    if (!isAgentDeckSnapshot(value)) {
      return { kind: "invalid", message: "Agent Deck 快照格式无效，已拒绝展示。" }
    }
    if (!hasRuntimeSource(value)) {
      return { kind: "invalid", message: "Agent Deck 快照不是运行时数据，已拒绝展示。" }
    }
    if (!hasSafeGuarantees(value)) {
      return { kind: "invalid", message: "Agent Deck 快照安全保证无效，已拒绝展示。" }
    }

    return { kind: "live", snapshot: value }
  } catch {
    return { kind: "unavailable", message: "无法读取实时 Agent Deck 快照。" }
  }
}
