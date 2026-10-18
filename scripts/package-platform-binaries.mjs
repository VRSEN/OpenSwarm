import fs from "node:fs"
import path from "node:path"
import { spawnSync } from "node:child_process"
import { platformAssets } from "./platform-assets.mjs"

const root = process.cwd()
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"))
const dist = path.resolve(process.argv[2] || "dist")
const out = path.resolve(process.argv[3] || "platform-packages")

fs.rmSync(out, { recursive: true, force: true })
fs.mkdirSync(out, { recursive: true })

for (const item of platformAssets) {
  const src = path.join(dist, item.asset)
  if (!fs.existsSync(src)) throw new Error(`missing platform asset: ${src}`)

  const dir = path.join(out, item.target.replace("@vrsen/", "vrsen-"))
  const bin = path.join(dir, "bin")
  fs.mkdirSync(bin, { recursive: true })
  fs.copyFileSync(src, path.join(bin, item.binary))
  if (item.os !== "win32") fs.chmodSync(path.join(bin, item.binary), 0o755)
  fs.writeFileSync(
    path.join(dir, "package.json"),
    JSON.stringify(
      {
        name: item.target,
        version: pkg.version,
        license: pkg.license,
        description: `${pkg.description} (${item.os} ${item.cpu} TUI binary)`,
        files: ["bin/"],
        os: [item.os],
        cpu: [item.cpu],
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
