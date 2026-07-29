import { AlertTriangle, LoaderCircle } from "lucide-react"
import type { RuntimeState } from "@/lib/load-agent-deck-snapshot"

export function RuntimeStatePanel({ state }: { state: Exclude<RuntimeState, { kind: "live" }> }) {
  if (state.kind === "loading") {
    return (
      <div className="mt-5 flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-300">
        <LoaderCircle className="size-4 animate-spin text-amber-300" />正在读取安全快照…
      </div>
    )
  }

  return (
    <div className="mt-5 flex items-start gap-2 rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-300">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-300" />
      <p>{state.message}</p>
    </div>
  )
}
