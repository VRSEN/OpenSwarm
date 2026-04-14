#!/usr/bin/env node
'use strict'

const { spawnSync } = require('child_process')
const path = require('path')

// Locate run.py relative to this file (bin/openswarm.js -> ../run.py)
const runScript = path.join(__dirname, '..', 'run.py')

// Prefer python3, fall back to python (covers Windows where it's usually 'python')
const candidates = process.platform === 'win32'
  ? ['python', 'python3', 'py']
  : ['python3', 'python']

let python = null
for (const cmd of candidates) {
  const probe = spawnSync(cmd, ['--version'], { stdio: 'pipe' })
  if (probe.status === 0) {
    python = cmd
    break
  }
}

if (!python) {
  process.stderr.write(
    'openswarm: Python 3.10+ is required but was not found.\n' +
    'Install it from https://www.python.org/downloads/ and try again.\n'
  )
  process.exit(1)
}

const result = spawnSync(python, [runScript, ...process.argv.slice(2)], {
  stdio: 'inherit',
  cwd: process.cwd(),
  env: process.env,
})

process.exit(result.status ?? 1)
