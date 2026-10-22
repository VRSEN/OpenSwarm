import os from "node:os"
import fs from "node:fs"
import path from "node:path"

export const productVersion = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf8")).version
const packageMarketplacePath = new URL("./openswarm.marketplace.json", import.meta.url)
const defaultMarketplace = {
  swarmId: "VRSEN/OpenSwarm",
  parentSwarmId: undefined,
  swarmOrigin: "original",
}
const githubOwnerPattern = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/
const githubRepositoryNamePattern = /^[A-Za-z0-9._-]{1,100}$/

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function readString(value, key, { required = true } = {}) {
  if ((value === undefined || value === "") && !required) return undefined
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`OpenSwarm marketplace metadata ${key} must be a non-empty string`)
  }
  return value.trim()
}

function readGitHubRepo(value, key, opts) {
  const repo = readString(value, key, opts)
  if (repo === undefined) return undefined
  const parts = repo.split("/")
  if (parts.length !== 2) {
    throw new Error(`OpenSwarm marketplace metadata ${key} must be a GitHub owner/repo`)
  }
  const [owner, name] = parts
  if (name.toLowerCase().endsWith(".git")) {
    throw new Error(`OpenSwarm marketplace metadata ${key} must be a GitHub owner/repo`)
  }
  if (!githubOwnerPattern.test(owner) || owner.includes("--") || !githubRepositoryNamePattern.test(name)) {
    throw new Error(`OpenSwarm marketplace metadata ${key} must be a GitHub owner/repo`)
  }
  return repo
}

function marketplacePath(cwd) {
  if (cwd) {
    const projectPath = path.resolve(cwd, "openswarm.marketplace.json")
    if (fs.existsSync(projectPath)) return projectPath
  }
  if (fs.existsSync(packageMarketplacePath)) return packageMarketplacePath
  return undefined
}

function readMarketplaceFileMetadata(cwd) {
  const source = marketplacePath(cwd)
  if (!source) return defaultMarketplace
  let parsed
  try {
    parsed = JSON.parse(fs.readFileSync(source, "utf8"))
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(`OpenSwarm marketplace metadata failed to load: ${message}`)
  }
  if (!isRecord(parsed)) {
    throw new Error("OpenSwarm marketplace metadata must be a JSON object")
  }
  const swarmOrigin = readString(parsed.swarmOrigin, "swarmOrigin")
  if (!["original", "fork", "unknown"].includes(swarmOrigin)) {
    throw new Error("OpenSwarm marketplace metadata swarmOrigin must be original, fork, or unknown")
  }
  const parentSwarmId = readGitHubRepo(parsed.parentSwarmId, "parentSwarmId", { required: false })
  if (swarmOrigin === "fork" && parentSwarmId === undefined) {
    throw new Error("OpenSwarm marketplace metadata parentSwarmId is required for fork swarms")
  }
  return {
    swarmId: readGitHubRepo(parsed.swarmId, "swarmId"),
    parentSwarmId,
    swarmOrigin,
  }
}

const marketplace = readMarketplaceFileMetadata()

// Downstream projects can edit this file to rebrand the launcher and TUI build.
export const product = {
  displayName: "OpenSwarm",
  command: "openswarm",
  packageName: "@vrsen/openswarm",
  launcherPackageName: "@vrsen/openswarm",
  releaseRepo: "VRSEN/OpenSwarm",
  docsUrl: "https://github.com/VRSEN/OpenSwarm",
  issueUrl: "https://github.com/VRSEN/OpenSwarm/issues/new?template=bug-report.yml",
  mdnsDomain: "openswarm.local",
  starterRepo: "VRSEN/OpenSwarm",
  starterFolder: "openswarm",
  entryFiles: "swarm.py,agency.py",
  marketplaceSwarmId: marketplace.swarmId,
  marketplaceParentSwarmId: marketplace.parentSwarmId,
  marketplaceSwarmOrigin: marketplace.swarmOrigin,
}

export const productTuiLogoLeft = [
  "                                    ",
  " ██████╗ ██████╗ ███████╗███╗   ██╗",
  "██╔═══██╗██╔══██╗██╔════╝████╗  ██║",
  "██║   ██║██████╔╝█████╗  ██╔██╗ ██║",
  "██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║",
  "╚██████╔╝██║     ███████╗██║ ╚████║",
  " ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝",
]

export const productTuiLogoRight = [
  "",
  "███████╗██╗    ██╗ █████╗ ██████╗ ███╗   ███╗",
  "██╔════╝██║    ██║██╔══██╗██╔══██╗████╗ ████║",
  "███████╗██║ █╗ ██║███████║██████╔╝██╔████╔██║",
  "╚════██║██║███╗██║██╔══██╗██╔══██╗██║╚██╔╝██║",
  "███████║╚███╔███╔╝██║  ██║██║  ██║██║ ╚═╝ ██║",
  "╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝",
]

