// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/propresenter.ts
//
// ProPresenter driver — focuses ProPresenter's library search box and pastes
// the verse/lyric text using OS-level keyboard automation.
//
// Strategy (cross-platform):
//   1. Write the text to Electron's clipboard.
//   2. Bring ProPresenter to the foreground.
//   3. Open the library search box (Cmd+F on macOS, Ctrl+F on Windows).
//   4. Paste the clipboard contents (Cmd+V / Ctrl+V).
//   5. Press Enter to execute the search.
//
// Using the clipboard sidesteps all character-escaping issues with SendKeys /
// AppleScript keystroke for arbitrary Unicode text.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { clipboard } from 'electron'
import type { IPresentationDriver } from './index'

const execFileAsync = promisify(execFile)

export class ProPresenterDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    // Put text on the clipboard first — shared by both platform paths.
    clipboard.writeText(text)

    if (process.platform === 'darwin') {
      await this._sendMac()
    } else if (process.platform === 'win32') {
      await this._sendWindows()
    } else {
      throw new Error('ProPresenter driver requires macOS or Windows')
    }
  }

  /** macOS: AppleScript via osascript. */
  private async _sendMac(): Promise<void> {
    const script = [
      'tell application "ProPresenter" to activate',
      'delay 0.4',
      'tell application "System Events"',
      '  keystroke "f" using command down', // open library search
      '  delay 0.3',
      '  keystroke "a" using command down', // select all existing text
      '  keystroke "v" using command down', // paste verse text
      '  delay 0.2',
      '  key code 36',                      // Return — execute search
      'end tell',
    ].join('\n')

    await execFileAsync('osascript', ['-e', script])
  }

  /** Windows: PowerShell + WScript.Shell SendKeys. */
  private async _sendWindows(): Promise<void> {
    // WScript.Shell SendKeys: ^ = Ctrl, % = Alt, + = Shift, {key} = special key.
    const script = [
      '$sh = New-Object -ComObject WScript.Shell',
      '$sh.AppActivate("ProPresenter")',
      'Start-Sleep -Milliseconds 400',
      '$sh.SendKeys("^f")',  // Ctrl+F — open library search
      'Start-Sleep -Milliseconds 300',
      '$sh.SendKeys("^a")',  // Ctrl+A — select existing text
      '$sh.SendKeys("^v")',  // Ctrl+V — paste verse text
      'Start-Sleep -Milliseconds 200',
      '$sh.SendKeys("{ENTER}")',
    ].join('; ')

    await execFileAsync('powershell', ['-NonInteractive', '-Command', script])
  }
}
