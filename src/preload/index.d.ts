// ─────────────────────────────────────────────────────────────────────────────
// src/preload/index.d.ts
//
// Extends the Window interface so TypeScript knows about window.verseflow in
// the renderer without importing Electron/Node types there.
// ─────────────────────────────────────────────────────────────────────────────

import type { AppSettings, AudioDevice, AppLaunchStatus, Suggestion, TranscriptPayload } from '../shared/types'

type Unsubscribe = () => void

export interface VerseFlowAPI {
  startListening: () => Promise<void>
  stopListening: () => Promise<void>
  sendToPresentation: (text: string) => Promise<void>
  getSettings: () => Promise<AppSettings>
  setSettings: (settings: Partial<AppSettings>) => Promise<AppSettings>
  getAudioDevices: () => Promise<AudioDevice[]>
  pickAppPath: () => Promise<string | null>
  checkAndLaunchApp: () => Promise<AppLaunchStatus>
  closeWindow: () => void
  minimizeWindow: () => void
  onTranscript: (cb: (payload: TranscriptPayload) => void) => Unsubscribe
  onSuggestion: (cb: (suggestion: Suggestion) => void) => Unsubscribe
  onStatus: (cb: (status: { connected: boolean; message: string }) => void) => Unsubscribe
  onError: (cb: (err: { message: string }) => void) => Unsubscribe
}

declare global {
  interface Window {
    verseflow: VerseFlowAPI
  }
}
