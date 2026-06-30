import { getProductEnv } from "../openswarm.config.mjs"

function stableProductEnv() {
  const env = getProductEnv({
    stateRoot: "__OPENSWARM_STATE_ROOT__",
  })
  delete env.AGENTSWARM_PRODUCT_STATE_ROOT
  delete env.AGENTSWARM_PRODUCT_VERSION
  return env
}

if (process.argv.includes("--json")) {
  console.log(JSON.stringify(stableProductEnv(), null, 2))
  process.exit(0)
}

const env = getProductEnv()

for (const [key, value] of Object.entries(env)) {
  if (key === "AGENTSWARM_PRODUCT_STATE_ROOT") continue
  if (value === undefined) continue
  console.log(`${key}<<__OPENSWARM_ENV__`)
  console.log(value)
  console.log("__OPENSWARM_ENV__")
}
