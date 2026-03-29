import { create } from 'zustand'
import type { Suggestion, TranscriptPayload, AppSettings } from '@shared/types'

interface StatusState {
  connected: boolean
  message: string
}

interface AppState {
  status: StatusState
  isListening: boolean
  transcript: TranscriptPayload | null
  suggestions: Suggestion[]
  activeSuggestion: Suggestion | null
  settings: AppSettings | null
  settingsPanelOpen: boolean

  setStatus: (s: StatusState) => void
  setListening: (v: boolean) => void
  setTranscript: (t: TranscriptPayload) => void
  addSuggestion: (s: Suggestion) => void
  clearSuggestions: () => void
  setActiveSuggestion: (s: Suggestion | null) => void
  setSettings: (s: AppSettings) => void
  setSettingsPanelOpen: (v: boolean) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  status: { connected: false, message: 'Initialising…' },
  isListening: false,
  transcript: null,
  suggestions: [],
  activeSuggestion: null,
  settings: null,
  settingsPanelOpen: false,

  setStatus: (s) => set({ status: s }),

  setListening: (v) => {
    set({ isListening: v })
    if (!v) set({ suggestions: [], transcript: null })
  },

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
}))
