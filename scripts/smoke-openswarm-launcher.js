#!/usr/bin/env node
'use strict'

const assert = require('assert')
const cp = require('child_process')
const fs = require('fs')
const os = require('os')
const path = require('path')
const vm = require('vm')
const { pathToFileURL } = require('url')

const root = path.dirname(__dirname)
const launcher = path.join(root, 'bin', 'openswarm')
const configPath = path.join(root, 'openswarm.config.mjs')
const marketplacePath = path.join(root, 'openswarm.marketplace.json')
const productEnvPath = path.join(root, 'openswarm.product-env.json')
const envWriter = path.join(root, 'scripts', 'write-product-env.mjs')
const marketplaceEnvKeys = [
  'OPENSWARM_MARKETPLACE_SWARM_ID',
  'OPENSWARM_MARKETPLACE_PARENT_SWARM_ID',
  'OPENSWARM_MARKETPLACE_SWARM_ORIGIN',
  'AGENTSWARM_MARKETPLACE_SWARM_ID',
  'AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID',
  'AGENTSWARM_MARKETPLACE_SWARM_ORIGIN',
]

function cleanEnv(extra = {}) {
  const env = { ...process.env, ...extra }
  for (const key of marketplaceEnvKeys) {
    if (!(key in extra)) delete env[key]
  }
  return env
}

async function loadConfig() {
  return import(pathToFileURL(configPath).href)
}

function assertNoDownloadSource() {
  const launcherSource = fs.readFileSync(launcher, 'utf8')
  assert.equal(launcherSource.includes('http'), false, 'launcher still contains HTTP download code')
  assert.equal(launcherSource.includes('OPENSWARM_TUI_URL'), false, 'launcher still reads OPENSWARM_TUI_URL')

  const runUtilsSource = fs.readFileSync(path.join(root, 'run_utils.py'), 'utf8')
  assert.equal(runUtilsSource.includes('urlretrieve'), false, 'run_utils.py still downloads release assets')
  assert.equal(runUtilsSource.includes('download=True'), false, 'run_utils.py still requests TUI binary downloads')
  assert.equal(runUtilsSource.includes('releases/latest/download'), false, 'run_utils.py still references GitHub release downloads')
}

function assertPlatformDependencyVersions() {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'))
  assert.equal(lock.packages[''].version, pkg.version, 'package-lock root version does not match package.json')

  const deps = Object.entries(pkg.optionalDependencies || {}).filter(([name]) => name.startsWith('@vrsen/openswarm-cli-'))
  assert.equal(deps.length, 12, 'expected 12 OpenSwarm platform optional dependencies')

  for (const [name, version] of deps) {
    assert.equal(version, pkg.version, `${name} optionalDependency version must match package.json version`)
    const entry = lock.packages[`node_modules/${name}`]
    assert.ok(entry, `package-lock is missing ${name}`)
    assert.equal(entry.version, pkg.version, `${name} package-lock version must match package.json version`)
    assert.equal(entry.license, pkg.license, `${name} package-lock license must match package.json license`)
    const unscoped = name.replace('@vrsen/', '')
    const [, platform, arch] = unscoped.match(/^openswarm-cli-(darwin|linux|windows)-(arm64|x64)(?:-|$)/) || []
    assert.ok(platform && arch, `${name} has unexpected platform package name`)
    assert.deepEqual(entry.cpu, [arch], `${name} package-lock cpu is incomplete`)
    assert.deepEqual(entry.os, [platform === 'windows' ? 'win32' : platform], `${name} package-lock os is incomplete`)
    assert.equal(
      entry.resolved,
      `https://registry.npmjs.org/${name}/-/${unscoped}-${pkg.version}.tgz`,
      `${name} package-lock resolved URL is incomplete`,
    )
  }
}

