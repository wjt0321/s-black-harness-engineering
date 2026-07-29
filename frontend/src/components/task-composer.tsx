import { useState } from "react"
import { Send, Users } from "lucide-react"

const draftStorageKey = "agent-deck/task-draft/v1"

export function TaskComposer() {
  const [goal, setGoal] = useState("")
  const [saved, setSaved] = useState(false)

  function saveDraft() {
    const normalizedGoal = goal.trim()
    if (!normalizedGoal) return
    sessionStorage.setItem(draftStorageKey, normalizedGoal)
    setGoal(normalizedGoal)
    setSaved(true)
  }

  return (
    <section className="rounded-2xl border border-zinc-700 bg-zinc-900/70 p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-zinc-400">当前项目</p>
          <h2 className="text-lg font-semibold">Agent Runtime</h2>
        </div>
        <span className="rounded-full bg-amber-400/15 px-3 py-1 text-sm text-amber-200">
          <Users className="mr-1 inline size-4" />协同模式（P0 仅试运行）
        </span>
      </div>
      <label className="sr-only" htmlFor="goal">任务目标</label>
      <textarea
        id="goal"
        value={goal}
        onChange={(event) => {
          setGoal(event.target.value)
          setSaved(false)
        }}
        placeholder="告诉 Agent 团队你想完成什么…"
        className="min-h-28 w-full resize-none rounded-xl border border-zinc-700 bg-zinc-950 p-4 text-zinc-100"
      />
      <div className="mt-3 flex items-center justify-between gap-3">
        <div className="text-sm text-zinc-400">
          队友：<span className="text-zinc-200">Pi</span> · <span className="text-zinc-200">OMP</span>
        </div>
        <button
          type="button"
          onClick={saveDraft}
          disabled={!goal.trim()}
          className="rounded-lg bg-amber-400 px-4 py-2 font-medium text-zinc-950 disabled:opacity-50"
        >
          <Send className="mr-1 inline size-4" />保存任务草稿
        </button>
      </div>
      {saved && <p className="mt-3 text-sm text-emerald-300">任务草稿已保存在当前浏览器会话中，尚未派发给 Agent。</p>}
    </section>
  )
}
