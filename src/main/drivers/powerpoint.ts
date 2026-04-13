// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/powerpoint.ts
//
// PowerPoint driver — uses Find (Ctrl+F / Cmd+F) to navigate to a slide that
// already contains the verse text.  Paste into the search box; PowerPoint will
// jump to the matching slide.
//
// If the congregation's deck has one slide per verse (a common pattern), this
// lets the operator instantly jump to the right slide.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { clipboard } from 'electron'
import type { IPresentationDriver } from './index'

const execFileAsync = promisify(execFile)

export class PowerPointDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    clipboard.writeText(text)

    if (process.platform === 'darwin') {
      await this._sendMac()
    } else if (process.platform === 'win32') {
      await this._sendWindows()
    } else {
      throw new Error('PowerPoint driver requires macOS or Windows')
    }
  }

  private async _sendMac(): Promise<void> {
    const script = [
      'tell application "Microsoft PowerPoint" to activate',
      'delay 0.4',
      'tell application "System Events"',
      '  keystroke "f" using command down',
      '  delay 0.4',
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
      '$sh.AppActivate("Microsoft PowerPoint")',
      'Start-Sleep -Milliseconds 400',
      '$sh.SendKeys("^f")',
      'Start-Sleep -Milliseconds 400',
      '$sh.SendKeys("^a")',
      '$sh.SendKeys("^v")',
      'Start-Sleep -Milliseconds 200',
      '$sh.SendKeys("{ENTER}")',
    ].join('; ')

    await execFileAsync('powershell', ['-NonInteractive', '-Command', script])
  }
}
