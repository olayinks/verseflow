// ─────────────────────────────────────────────────────────────────────────────
// src/preload/index.ts
//
// The preload script runs in a special context that has access to both the
// DOM (renderer world) and Node/Electron APIs (main world).  We use
// contextBridge to expose a safe, typed surface to the React UI — the renderer
// never gets direct access to Node or Electron internals.
// ─────────────────────────────────────────────────────────────────────────────

import { contextBridge, ipcRenderer } from 'electron'
import { IPC, type AppSettings, type AudioDevice, type AppLaunchStatus, type Suggestion, type TranscriptPayload, type CaptureMode, type TrainingStatus } from '../shared/types'

// ---------------------------------------------------------------------------
// Typed event-listener helpers
// ---------------------------------------------------------------------------

type Unsubscribe = () => void

function onEvent<T>(channel: string, cb: (payload: T) => void): Unsubscribe {
  const handler = (_: Electron.IpcRendererEvent, payload: T): void => cb(payload)
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.removeListener(channel, handler)
}

// ---------------------------------------------------------------------------
// The API surface exposed to the renderer
// ---------------------------------------------------------------------------

const verseflowAPI = {
  // ── Sidecar control ──────────────────────────────────────────────────────

  startListening: (): Promise<void> => ipcRenderer.invoke(IPC.START_LISTENING),

  stopListening: (): Promise<void> => ipcRenderer.invoke(IPC.STOP_LISTENING),

  setMode: (mode: CaptureMode): Promise<void> => ipcRenderer.invoke(IPC.SET_MODE, mode),

  // ── Presentation driver ──────────────────────────────────────────────────

  sendToPresentation: (text: string): Promise<void> =>
    ipcRenderer.invoke(IPC.SEND_TO_PRESENTATION, text),

  // ── Settings ─────────────────────────────────────────────────────────────

  getSettings: (): Promise<AppSettings> => ipcRenderer.invoke(IPC.GET_SETTINGS),

  setSettings: (settings: Partial<AppSettings>): Promise<AppSettings> =>
    ipcRenderer.invoke(IPC.SET_SETTINGS, settings),

  getAudioDevices: (): Promise<AudioDevice[]> => ipcRenderer.invoke(IPC.GET_AUDIO_DEVICES),

  pickAppPath: (): Promise<string | null> => ipcRenderer.invoke(IPC.APP_PICK_PATH),

  checkAndLaunchApp: (): Promise<AppLaunchStatus> => ipcRenderer.invoke(IPC.APP_CHECK_LAUNCH),

  // ── Window controls ──────────────────────────────────────────────────────

  closeWindow: (): void => ipcRenderer.send('window:close'),

  minimizeWindow: (): void => ipcRenderer.send('window:minimize'),

  // ── Speaker training ─────────────────────────────────────────────────────

  saveSample: (audio: ArrayBuffer, transcript: string): Promise<void> =>
    ipcRenderer.invoke(IPC.TRAINING_SAVE_SAMPLE, audio, transcript),

  getTrainingStatus: (): Promise<TrainingStatus> =>
    ipcRenderer.invoke(IPC.TRAINING_GET_STATUS),

  startTraining: (): Promise<void> =>
    ipcRenderer.invoke(IPC.TRAINING_START),

  onTrainingProgress: (cb: (status: TrainingStatus) => void): Unsubscribe =>
    onEvent(IPC.TRAINING_ON_PROGRESS, cb),

  // ── Push events (main → renderer) ────────────────────────────────────────

  onTranscript: (cb: (payload: TranscriptPayload) => void): Unsubscribe =>
    onEvent(IPC.ON_TRANSCRIPT, cb),

  onSuggestion: (cb: (suggestion: Suggestion) => void): Unsubscribe =>
    onEvent(IPC.ON_SUGGESTION, cb),

  onStatus: (cb: (status: { connected: boolean; message: string }) => void): Unsubscribe =>
    onEvent(IPC.ON_STATUS, cb),

  onError: (cb: (err: { message: string }) => void): Unsubscribe =>
    onEvent(IPC.ON_ERROR, cb),
}

contextBridge.exposeInMainWorld('verseflow', verseflowAPI)
