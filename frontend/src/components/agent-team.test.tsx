import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import fixture from "@/fixtures/agent-deck.fixture.json"
import { AgentTeam } from "./agent-team"

describe("AgentTeam", () => {
  it("shows Pi and OMP as pilot members while keeping three adapters pending", () => {
    render(<AgentTeam agents={fixture.agents} />)

    expect(screen.getByText("Pi")).toBeInTheDocument()
    expect(screen.getByText("OMP")).toBeInTheDocument()
    expect(screen.getAllByText("待接入")).toHaveLength(3)
    expect(screen.queryByText("立即执行")).not.toBeInTheDocument()
  })

  it("preserves a stale live status exactly instead of inferring readiness", () => {
    render(<AgentTeam agents={[
      { ...fixture.agents[0], status: "busy", status_label_zh: "已连接，存在未绑定会话", readiness_status: "stale", safe_summary_zh: "观察已超过 TTL。" },
      { ...fixture.agents[1], status: "stale", status_label_zh: "状态已过期", readiness_status: "stale", safe_summary_zh: "观察已超过 TTL。" },
    ]} />)

    expect(screen.getByText("已连接，存在未绑定会话")).toBeInTheDocument()
    expect(screen.getByText("状态已过期")).toBeInTheDocument()
    expect(screen.queryByText("空闲")).not.toBeInTheDocument()
  })
})
