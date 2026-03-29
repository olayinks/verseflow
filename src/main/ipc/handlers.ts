// ─────────────────────────────────────────────────────────────────────────────
// src/main/ipc/handlers.ts
//
// All ipcMain.handle() registrations live here.
// Each handler is the bridge between a renderer call and a main-process action.
// ─────────────────────────────────────────────────────────────────────────────

import { ipcMain, BrowserWindow, dialog } from 'electron'
import { IPC, type AppSettings, type AudioDevice, type AppLaunchStatus } from '../../shared/types'
import type { SidecarManager } from '../sidecar-manager'
import { getDriver } from '../drivers'
import { resolvePython } from '../python-resolver'
import { execFileSync } from 'child_process'
import { join } from 'path'
import { settingsStore } from '../settings-store'
import { isAppRunning, launchApp } from '../app-launcher'

// ---------------------------------------------------------------------------

interface HandlerDeps {
  mainWindow: BrowserWindow
  sidecarManager: SidecarManager
}

export function registerIpcHandlers({ mainWindow, sidecarManager }: HandlerDeps): void {
  // ── Window controls ───────────────────────────────────────────────────────

  ipcMain.on('window:close', () => mainWindow.close())
  ipcMain.on('window:minimize', () => mainWindow.minimize())

  // ── Sidecar control ───────────────────────────────────────────────────────

  ipcMain.handle(IPC.START_LISTENING, async () => {
    sidecarManager.startListening()
  })

  ipcMain.handle(IPC.STOP_LISTENING, async () => {
    sidecarManager.stopListening()
  })

  // ── Presentation driver ───────────────────────────────────────────────────

  ipcMain.handle(IPC.SEND_TO_PRESENTATION, async (_event, text: string) => {
    const driver = getDriver(settingsStore.store.presentationDriver)
    await driver.send(text)
  })

  // ── Settings ──────────────────────────────────────────────────────────────

  ipcMain.handle(IPC.GET_SETTINGS, async (): Promise<AppSettings> => {
    return settingsStore.store
  })

  ipcMain.handle(IPC.SET_SETTINGS, async (_event, partial: Partial<AppSettings>): Promise<AppSettings> => {
    Object.entries(partial).forEach(([k, v]) => {
      settingsStore.set(k as keyof AppSettings, v as AppSettings[keyof AppSettings])
    })
    if (partial.sidecarPort !== undefined) {
      sidecarManager.setPort(partial.sidecarPort)
    }
    if (partial.audioDevice !== undefined) {
      sidecarManager.restartAudio()
    }
    return settingsStore.store
  })

  // ── Audio devices ─────────────────────────────────────────────────────────

  ipcMain.handle(IPC.GET_AUDIO_DEVICES, async (): Promise<AudioDevice[]> => {
    try {
      const pythonExpr = resolvePython()
      const parts = pythonExpr.split(' ')
      const cmd = parts[0]
      const cmdArgs = parts.slice(1)

      const script = [
        'import sys, json',
        `sys.path.insert(0, r'${join(process.cwd(), 'sidecar').replace(/\\/g, '\\\\')}')`,
        'from audio.capture import AudioCapture',
        'print(json.dumps(AudioCapture.list_devices()))',
      ].join(';')

      const raw = execFileSync(cmd, [...cmdArgs, '-c', script], {
        encoding: 'utf8',
        timeout: 5000,
      })

      const devices: Array<{ index: number; name: string; channels: number; sample_rate: number }> =
        JSON.parse(raw.trim())

      return devices.map((d) => ({
        index: d.index,
        name: d.name,
        channels: d.channels,
        sampleRate: d.sample_rate,
      }))
    } catch (e) {
      console.error('[handlers] Failed to list audio devices:', e)
      return []
    }
  })

  // ── App path picker ───────────────────────────────────────────────────────

  ipcMain.handle(IPC.APP_PICK_PATH, async (): Promise<string | null> => {
    const filters =
      process.platform === 'darwin'
        ? [{ name: 'Applications', extensions: ['app'] }]
        : [{ name: 'Executables', extensions: ['exe'] }]

    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Select presentation application',
      properties: ['openFile'],
      filters,
    })

    return result.canceled ? null : result.filePaths[0]
  })

  // ── App check & launch ────────────────────────────────────────────────────

  ipcMain.handle(IPC.APP_CHECK_LAUNCH, async (): Promise<AppLaunchStatus> => {
    const { presentationDriver, presentationAppPath } = settingsStore.store

    if (presentationDriver === 'none' || !presentationAppPath) {
      return { running: false, launched: false }
    }

    const running = await isAppRunning(presentationAppPath)
    if (running) return { running: true, launched: false }

    await launchApp(presentationAppPath).catch((e) => {
      console.error('[handlers] Failed to launch presentation app:', e)
    })
    return { running: false, launched: true }
  })
}