function assertProductAddons(env) {
  assert.equal(env.AGENTSWARM_PRODUCT_ENABLE_ADDONS, 'true', 'AGENTSWARM_PRODUCT_ENABLE_ADDONS not enabled')
  assert.ok(env.AGENTSWARM_PRODUCT_ADDONS, 'AGENTSWARM_PRODUCT_ADDONS not set')

  const addons = JSON.parse(env.AGENTSWARM_PRODUCT_ADDONS)
  assert.deepEqual(addons, [
    { id: 'search', title: 'Web Search', keys: ['SEARCH_API_KEY'] },
    { id: 'anthropic', title: 'Anthropic Claude', keys: ['ANTHROPIC_API_KEY'], excludeProviders: ['anthropic'] },
    { id: 'composio', title: 'Composio', keys: ['COMPOSIO_API_KEY', 'COMPOSIO_USER_ID'] },
    { id: 'google', title: 'Google Gemini', keys: ['GOOGLE_API_KEY'], excludeProviders: ['google'] },
    { id: 'fal', title: 'Fal.ai', keys: ['FAL_KEY'] },
    { id: 'pexels', title: 'Pexels', keys: ['PEXELS_API_KEY'] },
    { id: 'pixabay', title: 'Pixabay', keys: ['PIXABAY_API_KEY'] },
    { id: 'unsplash', title: 'Unsplash', keys: ['UNSPLASH_ACCESS_KEY'] },
  ])
}

function loadLauncherResolver(opts) {
  const source = fs.readFileSync(launcher, 'utf8').split('\nconst openswarmBinary = ')[0]
  const fakeFs = {
    ...fs,
    existsSync(target) {
      if (target === '/etc/alpine-release') return Boolean(opts.musl)
      return fs.existsSync(target)
    },
    readFileSync(target, encoding) {
      if (target === '/proc/cpuinfo') return opts.avx2 ? 'flags\t: avx2\n' : 'flags\t: sse4_2\n'
      return fs.readFileSync(target, encoding)
    },
  }
  const fakeChild = {
    spawnSync(command) {
      if (command === 'sysctl') {
        return { status: 0, stdout: opts.avx2 ? '1\n' : '0\n', stderr: '' }
      }
      if (command === 'ldd') {
        return { status: 0, stdout: opts.musl ? 'musl libc\n' : 'glibc\n', stderr: '' }
      }
      return { status: opts.avx2 ? 0 : 1, stdout: opts.avx2 ? 'True\n' : 'False\n', stderr: '' }
    },
  }
  const sandbox = {
    __filename: launcher,
    console,
    module: { exports: {} },
    process: { ...process, arch: opts.arch, platform: opts.platform },
    require(name) {
      if (name === 'fs') return fakeFs
      if (name === 'child_process') return fakeChild
      if (name === 'path') return path
      if (name === 'url') return require('url')
      return require(name)
    },
  }
  vm.runInNewContext(`${source}\nmodule.exports = { platformPackages, supportsAvx2, isMusl }`, sandbox, {
    filename: launcher,
  })
  return sandbox.module.exports
}

