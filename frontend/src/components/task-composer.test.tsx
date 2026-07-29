import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"
import { TaskComposer } from "./task-composer"

describe("TaskComposer", () => {
  it("keeps a natural-language goal as a browser-session draft without dispatching it", async () => {
    const user = userEvent.setup()
    render(<TaskComposer />)

    await user.type(screen.getByLabelText("任务目标"), "审查当前项目的测试失败原因")
    await user.click(screen.getByRole("button", { name: "生成协作草案" }))

    expect(sessionStorage.getItem("agent-deck/task-draft/v1")).toBe("审查当前项目的测试失败原因")
    expect(screen.getByText("协作草案已保存在当前浏览器会话中；尚未写入任务账本或派发给 Agent。")).toBeInTheDocument()
    expect(screen.queryByText("立即执行")).not.toBeInTheDocument()
  })
})
