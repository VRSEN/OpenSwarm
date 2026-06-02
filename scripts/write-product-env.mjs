import { getProductEnv } from "../openswarm.config.mjs"

function stableProductEnv() {
  const env = getProductEnv({
    stateRoot: "__OPENSWARM_STATE_ROOT__",
    version: "__OPENSWARM_VERSION__",
  })
  delete env.AGENTSWARM_PRODUCT_STATE_ROOT
  delete env.AGENTSWARM_PRODUCT_VERSION
  return env
}

if (process.argv.includes("--json")) {
  console.log(JSON.stringify(stableProductEnv(), null, 2))
  process.exit(0)
}

const version = process.env.OPENSWARM_PRODUCT_VERSION || process.env.npm_package_version
if (!version) {
  console.error("OPENSWARM_PRODUCT_VERSION or npm_package_version is required to write OpenSwarm product env.")
  process.exit(1)
}

const env = getProductEnv({ version })

for (const [key, value] of Object.entries(env)) {
  if (key === "AGENTSWARM_PRODUCT_STATE_ROOT") continue
  if (value === undefined) continue
  console.log(`${key}<<__OPENSWARM_ENV__`)
  console.log(value)
  console.log("__OPENSWARM_ENV__")
}
