// S-BLACK 项目级 Pi 状态扩展：仅发布固定本地快照，不读取会话内容。
const { createLiveStatusExtension } = require("../../integrations/pi_omp_live_status/publisher.cjs")

export default function register(pi) {
  createLiveStatusExtension(pi, {
    profileId: "pi-local",
    bindingRelativePath: "adapters/external-agent-live-status-binding.pi-local.json",
    extensionFile: __filename,
  })
}
