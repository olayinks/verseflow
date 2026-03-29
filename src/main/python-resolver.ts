/**
 * src/main/python-resolver.ts
 *
 * Finds a Python 3.11+ executable on the current machine.
 *
 * Search order:
 *   1. VERSEFLOW_PYTHON env var (lets power users override)
 *   2. `py -3` — Windows Python Launcher (handles multi-version installs)
 *   3. `python3` — standard on macOS/Linux
 *   4. `python`  — fallback (may be Python 2 on old systems)
 *
 * Returns the first candidate that responds with Python 3.11+.
 * Throws if none are found.
 */

import { execFileSync } from 'child_process'

const MIN_MINOR = 11

function tryCandidate(cmd: string, args: string[]): string | null {
  try {
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

export function resolvePython(): string {
  // 1. Explicit override.
  const envOverride = process.env['VERSEFLOW_PYTHON']
  if (envOverride) return envOverride

  // 2. Windows py launcher — try newest-first.
  if (process.platform === 'win32') {
    for (const ver of ['3.13', '3.12', '3.11']) {
      const found = tryCandidate('py', [`-${ver}`])
      if (found) return `py -${ver}`  // return as a single string for splitting later
    }
    // Generic py -3 fallback.
    const pyGeneric = tryCandidate('py', ['-3'])
    if (pyGeneric) return 'py -3'
  }

  // 3. python3 (macOS/Linux standard).
  const p3 = tryCandidate('python3', [])
  if (p3) return 'python3'

  // 4. python fallback.
  const p = tryCandidate('python', [])
  if (p) return 'python'

  throw new Error(
    'Python 3.11+ not found. Install Python from https://python.org and run: pip install -r sidecar/requirements.txt',
  )
}
