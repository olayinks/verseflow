// ─────────────────────────────────────────────────────────────────────────────
// src/main/settings-store.ts
//
// Singleton electron-store instance shared by IPC handlers and the main process.
// Import this module wherever persistent settings need to be read or written.
// ─────────────────────────────────────────────────────────────────────────────

import Store from 'electron-store'
import { DEFAULT_SETTINGS, type AppSettings } from '../shared/types'

export const settingsStore = new Store<AppSettings>({
  defaults: DEFAULT_SETTINGS,
  schema: {
    sidecarPort: { type: 'number' },
    presentationDriver: { type: 'string' },
    presentationAppPath: { type: 'string' },
    translations: { type: 'array' },
    maxSuggestions: { type: 'number' },
    semanticThreshold: { type: 'number' },
    lyricsEnabled: { type: 'boolean' },
    audioDevice: { type: 'string' },
    setupCompleted: { type: 'boolean' },
  },
})
