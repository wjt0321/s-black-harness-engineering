import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import App from "./App"

describe("Agent Deck application shell", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.history.replaceState({}, "", "/")
  })

  it("renders the Chinese primary navigation and an honest missing-snapshot state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }))
    render(<App />)

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument()
    expect(screen.getByText("新建任务")).toBeInTheDocument()
    expect(screen.getByText("Agent 团队")).toBeInTheDocument()
    expect(await screen.findByText("尚未生成 Agent Deck 安全快照。")).toBeInTheDocument()
  })

  it("labels the explicit local demo fixture instead of calling it a live snapshot", () => {
    window.history.replaceState({}, "", "/?demo=1")
    render(<App />)

    expect(screen.getByText("演示数据")).toBeInTheDocument()
    expect(screen.getAllByText("Pi")).toHaveLength(2)
    expect(screen.queryByText("实时快照")).not.toBeInTheDocument()
  })
})