function assertPlatformPackageOrdering() {
  const names = (opts) => loadLauncherResolver(opts).platformPackages().map((item) => item.name)

  assert.deepEqual(names({ platform: 'linux', arch: 'x64', musl: true, avx2: false }), [
    '@vrsen/openswarm-cli-linux-x64-baseline-musl',
    '@vrsen/openswarm-cli-linux-x64-musl',
    '@vrsen/openswarm-cli-linux-x64-baseline',
    '@vrsen/openswarm-cli-linux-x64',
  ])
  assert.deepEqual(names({ platform: 'linux', arch: 'x64', musl: true, avx2: true }), [
    '@vrsen/openswarm-cli-linux-x64-musl',
    '@vrsen/openswarm-cli-linux-x64-baseline-musl',
    '@vrsen/openswarm-cli-linux-x64',
    '@vrsen/openswarm-cli-linux-x64-baseline',
  ])
  assert.deepEqual(names({ platform: 'linux', arch: 'x64', musl: false, avx2: false }), [
    '@vrsen/openswarm-cli-linux-x64-baseline',
    '@vrsen/openswarm-cli-linux-x64',
    '@vrsen/openswarm-cli-linux-x64-baseline-musl',
    '@vrsen/openswarm-cli-linux-x64-musl',
  ])
  assert.deepEqual(names({ platform: 'linux', arch: 'arm64', musl: true, avx2: false }), [
    '@vrsen/openswarm-cli-linux-arm64-musl',
    '@vrsen/openswarm-cli-linux-arm64',
  ])
  assert.deepEqual(names({ platform: 'darwin', arch: 'x64', musl: false, avx2: false }), [
    '@vrsen/openswarm-cli-darwin-x64-baseline',
    '@vrsen/openswarm-cli-darwin-x64',
  ])
  assert.deepEqual(names({ platform: 'darwin', arch: 'x64', musl: false, avx2: true }), [
    '@vrsen/openswarm-cli-darwin-x64',
    '@vrsen/openswarm-cli-darwin-x64-baseline',
  ])
  assert.deepEqual(names({ platform: 'win32', arch: 'x64', musl: false, avx2: false }), [
    '@vrsen/openswarm-cli-windows-x64-baseline',
    '@vrsen/openswarm-cli-windows-x64',
  ])
}

async function assertStateRoot() {
  const config = await loadConfig()
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  assert.equal(
    config.resolveStateRoot({}, 'linux', '/home/tester'),
    path.join('/home/tester', '.openswarm'),
  )
  assert.equal(
    config.resolveStateRoot({}, 'darwin', '/Users/tester'),
    path.join('/Users/tester', '.openswarm'),
  )
  assert.equal(
    config.resolveStateRoot({ APPDATA: 'C:\\Users\\tester\\AppData\\Roaming' }, 'win32', 'C:\\Users\\tester'),
    path.join('C:\\Users\\tester\\AppData\\Roaming', 'OpenSwarm'),
  )
  assert.equal(
    config.resolveStateRoot({ OPENSWARM_STATE_ROOT: '/tmp/openswarm-state' }, 'linux', '/home/tester'),
    path.resolve('/tmp/openswarm-state'),
  )

  const env = config.getProductEnv({
    env: {},
    stateRoot: path.join('/home/tester', '.openswarm'),
  })
  assert.equal(env.AGENTSWARM_PRODUCT_DISPLAY_NAME, 'OpenSwarm')
  assert.equal(env.AGENTSWARM_PRODUCT_STATE_ROOT, path.join('/home/tester', '.openswarm'))
  assert.equal(env.AGENTSWARM_PRODUCT_VERSION, pkg.version)
  assert.equal(env.AGENTSWARM_PRODUCT_HIDE_CONNECT, 'true')
  assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'VRSEN/OpenSwarm')
  assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, undefined)
  assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'original')
  assertProductAddons(env)

  const ambientEnv = config.getProductEnv({
    env: {
      OPENSWARM_MARKETPLACE_SWARM_ID: 'someone/custom-swarm',
      OPENSWARM_MARKETPLACE_PARENT_SWARM_ID: 'VRSEN/OpenSwarm',
      OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'fork',
      AGENTSWARM_MARKETPLACE_SWARM_ID: 'stale/swarm',
      AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID: 'stale/parent',
      AGENTSWARM_MARKETPLACE_SWARM_ORIGIN: 'unknown',
    },
    stateRoot: path.join('/home/tester', '.openswarm'),
  })
  assert.equal(ambientEnv.AGENTSWARM_MARKETPLACE_SWARM_ID, 'VRSEN/OpenSwarm')
  assert.equal(ambientEnv.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, undefined)
  assert.equal(ambientEnv.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'original')

  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-project-marketplace-'))
  try {
    const fullOwner = 'a'.repeat(39)
    const fullRepo = 'b'.repeat(100)
    fs.writeFileSync(
      path.join(project, 'openswarm.marketplace.json'),
      `${JSON.stringify({
        swarmId: `${fullOwner}/${fullRepo}`,
        parentSwarmId: 'VRSEN/OpenSwarm',
        swarmOrigin: 'fork',
      })}\n`,
      'utf8',
    )
    const fullEnv = config.getProductEnv({
      cwd: project,
      env: {
        OPENSWARM_MARKETPLACE_SWARM_ID: 'ignored/runtime',
        OPENSWARM_MARKETPLACE_PARENT_SWARM_ID: 'ignored/runtime-parent',
        OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'original',
      },
      stateRoot: path.join('/home/tester', '.openswarm'),
    })
    assert.equal(fullEnv.AGENTSWARM_MARKETPLACE_SWARM_ID, `${fullOwner}/${fullRepo}`)
    assert.equal(fullEnv.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(fullEnv.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'fork')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }

  const parentProject = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-parent-marketplace-'))
  try {
    fs.writeFileSync(
      path.join(parentProject, 'openswarm.marketplace.json'),
      '{"swarmId":"owner/child-swarm","parentSwarmId":"owner/parent-swarm","swarmOrigin":"fork"}\n',
      'utf8',
    )
    const forkEnv = config.getProductEnv({
      cwd: parentProject,
      env: {},
      stateRoot: path.join('/home/tester', '.openswarm'),
    })
    assert.equal(forkEnv.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, 'owner/parent-swarm')
  } finally {
    fs.rmSync(parentProject, { recursive: true, force: true })
  }
}

