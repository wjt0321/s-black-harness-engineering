import { ClipboardList, LockKeyhole, Route } from "lucide-react"
import type { DeckTask } from "@/lib/agent-deck-types"

const proposalSteps = [
  { title: "Pi · 分析与规划", detail: "澄清目标、拆分工作并列出验收要点。" },
  { title: "OMP · 实现与验证", detail: "按已确认计划完成实现与测试。" },
  { title: "Pi · 审阅与汇总", detail: "核对结果、证据和验收建议。" },
]

export function TaskWorkspace({ draftGoal, tasks }: { draftGoal: string | null; tasks: DeckTask[] }) {
  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-center gap-2">
        <ClipboardList className="size-5 text-amber-300" />
        <div>
          <h2 className="text-lg font-semibold">任务工作区</h2>
          <p className="text-sm text-zinc-400">先理解目标和协作方式，再进入既有受控流程。</p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <article className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
          <div className="flex items-center gap-2">
            <Route className="size-4 text-amber-300" />
            <h3 className="font-medium">当前任务草案</h3>
          </div>
          {draftGoal ? (
            <>
              <p className="mt-3 rounded-lg bg-zinc-900 p-3 text-sm text-zinc-200">{draftGoal}</p>
              <ol className="mt-4 space-y-3">
                {proposalSteps.map((step, index) => (
                  <li key={step.title} className="flex gap-3">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-amber-400/15 text-xs text-amber-200">{index + 1}</span>
                    <div>
                      <p className="font-medium">{step.title} <span className="ml-1 rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-normal text-zinc-400">待正式派发</span></p>
                      <p className="mt-1 text-sm text-zinc-400">{step.detail}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <p className="mt-4 flex gap-2 text-sm text-amber-100"><LockKeyhole className="mt-0.5 size-4 shrink-0 text-amber-300" />未写入任务账本，未调用主 Agent，也没有启动 Pi/OMP。</p>
            </>
          ) : (
            <p className="mt-3 text-sm text-zinc-400">写下目标并生成草案后，这里会展示团队接力建议。现在不会启动任何 Agent。</p>
          )}
        </article>

        <article className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-medium">已登记任务</h3>
            <span className="text-xs text-zinc-500">Harness 安全投影</span>
          </div>
          {tasks.length === 0 ? (
            <p className="mt-3 text-sm text-zinc-400">任务账本中暂时没有可安全展示的任务。</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {tasks.map((task) => (
                <li key={task.task_id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{task.title_zh}</p>
                      <p className="mt-1 text-xs text-zinc-500">{task.task_id} · {task.assignee_label_zh}</p>
                    </div>
                    <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-200">{task.status_label_zh}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  )
}
