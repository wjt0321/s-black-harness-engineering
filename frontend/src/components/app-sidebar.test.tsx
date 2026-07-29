import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AppSidebar } from "./app-sidebar"

describe("AppSidebar", () => {
  it("labels the product navigation in Chinese", () => {
    render(<AppSidebar />)

    expect(screen.getByRole("navigation", { name: "主导航" })).toBeInTheDocument()
    expect(screen.getByText("自动化")).toBeInTheDocument()
    expect(screen.getByText("插件")).toBeInTheDocument()
  })
})
