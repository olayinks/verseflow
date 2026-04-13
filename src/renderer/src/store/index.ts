import { create } from 'zustand'
import type { Suggestion, TranscriptPayload, AppSettings, CaptureMode } from '@shared/types'

interface StatusState {
  connected: boolean
  message: string
}

/**
 * Tracks the sidecar's engine lifecycle independently of the WebSocket
 * connection state so the UI can show a meaningful loading indicator.
 *
 *  disconnected → (WS connects) → loading → (engines ready) → ready
 *                                          → error (on load failure)
 */
export type EngineState = 'disconnected' | 'loading' | 'ready' | 'error'

interface AppState {
  status: StatusState
  engineState: EngineState
  isListening: boolean
  captureMode: CaptureMode
  transcript: TranscriptPayload | null
  suggestions: Suggestion[]
  activeSuggestion: Suggestion | null
  settings: AppSettings | null
  settingsPanelOpen: boolean
  helpPanelOpen: boolean

  // Accepts the raw payload from either the SidecarManager or the sidecar WS
  // message and derives engineState from it automatically.
  setStatus: (s: Record<string, unknown>) => void
  setEngineState: (s: EngineState) => void
  setListening: (v: boolean) => void
  setCaptureMode: (m: CaptureMode) => void
  setTranscript: (t: TranscriptPayload) => void
  addSuggestion: (s: Suggestion) => void
  clearSuggestions: () => void
  setActiveSuggestion: (s: Suggestion | null) => void
  setSettings: (s: AppSettings) => void
  setSettingsPanelOpen: (v: boolean) => void
  setHelpPanelOpen: (v: boolean) => void
}

function deriveEngineState(payload: Record<string, unknown>): EngineState {
  if (payload.state === 'ready')   return 'ready'
  if (payload.state === 'loading') return 'loading'
  if (payload.state === 'error')   return 'error'
  // SidecarManager pushes { connected, message } without a state field.
  // Treat a bare connected=true as "loading" (sidecar connected, engines unknown).
  if (payload.connected === true)  return 'loading'
  return 'disconnected'
}

export const useAppStore = create<AppState>((set, get) => ({
  status: { connected: false, message: 'Connecting…' },
  engineState: 'disconnected',
  isListening: false,
  captureMode: 'sermon',
  transcript: null,
  suggestions: [],
  activeSuggestion: null,
  settings: null,
  settingsPanelOpen: false,
  helpPanelOpen: false,

  setStatus: (payload) => set({
    status: {
      connected: payload.connected === true,
      message: typeof payload.message === 'string' ? payload.message : '',
    },
    engineState: deriveEngineState(payload),
  }),

  setEngineState: (s) => set({ engineState: s }),

  setListening: (v) => {
    set({ isListening: v })
    if (!v) set({ suggestions: [], transcript: null })
  },

  setCaptureMode: (m) => set({ captureMode: m }),

  setTranscript: (t) => set({ transcript: t }),

  addSuggestion: (s) => {
    const { suggestions, settings } = get()
    // Early-exit if already present (avoids full filter scan on duplicate push).
    if (suggestions.some((x) => x.id === s.id)) return
    const max = settings?.maxSuggestions ?? 5
    set({ suggestions: [s, ...suggestions].slice(0, max) })
  },

  clearSuggestions: () => set({ suggestions: [] }),

  setActiveSuggestion: (s) => set({ activeSuggestion: s }),

  setSettings: (s) => set({ settings: s }),

  setSettingsPanelOpen: (v) => set({ settingsPanelOpen: v }),
  setHelpPanelOpen: (v) => set({ helpPanelOpen: v }),
}))
