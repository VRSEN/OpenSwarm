import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { platformAssets } from "./platform-assets.mjs"

const version = process.argv[2]
const dist = path.resolve(process.argv[3] || "dist")
const asset = process.argv[4]

if (!version) {
  console.error("usage: node scripts/extract-agentswarm-binaries.mjs <agentswarm-version> [dist] [asset]")
  process.exit(1)
}

const semver = /^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?$/
if (!semver.test(version)) throw new Error(`AgentSwarm CLI version must be an exact semver, got: ${version}`)

const selected = asset ? platformAssets.filter((item) => item.asset === asset) : platformAssets
if (asset && selected.length === 0) throw new Error(`unknown platform asset: ${asset}`)

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: "utf8", ...options })
  if (result.status !== 0) {
    throw new Error([`command failed: ${command} ${args.join(" ")}`, result.stdout, result.stderr].filter(Boolean).join("\n"))
  }
  return result.stdout
}

function pack(item, dir) {
  const output = run("npm", ["pack", `${item.source}@${version}`, "--json", "--pack-destination", dir])
  const packed = JSON.parse(output)
  if (!Array.isArray(packed) || packed.length !== 1 || typeof packed[0].filename !== "string") {
    throw new Error(`unexpected npm pack output for ${item.source}: ${output}`)
  }
  return path.join(dir, packed[0].filename)
}

fs.rmSync(dist, { recursive: true, force: true })
fs.mkdirSync(dist, { recursive: true })

for (const item of selected) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "openswarm-agentswarm-"))
  try {
    const tarball = pack(item, tmp)
    const extracted = path.join(tmp, "package")
    run("tar", ["-xzf", tarball, "-C", tmp])

    const src = path.join(extracted, "bin", item.binary)
    if (!fs.existsSync(src)) throw new Error(`${item.source}@${version} is missing bin/${item.binary}`)

    const out = path.join(dist, item.asset)
    fs.copyFileSync(src, out)
    if (item.os !== "win32") fs.chmodSync(out, 0o755)
    console.log(`${item.source}@${version} -> ${out}`)
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}
