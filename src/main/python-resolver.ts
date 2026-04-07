/**
 * src/main/python-resolver.ts
 *
 * Finds a Python 3.11+ executable on the current machine.
 *
 * Search order:
 *   1. VERSEFLOW_PYTHON env var (lets power users override)
 *   2. `py -3.X` — Windows Python Launcher (handles multi-version installs)
 *   3. Common Windows install paths (direct .exe, avoids App Execution Alias stubs)
 *   4. `python3` — standard on macOS/Linux
 *   5. `python`  — fallback, skipping Windows Store stubs
 *
 * Returns the first candidate that responds with Python 3.11+.
 * Throws if none are found.
 */

import { execFileSync } from 'child_process'
import { existsSync } from 'fs'
import { homedir } from 'os'
import { join } from 'path'

const MIN_MINOR = 11

/**
 * Windows App Execution Aliases live in this directory. These stubs can pass
 * `--version` quickly but hang indefinitely when spawned from a non-interactive
 * context like Electron's main process.  We skip them unconditionally.
 */
const WIN_STORE_STUB_DIR = 'WindowsApps'.toLowerCase()

function resolvedPathContainsStub(cmd: string): boolean {
  if (process.platform !== 'win32') return false
  try {
    const out = execFileSync('where', [cmd], {
      encoding: 'utf8',
      timeout: 1500,
      stdio: ['ignore', 'pipe', 'ignore'],
    })
    const firstLine = out.split('\n')[0].trim().toLowerCase()
    return firstLine.includes(WIN_STORE_STUB_DIR)
  } catch {
    return false
  }
}

function tryCandidate(cmd: string, args: string[]): string | null {
  try {
    // Before testing a bare command name, check if Windows would resolve it to
    // a Store stub (the stub is known to hang in non-interactive spawns).
    if (process.platform === 'win32' && args.length === 0 && resolvedPathContainsStub(cmd)) {
      return null
    }

    const out = execFileSync(cmd, [...args, '--version'], {
      encoding: 'utf8',
      timeout: 3000,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    // stdout or stderr may contain "Python 3.X.Y"
    const match = (out + '').match(/Python (\d+)\.(\d+)/)
    if (match && parseInt(match[1]) === 3 && parseInt(match[2]) >= MIN_MINOR) {
      return cmd
    }
    return null
  } catch {
    return null
  }
}

/** Enumerate well-known Windows Python install locations (bypasses App Execution Aliases). */
function windowsKnownPaths(): string[] {
  const candidates: string[] = []
  const home = homedir()

  for (const ver of ['313', '312', '311']) {
    // Per-user installs: %LOCALAPPDATA%\Programs\Python\Python3XX\python.exe
    candidates.push(join(home, 'AppData', 'Local', 'Programs', 'Python', `Python${ver}`, 'python.exe'))
    // System-wide installs: C:\PythonXXX\python.exe
    candidates.push(`C:\\Python${ver}\\python.exe`)
  }

  return candidates.filter(p => existsSync(p) && !p.toLowerCase().includes(WIN_STORE_STUB_DIR))
}

export function resolvePython(): string {
  // 1. Explicit override.
  const envOverride = process.env['VERSEFLOW_PYTHON']
  if (envOverride) return envOverride

  if (process.platform === 'win32') {
    // 2. Windows py launcher — most reliable on properly configured systems.
    for (const ver of ['3.13', '3.12', '3.11']) {
      if (tryCandidate('py', [`-${ver}`])) return `py -${ver}`
    }
    if (tryCandidate('py', ['-3'])) return 'py -3'

    // 3. Direct paths to known install locations (works even when PATH is stripped).
    for (const fullPath of windowsKnownPaths()) {
      if (tryCandidate(fullPath, [])) return fullPath
    }
  }

  // 4. python3 (macOS/Linux standard).
  if (tryCandidate('python3', [])) return 'python3'

  // 5. python fallback — skips Windows Store stubs via tryCandidate.
  if (tryCandidate('python', [])) return 'python'

  throw new Error(
    'Python 3.11+ not found. Install Python from https://python.org and run: pip install -r sidecar/requirements.txt',
  )
}
