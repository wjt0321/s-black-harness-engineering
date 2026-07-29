import {
  Blocks,
  LayoutDashboard,
  ListTodo,
  PackageCheck,
  Settings,
  Sparkles,
  Users,
} from "lucide-react"

const navigation = [
  ["新建任务", ListTodo],
  ["任务看板", LayoutDashboard],
  ["Agent 团队", Users],
  ["交付与验收", PackageCheck],
  ["自动化", Sparkles],
  ["插件", Blocks],
  ["设置", Settings],
] as const

export function AppSidebar() {
  return (
    <aside className="border-r border-zinc-800 bg-zinc-900 p-5">
      <h1 className="text-xl font-semibold tracking-tight">Agent Deck<span className="text-amber-300">.</span></h1>
      <p className="mt-1 text-sm text-zinc-500">聚合式 Agent 工作台</p>
      <nav aria-label="主导航" className="mt-8 space-y-1">
        {navigation.map(([label, Icon], index) => (
          <button
            type="button"
            key={label}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${
              index === 0 ? "bg-zinc-800 text-white" : "text-zinc-400 hover:bg-zinc-800"
            }`}
          >
            <Icon className="size-4" />{label}
          </button>
        ))}
      </nav>
      <div className="mt-10 border-t border-zinc-800 pt-5">
        <p className="text-xs uppercase tracking-wider text-zinc-500">项目</p>
        <p className="mt-2 rounded-lg bg-zinc-800 px-3 py-2 text-sm">Agent Runtime</p>
      </div>
    </aside>
  )
}