async function assertProductEnvJsonSync() {
  const config = await loadConfig()
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  const checkedIn = fs.readFileSync(productEnvPath, 'utf8')
  const generated = cp.spawnSync(process.execPath, [envWriter, '--json'], {
    cwd: root,
    env: cleanEnv({
      OPENSWARM_MARKETPLACE_SWARM_ID: 'someone/custom-swarm',
      OPENSWARM_MARKETPLACE_PARENT_SWARM_ID: 'VRSEN/OpenSwarm',
      OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'fork',
    }),
    encoding: 'utf8',
  })
  assert.equal(generated.status, 0, `env JSON writer exited with ${generated.status}: ${generated.stderr}`)
  assert.equal(generated.stdout, checkedIn, 'write-product-env.mjs --json does not match openswarm.product-env.json')

  const fallback = JSON.parse(checkedIn)
  const env = config.getProductEnv({
    env: {},
    stateRoot: '__OPENSWARM_STATE_ROOT__',
  })
  delete env.AGENTSWARM_PRODUCT_STATE_ROOT
  delete env.AGENTSWARM_PRODUCT_VERSION
  assert.deepEqual(fallback, env, 'openswarm.product-env.json is out of sync with openswarm.config.mjs')
  assert.equal(fallback.AGENTSWARM_PRODUCT_VERSION, undefined, 'openswarm.product-env.json must not store dynamic package version')
  assert.equal(config.getProductEnv({ env: {}, stateRoot: '__OPENSWARM_STATE_ROOT__' }).AGENTSWARM_PRODUCT_VERSION, pkg.version)
}

