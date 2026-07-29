import { afterEach, describe, expect, it, vi } from "vitest"
import { loadAgentDeckSnapshot } from "./load-agent-deck-snapshot"

const runtimeSnapshot = {
  schema_version: "agent-deck/read-model/v1",
  source_mode: "runtime",
  project: { id: "agent-runtime", name_zh: "Agent Runtime" },
  agents: [],
  registered_work: [],
  timeline: [],
  delivery: { summary_zh: "暂无交付。" },
  guarantees: { read_only: true, ui_dispatch: false },
} as const

describe("loadAgentDeckSnapshot", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("requests the only fixed safe snapshot path without cache", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => runtimeSnapshot })
    vi.stubGlobal("fetch", fetchMock)

    await loadAgentDeckSnapshot()

    expect(fetchMock).toHaveBeenCalledWith("/agent-deck.snapshot.json", { cache: "no-store" })
  })

  it("rejects a fixture instead of presenting it as live runtime data", async () => {
    const fixture = { ...runtimeSnapshot, source_mode: "fixture" }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => fixture }))

    await expect(loadAgentDeckSnapshot()).resolves.toEqual({
      kind: "invalid",
      message: "Agent Deck 快照不是运行时数据，已拒绝展示。",
    })
  })

  it("rejects a snapshot whose guarantees would allow UI dispatch", async () => {
    const unsafe = { ...runtimeSnapshot, guarantees: { read_only: true, ui_dispatch: true } }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => unsafe }))

    await expect(loadAgentDeckSnapshot()).resolves.toEqual({
      kind: "invalid",
      message: "Agent Deck 快照安全保证无效，已拒绝展示。",
    })
  })

  it("returns an honest unavailable state for a missing snapshot", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }))

    await expect(loadAgentDeckSnapshot()).resolves.toEqual({
      kind: "unavailable",
      message: "尚未生成 Agent Deck 安全快照。",
    })
  })
})
