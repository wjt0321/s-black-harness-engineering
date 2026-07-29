import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { TaskWorkspace } from "./task-workspace"

describe("TaskWorkspace", () => {
  it("shows a transparent Pi to OMP to Pi proposal without an execution entry", () => {
    render(
      <TaskWorkspace
        draftGoal="为项目增加登录页面并测试"
        tasks={[
          {
            task_id: "task-20260729-001",
            title_zh: "实现任务工作区",
            status: "in_progress",
            status_label_zh: "进行中",
            assignee_label_zh: "已分配",
            updated_at: "2026-07-29T11:30:00Z",
          },
        ]}
      />,
    )

    expect(screen.getByText("当前任务草案")).toBeInTheDocument()
    expect(screen.getByText("Pi · 分析与规划")).toBeInTheDocument()
    expect(screen.getByText("OMP · 实现与验证")).toBeInTheDocument()
    expect(screen.getByText("Pi · 审阅与汇总")).toBeInTheDocument()
    expect(screen.getByText("未写入任务账本，未调用主 Agent，也没有启动 Pi/OMP。")).toBeInTheDocument()
    expect(screen.getByText("实现任务工作区")).toBeInTheDocument()
    expect(screen.getByText("进行中")).toBeInTheDocument()
    expect(screen.queryByText("立即执行")).not.toBeInTheDocument()
  })
})

  it("shows a formally registered task as waiting for main-agent planning", () => {
    render(
      <TaskWorkspace
        draftGoal={null}
        tasks={[
          {
            task_id: "task-20260729-003",
            title_zh: "正式登记的平台任务",
            status: "planned",
            status_label_zh: "等待规划",
            planning_state_zh: "等待主控 Agent 规划",
            assignee_label_zh: "已分配",
            updated_at: "2026-07-29T12:00:00Z",
          },
        ]}
      />,
    )

    expect(screen.getByText("正式登记的平台任务")).toBeInTheDocument()
    expect(screen.getByText("等待主控 Agent 规划")).toBeInTheDocument()
    expect(screen.queryByText("启动主控 Agent")).not.toBeInTheDocument()
  })
