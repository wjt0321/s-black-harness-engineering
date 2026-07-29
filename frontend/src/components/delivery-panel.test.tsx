import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { DeliveryPanel } from "./delivery-panel"

describe("DeliveryPanel", () => {
  it("keeps final approval in the existing controlled GUI", () => {
    render(<DeliveryPanel registeredWorkCount={2} summary="等待人工审阅。" />)

    expect(screen.getByText("等待人工审阅。")).toBeInTheDocument()
    expect(screen.getByText("最终通过、要求修改与有限放弃仍在既有受控 GUI 中完成。")).toBeInTheDocument()
    expect(screen.queryByText("批准并执行")).not.toBeInTheDocument()
  })
})
