import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"

const root = process.cwd()
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"))
const dist = path.resolve(process.argv[2] || "dist")
const out = path.resolve(process.argv[3] || "platform-packages")

const packages = [
  ["agentswarm-darwin-arm64", "@vrsen/openswarm-cli-darwin-arm64", "darwin", "arm64", "agentswarm"],
  ["agentswarm-darwin-x64", "@vrsen/openswarm-cli-darwin-x64", "darwin", "x64", "agentswarm"],
  ["agentswarm-darwin-x64-baseline", "@vrsen/openswarm-cli-darwin-x64-baseline", "darwin", "x64", "agentswarm"],
  ["agentswarm-linux-arm64", "@vrsen/openswarm-cli-linux-arm64", "linux", "arm64", "agentswarm"],
  ["agentswarm-linux-arm64-musl", "@vrsen/openswarm-cli-linux-arm64-musl", "linux", "arm64", "agentswarm"],
  ["agentswarm-linux-x64", "@vrsen/openswarm-cli-linux-x64", "linux", "x64", "agentswarm"],
  ["agentswarm-linux-x64-baseline", "@vrsen/openswarm-cli-linux-x64-baseline", "linux", "x64", "agentswarm"],
  ["agentswarm-linux-x64-baseline-musl", "@vrsen/openswarm-cli-linux-x64-baseline-musl", "linux", "x64", "agentswarm"],
  ["agentswarm-linux-x64-musl", "@vrsen/openswarm-cli-linux-x64-musl", "linux", "x64", "agentswarm"],
  ["agentswarm-windows-arm64.exe", "@vrsen/openswarm-cli-windows-arm64", "win32", "arm64", "agentswarm.exe"],
  ["agentswarm-windows-x64.exe", "@vrsen/openswarm-cli-windows-x64", "win32", "x64", "agentswarm.exe"],
  ["agentswarm-windows-x64-baseline.exe", "@vrsen/openswarm-cli-windows-x64-baseline", "win32", "x64", "agentswarm.exe"],
]

fs.rmSync(out, { recursive: true, force: true })
fs.mkdirSync(out, { recursive: true })

for (const [asset, name, os, cpu, binary] of packages) {
  const src = path.join(dist, asset)
  if (!fs.existsSync(src)) throw new Error(`missing platform asset: ${src}`)

  const dir = path.join(out, name.replace("@vrsen/", "vrsen-"))
  const bin = path.join(dir, "bin")
  fs.mkdirSync(bin, { recursive: true })
  fs.copyFileSync(src, path.join(bin, binary))
  if (os !== "win32") fs.chmodSync(path.join(bin, binary), 0o755)
  fs.writeFileSync(
    path.join(dir, "package.json"),
    JSON.stringify(
      {
        name,
        version: pkg.version,
        license: pkg.license,
        description: `${pkg.description} (${os} ${cpu} TUI binary)`,
        files: ["bin/"],
        os: [os],
        cpu: [cpu],
        publishConfig: { access: "public" },
      },
      null,
      2,
    ) + "\n",
  )

  const result = spawnSync("npm", ["pack", "--json"], { cwd: dir, encoding: "utf8" })
  if (result.status !== 0) throw new Error(result.stderr || result.stdout)
  const packed = JSON.parse(result.stdout)[0].filename
  fs.renameSync(path.join(dir, packed), path.join(out, packed))
  console.log(path.join(out, packed))
}
