// S-BLACK 项目级 OMP 扩展：发布只读状态，并消费一次性受控工作项。
const { createLiveStatusExtension } = require("../../integrations/pi_omp_live_status/publisher.cjs")
const { createControlledDispatchExtension } = require("../../integrations/pi_omp_live_status/controlled_dispatch.cjs")

export default function register(pi) {
  createLiveStatusExtension(pi, {
    profileId: "omp-local",
    bindingRelativePath: "adapters/external-agent-live-status-binding.omp-local.json",
    extensionFile: __filename,
  })
  createControlledDispatchExtension(pi, {
    profileId: "omp-local",
    bindingRelativePath: "adapters/external-agent-dispatch-binding.omp-local.json",
    extensionFile: __filename,
  })
}
