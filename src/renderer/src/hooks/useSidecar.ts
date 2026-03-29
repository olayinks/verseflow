// ─────────────────────────────────────────────────────────────────────────────
// src/renderer/src/hooks/useSidecar.ts
//
// Subscribes to all push events from the main process (via preload IPC bridge)
// and writes them into the Zustand store.  Also exposes start/stop controls.
//
// Call this hook once at the top of the component tree (in App.tsx).
// ─────────────────────────────────────────────────────────────────────────────

import { useEffect, useCallback } from 'react'
import { useAppStore } from '../store'

export function useSidecar(): {
  startListening: () => Promise<void>
  stopListening: () => Promise<void>
} {
  const { setStatus, setTranscript, addSuggestion, setListening, setSettings, setSettingsPanelOpen } = useAppStore()

  // Subscribe to IPC push events on mount, unsubscribe on unmount.
  useEffect(() => {
    const api = window.verseflow

    const unsubs = [
      api.onStatus((s) => setStatus(s)),
      api.onTranscript((t) => setTranscript(t)),
      api.onSuggestion((s) => addSuggestion(s)),
      api.onError((e) => setStatus({ connected: false, message: e.message })),
    ]

    // Load persisted settings once on mount.
    // Open the settings panel automatically if setup has never been completed,
    // or if a driver is selected but no app path has been configured.
    api.getSettings().then((s) => {
      setSettings(s)
      if (!s.setupCompleted || (s.presentationDriver !== 'none' && !s.presentationAppPath)) {
        setSettingsPanelOpen(true)
      }
    }).catch(console.error)

    return () => unsubs.forEach((u) => u())
  }, [setStatus, setTranscript, addSuggestion, setSettings])

  const startListening = useCallback(async () => {
    await window.verseflow.startListening()
    setListening(true)
  }, [setListening])

  const stopListening = useCallback(async () => {
    await window.verseflow.stopListening()
    setListening(false)
  }, [setListening])

  return { startListening, stopListening }
}
