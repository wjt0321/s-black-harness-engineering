import { ShieldCheck } from "lucide-react"

export function DeliveryPanel({
  registeredWorkCount,
  summary,
}: {
  registeredWorkCount: number
  summary: string
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="size-5 text-amber-300" />
        <h2 className="text-lg font-semibold">交付与验收</h2>
      </div>
      <p className="mt-3 text-sm text-zinc-300">{summary}</p>
      <p className="mt-4 text-sm text-zinc-500">已登记试运行：{registeredWorkCount} 项。</p>
      <p className="mt-2 text-sm text-zinc-500">最终通过、要求修改与有限放弃仍在既有受控 GUI 中完成。</p>
    </section>
  )
}
