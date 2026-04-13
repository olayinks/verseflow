import { create } from 'zustand'
import type { Suggestion, TranscriptPayload, AppSettings, CaptureMode } from '@shared/types'

interface StatusState {
  connected: boolean
  message: string
}

interface AppState {
  status: StatusState
  isListening: boolean
  captureMode: CaptureMode
  transcript: TranscriptPayload | null
  suggestions: Suggestion[]
  activeSuggestion: Suggestion | null
  settings: AppSettings | null
  settingsPanelOpen: boolean
  helpPanelOpen: boolean

  setStatus: (s: StatusState) => void
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

export const useAppStore = create<AppState>((set, get) => ({
  status: { connected: false, message: 'Initialising…' },
  isListening: false,
  captureMode: 'sermon',
  transcript: null,
  suggestions: [],
  activeSuggestion: null,
  settings: null,
  settingsPanelOpen: false,
  helpPanelOpen: false,

  setStatus: (s) => set({ status: s }),

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
