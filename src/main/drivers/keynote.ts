// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/keynote.ts
//
// Keynote driver (macOS only) — uses Find (Cmd+F) to navigate to the slide
// that contains the verse text.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { clipboard } from 'electron'
import type { IPresentationDriver } from './index'

const execFileAsync = promisify(execFile)

export class KeynoteDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    if (process.platform !== 'darwin') {
      throw new Error('Keynote is only available on macOS')
    }

    clipboard.writeText(text)
    await this._sendMac()
  }

  private async _sendMac(): Promise<void> {
    const script = [
      'tell application "Keynote" to activate',
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
}
