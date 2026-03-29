// ─────────────────────────────────────────────────────────────────────────────
// src/main/app-launcher.ts
//
// Utilities for checking whether a presentation app is currently running and
// for launching it if it is not.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { basename, extname } from 'path'

const execFileAsync = promisify(execFile)

/**
 * Returns true if a process whose name matches the basename of `appPath` is
 * currently running.
 */
export async function isAppRunning(appPath: string): Promise<boolean> {
  const name = basename(appPath, extname(appPath))
  try {
    if (process.platform === 'darwin') {
      const { stdout } = await execFileAsync('pgrep', ['-xi', name])
      return stdout.trim().length > 0
    }
    if (process.platform === 'win32') {
      const { stdout } = await execFileAsync('powershell', [
        '-NonInteractive',
        '-Command',
        `[bool](Get-Process -Name "${name}" -ErrorAction SilentlyContinue)`,
      ])
      return stdout.trim().toLowerCase() === 'true'
    }
    return false
  } catch {
    return false
  }
}

/**
 * Launches the application at `appPath`.
 * Fire-and-forget — throws only if the OS refuses to start the process at all.
 */
export async function launchApp(appPath: string): Promise<void> {
  if (process.platform === 'darwin') {
    // `open` handles both .app bundles and raw executables.
    await execFileAsync('open', [appPath])
  } else if (process.platform === 'win32') {
    // Detach so Electron doesn't wait for the child to exit.
    execFile(appPath, [], { detached: true, stdio: 'ignore' })
  } else {
    execFile(appPath, [], { detached: true, stdio: 'ignore' })
  }
}