function writeFakePackage(rootDir, marketplace) {
  const pkg = path.join(rootDir, 'node_modules', '@vrsen', 'openswarm')
  const bin = path.join(pkg, 'bin')
  const dep = path.join(pkg, 'node_modules', '@vrsen', 'agentswarm', 'bin')
  const platform = path.join(pkg, 'node_modules', '@vrsen', `openswarm-cli-${process.platform === 'win32' ? 'windows' : process.platform}-${process.arch === 'arm64' ? 'arm64' : 'x64'}`, 'bin')
  fs.mkdirSync(bin, { recursive: true })
  fs.mkdirSync(dep, { recursive: true })
  fs.mkdirSync(platform, { recursive: true })
  fs.copyFileSync(launcher, path.join(bin, 'openswarm'))
  fs.chmodSync(path.join(bin, 'openswarm'), 0o755)
  fs.copyFileSync(configPath, path.join(pkg, 'openswarm.config.mjs'))
  if (marketplace) {
    fs.writeFileSync(path.join(pkg, 'openswarm.marketplace.json'), `${JSON.stringify(marketplace, null, 2)}\n`, 'utf8')
  } else {
    fs.copyFileSync(marketplacePath, path.join(pkg, 'openswarm.marketplace.json'))
  }
  fs.writeFileSync(
    path.join(pkg, 'package.json'),
    JSON.stringify({ name: '@vrsen/openswarm', version: '7.8.9-smoke' }),
    'utf8',
  )
  fs.writeFileSync(
    path.join(dep, 'agentswarm'),
    [
      '#!/usr/bin/env node',
      "'use strict'",
      "const cp = require('child_process')",
      "const fs = require('fs')",
      "if (process.env.OPENSWARM_LAUNCHER_SMOKE_ENV) {",
      "  fs.writeFileSync(process.env.OPENSWARM_LAUNCHER_SMOKE_ENV, JSON.stringify(process.env, null, 2))",
      '}',
      "const result = cp.spawnSync(process.env.AGENTSWARM_BIN_PATH, process.argv.slice(2), { stdio: 'inherit' })",
      "process.exit(result.status ?? 1)",
    ].join('\n'),
    'utf8',
  )
  fs.chmodSync(path.join(dep, 'agentswarm'), 0o755)
  fs.writeFileSync(
    path.join(platform, process.platform === 'win32' ? 'agentswarm.exe' : 'agentswarm'),
    [
      '#!/usr/bin/env node',
      "'use strict'",
      "console.log('platform-smoke')",
    ].join('\n'),
    'utf8',
  )
  fs.chmodSync(path.join(platform, process.platform === 'win32' ? 'agentswarm.exe' : 'agentswarm'), 0o755)
  return path.join(bin, 'openswarm')
}

