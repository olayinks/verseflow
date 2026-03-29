// ─────────────────────────────────────────────────────────────────────────────
// src/main/drivers/openlp.ts
//
// OpenLP driver — uses the built-in REST API (v2, default port 4316) to search
// for a Bible verse and send it live.  OpenLP must have the Bible plugin enabled
// and the Remote plugin active.
//
// API flow:
//   1. Search the Bible plugin for the verse text.
//   2. Add the first matching result to the service queue.
//   3. Set it live immediately.
//
// Falls back to keyboard automation (Ctrl+F) if the API call fails, so the
// driver still works even when the Remote plugin is disabled.
// ─────────────────────────────────────────────────────────────────────────────

import { execFile } from 'child_process'
import { promisify } from 'util'
import { clipboard } from 'electron'
import type { IPresentationDriver } from './index'

const execFileAsync = promisify(execFile)

const OPENLP_BASE = 'http://localhost:4316/api/v2'

export class OpenLPDriver implements IPresentationDriver {
  async send(text: string): Promise<void> {
    clipboard.writeText(text)

    try {
      await this._sendViaApi(text)
    } catch {
      // Remote plugin unavailable or no match — fall back to keyboard.
      await this._sendViaKeyboard()
    }
  }

  /** Search the Bibles plugin and push the first result live. */
  private async _sendViaApi(text: string): Promise<void> {
    const searchUrl = `${OPENLP_BASE}/plugins/bibles/search?text=${encodeURIComponent(text)}`
    const searchRes = await fetch(searchUrl)
    if (!searchRes.ok) throw new Error(`OpenLP search failed: ${searchRes.status}`)

    const data = (await searchRes.json()) as { results: { items: unknown[] } }
    const items = data?.results?.items
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error('No results from OpenLP Bible search')
    }

    // Add the first match to the service and go live.
    const addRes = await fetch(`${OPENLP_BASE}/plugins/bibles/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: (items[0] as { id: unknown }).id }),
    })
    if (!addRes.ok) throw new Error(`OpenLP add failed: ${addRes.status}`)

    // Trigger the last added item live.
    await fetch(`${OPENLP_BASE}/controller/live/set`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: 0 }),
    })
  }

  /** Keyboard fallback: focus OpenLP's media manager search box. */
  private async _sendViaKeyboard(): Promise<void> {
    if (process.platform === 'darwin') {
      const script = [
        'tell application "OpenLP" to activate',
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
    } else if (process.platform === 'win32') {
      const script = [
        '$sh = New-Object -ComObject WScript.Shell',
        '$sh.AppActivate("OpenLP")',
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
}
