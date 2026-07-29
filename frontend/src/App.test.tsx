import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import App from "./App"
vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok:false}))
describe("Agent Deck application shell",()=>{it("renders the Chinese primary navigation",()=>{render(<App/>);expect(screen.getByRole("navigation",{name:"主导航"})).toBeInTheDocument();expect(screen.getByText("新建任务")).toBeInTheDocument();expect(screen.getByText("Agent 团队")).toBeInTheDocument()})})