function assertLauncherDelegatesToDependency() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-smoke-'))
  try {
    const bin = writeFakePackage(tmp)
    const envPath = path.join(tmp, 'env.json')
    const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
      cwd: tmp,
      env: cleanEnv({
        ENABLE_TELEMETRY: '0',
        OPEN_SWARM_TELEMETRY: '1',
        AGENTSWARM_TELEMETRY: 'true',
        AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID: 'stale/parent',
        OPENSWARM_TUI_URL: 'https://127.0.0.1:9/should-not-be-read',
        OPENSWARM_LAUNCHER_SMOKE_ENV: envPath,
      }),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    assert.equal(result.stdout.trim(), 'platform-smoke')

    const env = JSON.parse(fs.readFileSync(envPath, 'utf8'))
    assert.equal(env.AGENTSWARM_PRODUCT_DISPLAY_NAME, 'OpenSwarm')
    assert.equal(env.AGENTSWARM_PRODUCT_COMMAND, 'openswarm')
    assert.equal(env.AGENTSWARM_PRODUCT_VERSION, '7.8.9-smoke')
    assert.equal(env.AGENTSWARM_PRODUCT_HIDE_CONNECT, 'true')
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, undefined)
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'original')
    assert.equal(env.AGENTSWARM_LAUNCHER, '1')
    assert.equal(env.PYTHONUTF8, '1')
    assert.equal(env.PYTHONIOENCODING, 'utf-8')
    assert.equal(env.OPEN_SWARM_TELEMETRY, '0')
    assert.equal(env.AGENTSWARM_TELEMETRY, '0')
    assert.ok(env.AGENTSWARM_BIN_PATH, 'AGENTSWARM_BIN_PATH was not set')
    assert.ok(env.AGENTSWARM_BIN_PATH.includes('openswarm-cli-'), 'AGENTSWARM_BIN_PATH did not use an OpenSwarm platform package')
    assertProductAddons(env)
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertLauncherPassesForkMarketplaceMetadata() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-fork-marketplace-'))
  try {
    const bin = writeFakePackage(tmp, {
      swarmId: 'someone/custom-swarm',
      parentSwarmId: 'VRSEN/OpenSwarm',
      swarmOrigin: 'fork',
    })
    const envPath = path.join(tmp, 'env.json')
    const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
      cwd: tmp,
      env: cleanEnv({ OPENSWARM_LAUNCHER_SMOKE_ENV: envPath }),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    const env = JSON.parse(fs.readFileSync(envPath, 'utf8'))
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'someone/custom-swarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'fork')
    assert.equal(env.AGENTSWARM_PRODUCT_VERSION, '7.8.9-smoke')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertLauncherPassesProjectMarketplaceMetadata() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-project-marketplace-'))
  try {
    const bin = writeFakePackage(tmp)
    const project = path.join(tmp, 'project')
    fs.mkdirSync(project)
    fs.writeFileSync(
      path.join(project, 'openswarm.marketplace.json'),
      '{"swarmId":"someone/project-swarm","parentSwarmId":"VRSEN/OpenSwarm","swarmOrigin":"fork"}\n',
      'utf8',
    )
    const envPath = path.join(tmp, 'env.json')
    const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
      cwd: project,
      env: cleanEnv({ OPENSWARM_LAUNCHER_SMOKE_ENV: envPath }),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    const env = JSON.parse(fs.readFileSync(envPath, 'utf8'))
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'someone/project-swarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'fork')
    assert.equal(env.AGENTSWARM_PRODUCT_VERSION, '7.8.9-smoke')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertLauncherIgnoresMarketplaceEnv() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-ignore-marketplace-env-'))
  try {
    const bin = writeFakePackage(tmp)
    const envPath = path.join(tmp, 'env.json')
    const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
      cwd: tmp,
      env: cleanEnv({
        OPENSWARM_LAUNCHER_SMOKE_ENV: envPath,
        OPENSWARM_MARKETPLACE_SWARM_ID: 'someone/custom-swarm',
        OPENSWARM_MARKETPLACE_PARENT_SWARM_ID: '',
        OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'original',
        AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID: 'stale/parent',
      }),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    const env = JSON.parse(fs.readFileSync(envPath, 'utf8'))
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, undefined)
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'original')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertLauncherIgnoresMalformedMarketplaceEnv() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-ignore-bad-marketplace-env-'))
  try {
    const bin = writeFakePackage(tmp)
    const envPath = path.join(tmp, 'env.json')
    const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
      cwd: tmp,
      env: cleanEnv({
        OPENSWARM_LAUNCHER_SMOKE_ENV: envPath,
        OPENSWARM_MARKETPLACE_SWARM_ID: 'someone/custom-swarm',
        OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'fork',
      }),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    const env = JSON.parse(fs.readFileSync(envPath, 'utf8'))
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ID, 'VRSEN/OpenSwarm')
    assert.equal(env.AGENTSWARM_MARKETPLACE_PARENT_SWARM_ID, undefined)
    assert.equal(env.AGENTSWARM_MARKETPLACE_SWARM_ORIGIN, 'original')
    assert.equal(env.AGENTSWARM_PRODUCT_VERSION, '7.8.9-smoke')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertMalformedMarketplaceMetadataFails() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-bad-marketplace-'))
  try {
    for (const marketplace of [
      { swarmId: '', swarmOrigin: 'fork' },
      { swarmId: 'openswarm', swarmOrigin: 'fork' },
      { swarmId: 'bad--owner/custom-swarm', swarmOrigin: 'original' },
      { swarmId: 'someone/custom-swarm.GIT', swarmOrigin: 'original' },
      { swarmId: `owner/${'a'.repeat(129)}`, swarmOrigin: 'original' },
      { swarmId: 'someone/custom-swarm', swarmOrigin: 'fork' },
      { swarmId: 'someone/custom-swarm', parentSwarmId: 'VRSEN/OpenSwarm', swarmOrigin: 'copy' },
    ]) {
      const bin = writeFakePackage(tmp, marketplace)
      const result = cp.spawnSync(process.execPath, [bin, 'smoke'], {
        cwd: tmp,
        env: cleanEnv(),
        encoding: 'utf8',
      })
      assert.notEqual(result.status, 0, `launcher succeeded with malformed marketplace metadata: ${JSON.stringify(marketplace)}`)
      assert.ok(result.stderr.includes('OpenSwarm marketplace metadata'), result.stderr)
    }
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertVersionRequestUsesOpenSwarmPackageVersion() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-version-'))
  try {
    const bin = writeFakePackage(tmp)
    const result = cp.spawnSync(process.execPath, [bin, '--version'], {
      cwd: tmp,
      env: cleanEnv(),
      encoding: 'utf8',
    })
    assert.equal(result.status, 0, `launcher exited with ${result.status}: ${result.stderr}`)
    assert.equal(result.stdout.trim(), '7.8.9-smoke')
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertMissingPlatformPackageFails() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'openswarm-launcher-missing-'))
  try {
    const bin = writeFakePackage(tmp)
    const pkg = path.join(tmp, 'node_modules', '@vrsen', 'openswarm', 'node_modules', '@vrsen')
    for (const item of fs.readdirSync(pkg)) {
      if (item.startsWith('openswarm-cli-')) fs.rmSync(path.join(pkg, item), { recursive: true, force: true })
    }
    const result = cp.spawnSync(process.execPath, [bin, '--version'], {
      cwd: tmp,
      env: cleanEnv(),
      encoding: 'utf8',
    })
    assert.notEqual(result.status, 0, 'launcher succeeded without an OpenSwarm platform package')
    assert.ok(result.stderr.includes('optional dependencies enabled'), result.stderr)
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
}

function assertWorkflowEnvWriter() {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  const result = cp.spawnSync(process.execPath, [envWriter], {
    cwd: root,
    env: cleanEnv({
      OPENSWARM_MARKETPLACE_SWARM_ID: 'someone/custom-swarm',
      OPENSWARM_MARKETPLACE_PARENT_SWARM_ID: 'VRSEN/OpenSwarm',
      OPENSWARM_MARKETPLACE_SWARM_ORIGIN: 'fork',
    }),
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, `env writer exited with ${result.status}: ${result.stderr}`)
  assert.ok(result.stdout.includes('AGENTSWARM_PRODUCT_DISPLAY_NAME<<__OPENSWARM_ENV__'))
  assert.ok(result.stdout.includes('OpenSwarm'))
  assert.ok(result.stdout.includes('AGENTSWARM_PRODUCT_VERSION<<__OPENSWARM_ENV__'))
  assert.ok(result.stdout.includes(pkg.version))
}

async function main() {
  assertNoDownloadSource()
  assertPlatformDependencyVersions()
  assertPlatformPackageOrdering()
  await assertStateRoot()
  await assertProductEnvJsonSync()
  assertLauncherDelegatesToDependency()
  assertLauncherPassesForkMarketplaceMetadata()
  assertLauncherPassesProjectMarketplaceMetadata()
  assertLauncherIgnoresMarketplaceEnv()
  assertLauncherIgnoresMalformedMarketplaceEnv()
  assertMalformedMarketplaceMetadataFails()
  assertVersionRequestUsesOpenSwarmPackageVersion()
  assertMissingPlatformPackageFails()
  assertWorkflowEnvWriter()
  console.log('openswarm launcher smoke passed')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
