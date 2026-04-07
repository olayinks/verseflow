// ─────────────────────────────────────────────────────────────────────────────
// src/main/sidecar-manager.ts
//
// Manages the lifecycle of the Python sidecar subprocess and the WebSocket
// client that Electron uses to talk to it.
//
// Architecture:
//   Electron main  ──WS client──▶  Python sidecar (WS server)
//
// The sidecar is responsible for all heavy lifting:
//   audio capture → STT → detection engines → WebSocket push.
//
// In dev mode the sidecar can be started manually (`npm run sidecar:dev`)
// or auto-spawned by this manager.  In production, the sidecar binary is
// bundled in resources/ and spawned here.
// ─────────────────────────────────────────────────────────────────────────────

import { ChildProcess, spawn } from 'child_process'
import { join } from 'path'
import { BrowserWindow } from 'electron'
import WebSocket from 'ws'
import { is } from '@electron-toolkit/utils'
import { IPC, type WsMessage, DEFAULT_SETTINGS } from '../shared/types'
import { resolvePython } from './python-resolver'
import { settingsStore } from './settings-store'

const RECONNECT_DELAY_MS = 2000
const MAX_RECONNECT_ATTEMPTS = 10

export class SidecarManager {
  private process: ChildProcess | null = null
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private shuttingDown = false
  private port: number = DEFAULT_SETTINGS.sidecarPort

  // ── Spawn ─────────────────────────────────────────────────────────────────

  private spawnSidecar(): void {
    if (this.process) return

    let cmd: string
    let args: string[]
    const configPath = join(process.cwd(), 'data', 'dev-config.json')

    if (is.dev) {
      // Resolve Python at spawn time so we pick up the correct version.
      // resolvePython() may return "py -3.13" (space-separated) on Windows.
      const pythonExpr = resolvePython()
      const parts = pythonExpr.split(' ')
      cmd = parts[0]
      args = [...parts.slice(1), join(process.cwd(), 'sidecar', 'main.py'), configPath]
    } else {
      // Prod: run the bundled executable from resources/.
      const ext = process.platform === 'win32' ? '.exe' : ''
      cmd = join(process.resourcesPath, `verseflow-sidecar${ext}`)
      args = [configPath]
    }

    console.log('[SidecarManager] Spawning sidecar:', cmd, args.join(' '))

    const audioDevice = settingsStore.get('audioDevice')
    this.process = spawn(cmd, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        VERSEFLOW_PORT: String(this.port),
        ...(audioDevice ? { VERSEFLOW_AUDIO_DEVICE: audioDevice } : {}),
      },
    })

    this.process.stdout?.on('data', (d: Buffer) =>
      console.log('[sidecar]', d.toString().trimEnd()),
    )
    this.process.stderr?.on('data', (d: Buffer) =>
      console.error('[sidecar:err]', d.toString().trimEnd()),
    )
    this.process.on('exit', (code) => {
      console.warn('[SidecarManager] Sidecar exited with code', code)
      this.process = null
      if (!this.shuttingDown) {
        this.reconnectAttempts = 0  // fresh process = fresh WS reconnect budget
        setTimeout(() => this.spawnSidecar(), RECONNECT_DELAY_MS * 2)
      }
    })
  }

  // ── WebSocket connection ──────────────────────────────────────────────────

  connect(win: BrowserWindow): void {
    if (is.dev) {
      // In dev, never auto-spawn — the developer starts the sidecar manually
      // (either `npm run sidecar:dev` or `npm run sidecar:mock`).
      // Just try to connect and retry until something answers.
      console.log('[SidecarManager] Dev mode — waiting for manually started sidecar on port', this.port)
      this.openWebSocket(win)
    } else {
      this.spawnSidecar()
      // Give the sidecar a moment to boot before connecting.
      setTimeout(() => this.openWebSocket(win), 1500)
    }
  }

  private openWebSocket(win: BrowserWindow): void {
    if (this.shuttingDown) return

    const url = `ws://127.0.0.1:${this.port}`
    console.log('[SidecarManager] Connecting to sidecar at', url)

    this.ws = new WebSocket(url)

    this.ws.on('open', () => {
      console.log('[SidecarManager] WebSocket connected')
      this.reconnectAttempts = 0
      this.pushStatus(win, true, 'Connected to audio engine')
    })

    this.ws.on('message', (raw: WebSocket.RawData) => {
      try {
        const msg: WsMessage = JSON.parse(raw.toString())
        this.routeMessage(win, msg)
      } catch (e) {
        console.error('[SidecarManager] Bad message:', e)
      }
    })

    this.ws.on('close', () => {
      console.warn('[SidecarManager] WebSocket closed')
      this.pushStatus(win, false, 'Audio engine disconnected')
      this.scheduleReconnect(win)
    })

    this.ws.on('error', (err) => {
      console.error('[SidecarManager] WebSocket error:', err.message)
      // 'close' fires after 'error', so reconnect is handled there.
    })
  }

  private scheduleReconnect(win: BrowserWindow): void {
    if (this.shuttingDown) return
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('[SidecarManager] Max reconnect attempts reached')
      return
    }
    this.reconnectAttempts++
    const delay = RECONNECT_DELAY_MS * this.reconnectAttempts
    console.log(`[SidecarManager] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
    setTimeout(() => this.openWebSocket(win), delay)
  }

  // ── Message routing ───────────────────────────────────────────────────────

  private routeMessage(win: BrowserWindow, msg: WsMessage): void {
    switch (msg.type) {
      case 'transcript':
        win.webContents.send(IPC.ON_TRANSCRIPT, msg.payload)
        break
      case 'verse_suggestion':
      case 'lyric_suggestion':
        win.webContents.send(IPC.ON_SUGGESTION, msg.payload)
        break
      case 'status':
        win.webContents.send(IPC.ON_STATUS, msg.payload)
        break
      case 'error':
        win.webContents.send(IPC.ON_ERROR, msg.payload)
        break
      default:
        console.warn('[SidecarManager] Unknown message type:', (msg as WsMessage).type)
    }
  }

  // ── Commands to sidecar ───────────────────────────────────────────────────

  send(msg: WsMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    } else {
      console.warn('[SidecarManager] Cannot send — WebSocket not open')
    }
  }

  startListening(): void {
    this.send({ type: 'status', payload: { command: 'start' } })
  }

  stopListening(): void {
    this.send({ type: 'status', payload: { command: 'stop' } })
  }

  setMode(mode: string): void {
    this.send({ type: 'status', payload: { command: `set_mode:${mode}` } })
  }

  // ── Teardown ──────────────────────────────────────────────────────────────

  shutdown(): void {
    this.shuttingDown = true
    this.ws?.close()
    this.ws = null
    this.process?.kill()
    this.process = null
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private pushStatus(win: BrowserWindow, connected: boolean, message: string): void {
    win.webContents.send(IPC.ON_STATUS, { connected, message })
  }

  setPort(port: number): void {
    this.port = port
  }

  /**
   * Restart the sidecar so it picks up a new audio device from the settings
   * store.  In production, killing the process triggers the auto-respawn which
   * re-reads VERSEFLOW_AUDIO_DEVICE from the store.  In dev mode the user
   * restarts the sidecar manually.
   */
  restartAudio(): void {
    if (!is.dev && this.process) {
      this.process.kill()
    }
  }
}
