import { useEffect, useState } from "react"
import fixture from "@/fixtures/agent-deck.fixture.json"
import { AppSidebar } from "@/components/app-sidebar"
import { AgentTeam } from "@/components/agent-team"
import { CollaborationTimeline } from "@/components/collaboration-timeline"
import { DeliveryPanel } from "@/components/delivery-panel"
import { RuntimeStatePanel } from "@/components/runtime-state"
import { TaskComposer } from "@/components/task-composer"
import { TaskWorkspace } from "@/components/task-workspace"
import type { AgentDeckSnapshot } from "@/lib/agent-deck-types"
import { loadAgentDeckSnapshot, type RuntimeState } from "@/lib/load-agent-deck-snapshot"

type WorkbenchState = RuntimeState | { kind: "fixture"; snapshot: AgentDeckSnapshot }
const demoSnapshot = fixture as AgentDeckSnapshot

function initialWorkbenchState(): WorkbenchState {
  return new URLSearchParams(window.location.search).has("demo")
    ? { kind: "fixture", snapshot: demoSnapshot }
    : { kind: "loading" }
}

export default function App() {
  const [runtime, setRuntime] = useState<WorkbenchState>(initialWorkbenchState)
  const [draftGoal, setDraftGoal] = useState<string | null>(null)

  useEffect(() => {
    if (runtime.kind === "fixture") return
    void loadAgentDeckSnapshot().then(setRuntime)
  }, [runtime.kind])

  const snapshot = runtime.kind === "live" || runtime.kind === "fixture" ? runtime.snapshot : null
  const isFixture = runtime.kind === "fixture"

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 md:grid md:grid-cols-[260px_1fr]">
      <AppSidebar />
      <main aria-label="Agent Deck 工作台" className="p-5 md:p-8">
        <header className="mb-7">
          <p className="text-sm text-amber-200">本地优先 · Harness 受控底座</p>
          <h2 className="mt-1 text-3xl font-semibold">把目标交给团队</h2>
          <p className="mt-2 text-zinc-400">发布目标、观察协作、验收结果。P0 不会从此界面直接派发任何 Agent。</p>
        </header>

        <TaskComposer onProposalChange={setDraftGoal} />
        {runtime.kind !== "live" && runtime.kind !== "fixture" && <RuntimeStatePanel state={runtime} />}
        {snapshot && (
          <>
            <div className="mt-5 flex items-center gap-2 text-sm">
              <span className={`rounded-full px-3 py-1 ${isFixture ? "bg-sky-400/15 text-sky-200" : "bg-emerald-400/15 text-emerald-300"}`}>
                {isFixture ? "演示数据" : "实时快照"}
              </span>
              <span className="text-zinc-500">{snapshot.project.name_zh}</span>
            </div>
            <div className="mt-5"><TaskWorkspace draftGoal={draftGoal} tasks={snapshot.task_queue ?? []} /></div>
            <div className="mt-5"><AgentTeam agents={snapshot.agents} /></div>
            <div className="mt-5 grid gap-5 xl:grid-cols-2">
              <CollaborationTimeline snapshot={snapshot} />
              <DeliveryPanel
                registeredWorkCount={snapshot.registered_work.length}
                summary={snapshot.delivery.summary_zh}
              />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
