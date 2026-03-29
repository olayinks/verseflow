// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/easyworship.ts
//
// EasyWorship driver — focuses the library search box and pastes the verse text.
//
// EasyWorship shortcut: Ctrl+F (Windows) / Cmd+F (macOS) opens library search.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { clipboard } from 'electron'
import type { IPresentationDriver } from './index'

const execFileAsync = promisify(execFile)

export class EasyWorshipDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    clipboard.writeText(text)

    if (process.platform === 'darwin') {
      await this._sendMac()
    } else if (process.platform === 'win32') {
      await this._sendWindows()
    } else {
      throw new Error('EasyWorship driver requires macOS or Windows')
    }
  }

  private async _sendMac(): Promise<void> {
    const script = [
      'tell application "EasyWorship" to activate',
      'delay 0.4',
      'tell application "System Events"',
      '  keystroke "f" using command down',
      '  delay 0.3',
      '  keystroke "a" using command down',
      '  keystroke "v" using command down',
      '  delay 0.2',
      '  key code 36',
      'end tell',
    ].join('\n')

    await execFileAsync('osascript', ['-e', script])
  }

  private async _sendWindows(): Promise<void> {
    const script = [
      '$sh = New-Object -ComObject WScript.Shell',
      '$sh.AppActivate("EasyWorship")',
      'Start-Sleep -Milliseconds 400',
      '$sh.SendKeys("^f")',
      'Start-Sleep -Milliseconds 300',
      '$sh.SendKeys("^a")',
      '$sh.SendKeys("^v")',
      'Start-Sleep -Milliseconds 200',
      '$sh.SendKeys("{ENTER}")',
    ].join('; ')

    await execFileAsync('powershell', ['-NonInteractive', '-Command', script])
  }
}