export const productWordmarkLines = productTuiLogoLeft.map((line, index) =>
  `${line} ${productTuiLogoRight[index] ?? ""}`.trimEnd(),
)

export const productAddons = [
  { id: "search", title: "Web Search", keys: ["SEARCH_API_KEY"] },
  { id: "anthropic", title: "Anthropic Claude", keys: ["ANTHROPIC_API_KEY"], excludeProviders: ["anthropic"] },
  { id: "composio", title: "Composio", keys: ["COMPOSIO_API_KEY", "COMPOSIO_USER_ID"] },
  { id: "google", title: "Google Gemini", keys: ["GOOGLE_API_KEY"], excludeProviders: ["google"] },
  { id: "fal", title: "Fal.ai", keys: ["FAL_KEY"] },
  { id: "pexels", title: "Pexels", keys: ["PEXELS_API_KEY"] },
  { id: "pixabay", title: "Pixabay", keys: ["PIXABAY_API_KEY"] },
  { id: "unsplash", title: "Unsplash", keys: ["UNSPLASH_ACCESS_KEY"] },
]

export function resolveStateRoot(env = process.env, platform = process.platform, home = os.homedir()) {
  const explicit = env.OPENSWARM_STATE_ROOT && env.OPENSWARM_STATE_ROOT.trim()
  if (explicit) return path.resolve(explicit)
  if (platform === "win32") {
    return path.join(env.APPDATA || path.join(home, "AppData", "Roaming"), "OpenSwarm")
  }
  return path.join(home, ".openswarm")
}

export function getProductEnv(opts = {}) {
  const marketplace = readMarketplaceFileMetadata(opts.cwd ?? process.cwd())
  const activeMarketplace = {
    swarmId: marketplace.swarmId,
    parentSwarmId: marketplace.parentSwarmId,
    swarmOrigin: marketplace.swarmOrigin,
  }
  const env = {
    AGENTSWARM_PRODUCT_DISPLAY_NAME: product.displayName,
    AGENTSWARM_PRODUCT_COMMAND: product.command,
    AGENTSWARM_PRODUCT_PACKAGE_NAME: product.packageName,
    AGENTSWARM_PRODUCT_LAUNCHER_PACKAGE_NAME: product.launcherPackageName,
    AGENTSWARM_PRODUCT_RELEASE_REPO: product.releaseRepo,
    AGENTSWARM_PRODUCT_DOCS_URL: product.docsUrl,
    AGENTSWARM_PRODUCT_ISSUE_URL: product.issueUrl,
    AGENTSWARM_PRODUCT_MDNS_DOMAIN: product.mdnsDomain,
    AGENTSWARM_PRODUCT_STARTER_REPO: product.starterRepo,
    AGENTSWARM_PRODUCT_STARTER_FOLDER: product.starterFolder,
    AGENTSWARM_PRODUCT_ENTRY_FILES: product.entryFiles,
    AGENTSWARM_PRODUCT_SKIP_POST_AUTH_MODEL_SELECTION: "true",
    AGENTSWARM_PRODUCT_HIDE_CONNECT: "true",
    AGENTSWARM_PRODUCT_TUI_LOGO_LEFT: JSON.stringify(productTuiLogoLeft),
    AGENTSWARM_PRODUCT_TUI_LOGO_RIGHT: JSON.stringify(productTuiLogoRight),
    AGENTSWARM_PRODUCT_WORDMARK_LINES: JSON.stringify(productWordmarkLines),
    AGENTSWARM_PRODUCT_PYTHON_ENVIRONMENT: "standalone",
    AGENTSWARM_PRODUCT_ENABLE_ADDONS: "true",
    AGENTSWARM_PRODUCT_ADDONS: JSON.stringify(productAddons),
    AGENTSWARM_PRODUCT_STATE_ROOT: opts.stateRoot ?? resolveStateRoot(opts.env),
    AGENTSWARM_PRODUCT_VERSION: productVersion,
    AGENTSWARM_MARKETPLACE_SWARM_ID: activeMarketplace.swarmId,
    AGENTSWARM_MARKETPLACE_SWARM_ORIGIN: activeMarketplace.swarmOrigin,
  }
  if (activeMarketplace.parentSwarmId) {
    env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID = activeMarketplace.parentSwarmId
  }
  return env
}

export default {
  product,
  productTuiLogoLeft,
  productTuiLogoRight,
  productWordmarkLines,
  productAddons,
  productVersion,
  resolveStateRoot,
  getProductEnv,
}
