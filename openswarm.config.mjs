import os from "node:os"
import path from "node:path"

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
  return {
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
    AGENTSWARM_PRODUCT_TUI_LOGO_LEFT: JSON.stringify(productTuiLogoLeft),
    AGENTSWARM_PRODUCT_TUI_LOGO_RIGHT: JSON.stringify(productTuiLogoRight),
    AGENTSWARM_PRODUCT_WORDMARK_LINES: JSON.stringify(productWordmarkLines),
    AGENTSWARM_PRODUCT_PYTHON_ENVIRONMENT: "standalone",
    AGENTSWARM_PRODUCT_ENABLE_ADDONS: "true",
    AGENTSWARM_PRODUCT_ADDONS: JSON.stringify(productAddons),
    AGENTSWARM_PRODUCT_STATE_ROOT: opts.stateRoot ?? resolveStateRoot(opts.env),
    AGENTSWARM_PRODUCT_VERSION: opts.version,
  }
}

export default {
  product,
  productTuiLogoLeft,
  productTuiLogoRight,
  productWordmarkLines,
  productAddons,
  resolveStateRoot,
  getProductEnv,
}
