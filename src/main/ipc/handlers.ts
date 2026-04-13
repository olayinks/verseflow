// ─────────────────────────────────────────────────────────────────────────────
// src/main/ipc/handlers.ts
//
// All ipcMain.handle() registrations live here.
// Each handler is the bridge between a renderer call and a main-process action.
// ─────────────────────────────────────────────────────────────────────────────

import { app, ipcMain, BrowserWindow, dialog } from 'electron'
import { IPC, type AppSettings, type AudioDevice, type AppLaunchStatus, type CaptureMode, type TrainingStatus } from '../../shared/types'
import type { SidecarManager } from '../sidecar-manager'
import { getDriver } from '../drivers'
import { resolvePython } from '../python-resolver'
import { execFileSync, spawn } from 'child_process'
import { join } from 'path'
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'fs'
import { is } from '@electron-toolkit/utils'
import { settingsStore } from '../settings-store'
import { isAppRunning, launchApp } from '../app-launcher'

// ── Training helpers ──────────────────────────────────────────────────────────
// User-generated data (samples, manifest, trained model) lives in the OS user
// data directory — this is writable in both dev and packaged production builds.
// The trainer script itself is read from the source tree in dev and from
// process.resourcesPath in production (bundled via extraResources).

const USER_DATA = app.getPath('userData')
const TRAINING_DIR = join(USER_DATA, 'training')
const SAMPLES_DIR = join(TRAINING_DIR, 'samples')
const MANIFEST_PATH = join(TRAINING_DIR, 'manifest.json')
const CUSTOM_MODEL_DIR = join(USER_DATA, 'models', 'custom-whisper-ct2')

interface SampleEntry {
  id: string
  audioFile: string
  transcript: string
  createdAt: string
}

function readManifest(): SampleEntry[] {
  if (!existsSync(MANIFEST_PATH)) return []
  try {
    return JSON.parse(readFileSync(MANIFEST_PATH, 'utf8'))
  } catch {
    return []
  }
}

function writeManifest(samples: SampleEntry[]): void {
  mkdirSync(TRAINING_DIR, { recursive: true })
  writeFileSync(MANIFEST_PATH, JSON.stringify(samples, null, 2), 'utf8')
}

let trainingProcess: ReturnType<typeof spawn> | null = null

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

  ipcMain.handle(IPC.SET_MODE, async (_event, mode: CaptureMode) => {
    sidecarManager.setMode(mode)
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

  // ── Speaker training ──────────────────────────────────────────────────────

  ipcMain.handle(IPC.TRAINING_SAVE_SAMPLE, async (_event, audio: ArrayBuffer, transcript: string): Promise<void> => {
    mkdirSync(SAMPLES_DIR, { recursive: true })
    const id = `sample_${Date.now()}`
    const audioFile = join(SAMPLES_DIR, `${id}.wav`)
    writeFileSync(audioFile, Buffer.from(audio))
    const samples = readManifest()
    samples.push({ id, audioFile, transcript: transcript.trim(), createdAt: new Date().toISOString() })
    writeManifest(samples)
  })

  ipcMain.handle(IPC.TRAINING_GET_STATUS, async (): Promise<TrainingStatus> => {
    const samples = readManifest()
    return {
      sampleCount: samples.length,
      isTraining: trainingProcess !== null,
      progress: 0,
      hasCustomModel: existsSync(join(CUSTOM_MODEL_DIR, 'model.bin')),
      lastError: null,
    }
  })

  ipcMain.handle(IPC.TRAINING_START, async (): Promise<void> => {
    if (trainingProcess) return

    // Resolve system Python — training always uses the system Python, never the
    // bundled sidecar binary, because it needs pip-installable packages.
    let pythonExpr: string
    try {
      pythonExpr = resolvePython()
    } catch {
      mainWindow.webContents.send(IPC.TRAINING_ON_PROGRESS, {
        sampleCount: readManifest().length,
        isTraining: false,
        progress: 0,
        hasCustomModel: existsSync(join(CUSTOM_MODEL_DIR, 'model.bin')),
        lastError: 'Python 3.11+ not found. Install Python from python.org.',
      } satisfies TrainingStatus)
      return
    }

    // Pre-flight: verify training dependencies are installed.
    const parts = pythonExpr.split(' ')
    const cmd = parts[0]
    const cmdArgs = parts.slice(1)
    try {
      execFileSync(cmd, [...cmdArgs, '-c', 'import torch, transformers, datasets, soundfile, ctranslate2'], {
        encoding: 'utf8', timeout: 10_000, stdio: ['ignore', 'ignore', 'pipe'],
      })
    } catch {
      mainWindow.webContents.send(IPC.TRAINING_ON_PROGRESS, {
        sampleCount: readManifest().length,
        isTraining: false,
        progress: 0,
        hasCustomModel: existsSync(join(CUSTOM_MODEL_DIR, 'model.bin')),
        lastError: 'Training packages missing. Run: pip install -r sidecar/requirements-training.txt',
      } satisfies TrainingStatus)
      return
    }

    // In dev the script is in the source tree; in production it is bundled via
    // extraResources and available at process.resourcesPath.
    const scriptPath = is.dev
      ? join(process.cwd(), 'sidecar', 'training', 'trainer.py')
      : join(process.resourcesPath, 'trainer.py')

    const args = [...cmdArgs, scriptPath, MANIFEST_PATH, CUSTOM_MODEL_DIR]

    trainingProcess = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'] })

    const pushProgress = (status: Partial<TrainingStatus>): void => {
      mainWindow.webContents.send(IPC.TRAINING_ON_PROGRESS, {
        sampleCount: readManifest().length,
        isTraining: true,
        progress: 0,
        hasCustomModel: existsSync(join(CUSTOM_MODEL_DIR, 'model.bin')),
        lastError: null,
        ...status,
      } satisfies TrainingStatus)
    }

    trainingProcess.stdout?.on('data', (d: Buffer) => {
      const line = d.toString().trim()
      // Trainer emits: PROGRESS:<0-100>
      const match = line.match(/^PROGRESS:(\d+)$/)
      if (match) pushProgress({ progress: parseInt(match[1]) })
      console.log('[trainer]', line)
    })

    trainingProcess.stderr?.on('data', (d: Buffer) =>
      console.error('[trainer:err]', d.toString().trim()),
    )

    trainingProcess.on('exit', (code) => {
      const hasCustomModel = existsSync(join(CUSTOM_MODEL_DIR, 'model.bin'))
      mainWindow.webContents.send(IPC.TRAINING_ON_PROGRESS, {
        sampleCount: readManifest().length,
        isTraining: false,
        progress: code === 0 ? 100 : 0,
        hasCustomModel,
        lastError: code !== 0 ? `Training exited with code ${code}` : null,
      } satisfies TrainingStatus)
      trainingProcess = null
    })
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
