#!/usr/bin/env node
'use strict'

const assert = require('assert')
const EventEmitter = require('events')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const root = path.dirname(__dirname)
const launcher = path.join(root, 'bin', 'openswarm')

function createClient(requests) {
  return {
    get(url, _opts, callback) {
      requests.push(url)
      const req = new EventEmitter()
      req.setTimeout = () => req
      req.destroy = (error) => req.emit('error', error)

      process.nextTick(() => {
        const res = new EventEmitter()
        res.statusCode = 404
        res.headers = {}
        res.resume = () => {}
        callback(res)
      })

      return req
    },
  }
}

function load(opts) {
  const requests = []
  const child = {
    spawnSync(command) {
      if (command === 'ldd') {
        return {
          status: 0,
          stdout: opts.ldd || '',
          stderr: '',
        }
      }
      return {
        status: 1,
        stdout: '',
        stderr: '',
      }
    },
  }
  const files = {
    ...fs,
    existsSync(target) {
      if (target === '/etc/alpine-release') return Boolean(opts.alpine)
      return fs.existsSync(target)
    },
  }
  const proc = {
    ...process,
    arch: () => opts.arch,
    env: {
      ...process.env,
      ...opts.env,
    },
    platform: opts.platform,
    stdout: {
      write() {},
    },
  }
  const modules = {
    assert,
    events: EventEmitter,
    fs: files,
    http: createClient(requests),
    https: createClient(requests),
    os: {
      arch: () => opts.arch,
      homedir: () => opts.homedir || '/home/tester',
    },
    path,
    'child_process': child,
  }
  const context = {
    Buffer,
    Error,
    JSON,
    Promise,
    URL,
    console,
    module: { exports: {} },
    process: proc,
    require(name) {
      if (modules[name]) return modules[name]
      return require(name)
    },
    __filename: launcher,
  }
  context.exports = context.module.exports

  const source = fs.readFileSync(launcher, 'utf8')
  const start = source.startsWith('#!') ? source.indexOf('\n') + 1 : 0
  const startup = source.indexOf('\nconst agentswarmBin = resolveAgentswarm(packageDir)')
  assert.notEqual(startup, -1, 'launcher startup block not found')
  const script = new vm.Script(
    `${source.slice(start, startup)}
module.exports = { downstreamEnv, getBinaryNames, isMuslLinux, resolveStateRoot, shouldUseDependencyBinary, ensureCustomBinary }`,
    { filename: launcher },
  )
  script.runInNewContext(context)

  return {
    api: context.module.exports,
    requests,
  }
}

function assertProductAddons(api) {
  assert.ok(api.downstreamEnv, 'downstreamEnv export not available')
  assert.ok(api.downstreamEnv.AGENTSWARM_PRODUCT_ADDONS, 'AGENTSWARM_PRODUCT_ADDONS not set')

  const addons = JSON.parse(api.downstreamEnv.AGENTSWARM_PRODUCT_ADDONS)
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

function assertStateRoot() {
  const linux = load({
    platform: 'linux',
    arch: 'x64',
    homedir: '/home/tester',
  })
  assert.equal(linux.api.resolveStateRoot(), path.join('/home/tester', '.openswarm'))
  assert.equal(linux.api.downstreamEnv.AGENTSWARM_PRODUCT_STATE_ROOT, path.join('/home/tester', '.openswarm'))

  const darwin = load({
    platform: 'darwin',
    arch: 'arm64',
    homedir: '/Users/tester',
  })
  assert.equal(darwin.api.resolveStateRoot(), path.join('/Users/tester', '.openswarm'))

  const windows = load({
    platform: 'win32',
    arch: 'x64',
    homedir: 'C:\\Users\\tester',
    env: {
      APPDATA: 'C:\\Users\\tester\\AppData\\Roaming',
    },
  })
  assert.equal(windows.api.resolveStateRoot(), path.join('C:\\Users\\tester\\AppData\\Roaming', 'OpenSwarm'))

  const explicit = load({
    platform: 'linux',
    arch: 'x64',
    env: {
      OPENSWARM_STATE_ROOT: '/tmp/openswarm-state',
    },
  })
  assert.equal(explicit.api.resolveStateRoot(), path.resolve('/tmp/openswarm-state'))
}

async function main() {
  const musl = load({
    platform: 'linux',
    arch: 'x64',
    ldd: 'musl libc (x86_64)',
  })
  assert.equal(musl.api.isMuslLinux(), true)
  assert.equal(musl.api.shouldUseDependencyBinary(), true)
  assert.equal(await musl.api.ensureCustomBinary(), null)
  assert.deepEqual(musl.requests, [])
  assertProductAddons(musl.api)
  assertStateRoot()

  const explicit = load({
    platform: 'linux',
    arch: 'x64',
    env: {
      OPENSWARM_TUI_URL: 'https://example.test/openswarm',
    },
    ldd: 'musl libc (x86_64)',
  })
  assert.equal(explicit.api.shouldUseDependencyBinary(), false)
  assert.deepEqual(explicit.api.getBinaryNames(), ['agentswarm-linux-x64', 'agentswarm-linux-x64-baseline'])

  const glibc = load({
    platform: 'linux',
    arch: 'x64',
    ldd: 'ldd (GNU libc)',
  })
  assert.equal(glibc.api.isMuslLinux(), false)
  assert.equal(glibc.api.shouldUseDependencyBinary(), false)
  await assert.rejects(() => glibc.api.ensureCustomBinary(), /custom OpenSwarm TUI unavailable/)
  assert.ok(glibc.requests.some((url) => url.includes('agentswarm-linux-x64')))

  console.log('openswarm launcher smoke passed')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
