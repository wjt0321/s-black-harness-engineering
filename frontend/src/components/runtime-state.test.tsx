import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { RuntimeStatePanel } from "./runtime-state"

describe("RuntimeStatePanel", () => {
  it("does not turn an unavailable snapshot into an execution affordance", () => {
    render(<RuntimeStatePanel state={{ kind: "unavailable", message: "尚未生成 Agent Deck 安全快照。" }} />)

    expect(screen.getByText("尚未生成 Agent Deck 安全快照。")).toBeInTheDocument()
    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })
})
