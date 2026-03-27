import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import process from 'node:process'

const require = createRequire(import.meta.url)
const playwrightCliPath = require.resolve('@playwright/test/cli')

const env = { ...process.env }
if (env.FORCE_COLOR && env.NO_COLOR) {
  delete env.NO_COLOR
}

const child = spawn(process.execPath, [playwrightCliPath, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env,
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 0)
})
